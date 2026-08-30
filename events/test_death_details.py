from dataclasses import FrozenInstanceError, fields
from importlib import import_module
from inspect import Parameter, signature
from unittest.mock import patch

from django.contrib import admin
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import IntegrityError, migrations, models, transaction
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from . import services
from .models import DeathDetail, Event, EventType
from .services import (
    DeathDetailInput,
    EventInput,
    create_death_detail,
    delete_death_detail,
    update_death_detail,
    update_event,
)


class DeathDetailModelTests(TestCase):
    def setUp(self) -> None:
        self.death_type = EventType.objects.get(code="death")
        self.other_type = EventType.objects.get(code="other")
        self.death_event = Event.objects.create(event_type=self.death_type)

    def test_model_has_exact_fields_and_metadata(self) -> None:
        self.assertEqual(DeathDetail.__bases__, (models.Model,))
        self.assertEqual(
            {field.name for field in DeathDetail._meta.local_fields},
            {"id", "event", "cause", "circumstances"},
        )
        event_field = DeathDetail._meta.get_field("event")
        self.assertIsInstance(event_field, models.OneToOneField)
        self.assertIs(event_field.remote_field.model, Event)
        self.assertIs(event_field.remote_field.on_delete, models.CASCADE)
        self.assertEqual(event_field.remote_field.related_name, "death_detail")
        self.assertTrue(DeathDetail._meta.get_field("cause").blank)
        self.assertTrue(DeathDetail._meta.get_field("circumstances").blank)
        self.assertEqual(DeathDetail._meta.verbose_name, "Detail úmrtí")
        self.assertEqual(
            DeathDetail._meta.verbose_name_plural,
            "Detaily úmrtí",
        )

    def test_requires_at_least_one_text(self) -> None:
        detail = DeathDetail(event=self.death_event)

        with self.assertRaises(ValidationError) as context:
            detail.full_clean()

        self.assertEqual(
            context.exception.error_dict[NON_FIELD_ERRORS][0].code,
            "death_detail_empty",
        )

    def test_requires_system_death_event(self) -> None:
        event = Event.objects.create(event_type=self.other_type)
        detail = DeathDetail(event=event, cause="Příčina")

        with self.assertRaises(ValidationError) as context:
            detail.full_clean()

        self.assertEqual(
            context.exception.error_dict["event"][0].code,
            "death_detail_event_type_required",
        )

        EventType.objects.filter(pk=self.death_type.pk).update(is_system=False)
        system_flag_detail = DeathDetail(
            event=self.death_event,
            cause="Příčina",
        )
        with self.assertRaises(ValidationError) as system_context:
            system_flag_detail.full_clean()
        self.assertEqual(
            system_context.exception.error_dict["event"][0].code,
            "death_detail_event_type_required",
        )

    def test_one_to_one_constraint_and_event_cascade(self) -> None:
        first = DeathDetail.objects.create(
            event=self.death_event,
            cause="Příčina",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DeathDetail.objects.create(
                    event=self.death_event,
                    circumstances="Okolnosti",
                )

        self.death_event.delete()
        self.assertFalse(DeathDetail.objects.filter(pk=first.pk).exists())

    def test_string_representation_uses_parent_event(self) -> None:
        detail = DeathDetail(
            event=Event(event_type=self.death_type, title="Úmrtí Jana"),
            cause="Příčina",
        )

        self.assertEqual(str(detail), "Detail úmrtí – Úmrtí Jana")


class DeathDetailServiceApiTests(SimpleTestCase):
    def test_input_is_frozen_slotted_with_stable_fields(self) -> None:
        data = DeathDetailInput()

        self.assertFalse(hasattr(data, "__dict__"))
        self.assertEqual(
            tuple(field.name for field in fields(DeathDetailInput)),
            ("cause", "circumstances"),
        )
        with self.assertRaises(FrozenInstanceError):
            data.cause = "Změna"

    def test_services_are_keyword_only_and_public(self) -> None:
        for service in (
            create_death_detail,
            update_death_detail,
            delete_death_detail,
        ):
            self.assertTrue(
                all(
                    parameter.kind is Parameter.KEYWORD_ONLY
                    for parameter in signature(service).parameters.values()
                )
            )
        for name in (
            "DeathDetailInput",
            "create_death_detail",
            "update_death_detail",
            "delete_death_detail",
        ):
            self.assertIn(name, services.__all__)


class DeathDetailServiceTests(TestCase):
    def setUp(self) -> None:
        self.death_type = EventType.objects.get(code="death")
        self.other_type = EventType.objects.get(code="other")
        self.event = Event.objects.create(
            event_type=self.death_type,
            title="Úmrtí",
        )

    def assert_error_code(self, context, *, key: str, code: str) -> None:
        self.assertEqual(context.exception.error_dict[key][0].code, code)

    def test_create_normalizes_and_links_detail(self) -> None:
        detail = create_death_detail(
            event=self.event,
            data=DeathDetailInput(
                cause="  Přirozená příčina  ",
                circumstances="  V domácím prostředí.  ",
            ),
        )

        self.assertEqual(detail.event, self.event)
        self.assertEqual(detail.cause, "Přirozená příčina")
        self.assertEqual(detail.circumstances, "V domácím prostředí.")

    def test_create_locks_parent_event(self) -> None:
        original_lock = Event.objects.select_for_update

        with patch.object(
            Event.objects,
            "select_for_update",
            wraps=original_lock,
        ) as event_lock:
            create_death_detail(
                event=self.event,
                data=DeathDetailInput(cause="Příčina"),
            )

        event_lock.assert_called_once_with()

    def test_create_allows_archived_but_rejects_soft_deleted_event(self) -> None:
        Event.objects.filter(pk=self.event.pk).update(archived_at=timezone.now())
        archived_detail = create_death_detail(
            event=self.event,
            data=DeathDetailInput(cause="Příčina"),
        )
        self.assertEqual(archived_detail.event_id, self.event.pk)

        other_event = Event.objects.create(event_type=self.death_type)
        Event.objects.filter(pk=other_event.pk).update(deleted_at=timezone.now())
        with self.assertRaises(ValidationError) as context:
            create_death_detail(
                event=other_event,
                data=DeathDetailInput(cause="Příčina"),
            )
        self.assert_error_code(
            context,
            key="event",
            code="death_detail_event_deleted",
        )

    def test_create_rejects_invalid_parent_empty_data_and_duplicate(self) -> None:
        other_event = Event.objects.create(event_type=self.other_type)
        with self.assertRaises(ValidationError) as type_context:
            create_death_detail(
                event=other_event,
                data=DeathDetailInput(cause="Příčina"),
            )
        self.assert_error_code(
            type_context,
            key="event",
            code="death_detail_event_type_required",
        )

        with self.assertRaises(ValidationError) as empty_context:
            create_death_detail(
                event=self.event,
                data=DeathDetailInput(),
            )
        self.assert_error_code(
            empty_context,
            key=NON_FIELD_ERRORS,
            code="death_detail_empty",
        )
        self.assertFalse(DeathDetail.objects.filter(event=self.event).exists())

        create_death_detail(
            event=self.event,
            data=DeathDetailInput(cause="První"),
        )
        with self.assertRaises(ValidationError) as duplicate_context:
            create_death_detail(
                event=self.event,
                data=DeathDetailInput(cause="Druhý"),
            )
        self.assert_error_code(
            duplicate_context,
            key="event",
            code="death_detail_exists",
        )

    def test_create_maps_confirmed_database_duplicate(self) -> None:
        collision = IntegrityError("UNIQUE constraint failed")
        with (
            patch.object(
                DeathDetail,
                "save",
                side_effect=collision,
            ) as save_detail,
            patch.object(DeathDetail.objects, "filter") as competing_detail,
        ):
            competing_detail.return_value.exists.return_value = True
            with self.assertRaises(ValidationError) as context:
                create_death_detail(
                    event=self.event,
                    data=DeathDetailInput(cause="Příčina"),
                )

        save_detail.assert_called_once_with()
        competing_detail.return_value.exists.assert_called_once_with()
        self.assert_error_code(
            context,
            key="event",
            code="death_detail_exists",
        )

    def test_create_does_not_mask_unrelated_integrity_error(self) -> None:
        collision = IntegrityError("FOREIGN KEY constraint failed")
        with (
            patch.object(DeathDetail, "save", side_effect=collision),
            patch.object(DeathDetail.objects, "filter") as competing_detail,
        ):
            competing_detail.return_value.exists.return_value = False
            with self.assertRaisesRegex(
                IntegrityError,
                "FOREIGN KEY constraint failed",
            ):
                create_death_detail(
                    event=self.event,
                    data=DeathDetailInput(cause="Příčina"),
                )

    def test_create_rejects_unsaved_and_missing_event(self) -> None:
        missing = Event.objects.create(event_type=self.death_type)
        Event.objects.filter(pk=missing.pk).delete()
        for event in (Event(event_type=self.death_type), missing):
            with self.subTest(event=event.pk):
                with self.assertRaises(ValidationError) as context:
                    create_death_detail(
                        event=event,
                        data=DeathDetailInput(cause="Příčina"),
                    )
                self.assert_error_code(
                    context,
                    key="event",
                    code="death_detail_event_unsaved",
                )

    def test_update_normalizes_and_preserves_parent(self) -> None:
        detail = create_death_detail(
            event=self.event,
            data=DeathDetailInput(cause="Původní"),
        )

        updated = update_death_detail(
            death_detail=detail,
            data=DeathDetailInput(
                cause="  Nová příčina ",
                circumstances=" Nové okolnosti. ",
            ),
        )

        self.assertEqual(updated.event, self.event)
        self.assertEqual(updated.cause, "Nová příčina")
        self.assertEqual(updated.circumstances, "Nové okolnosti.")

    def test_update_and_delete_lock_event_before_detail(self) -> None:
        for operation in ("update", "delete"):
            with self.subTest(operation=operation):
                event = Event.objects.create(event_type=self.death_type)
                detail = create_death_detail(
                    event=event,
                    data=DeathDetailInput(cause="Příčina"),
                )
                lock_order: list[str] = []
                original_event_lock = Event.objects.select_for_update
                original_detail_lock = DeathDetail.objects.select_for_update

                def lock_event():
                    lock_order.append("event")
                    return original_event_lock()

                def lock_detail():
                    lock_order.append("detail")
                    return original_detail_lock()

                with (
                    patch.object(
                        Event.objects,
                        "select_for_update",
                        side_effect=lock_event,
                    ),
                    patch.object(
                        DeathDetail.objects,
                        "select_for_update",
                        side_effect=lock_detail,
                    ),
                ):
                    if operation == "update":
                        update_death_detail(
                            death_detail=detail,
                            data=DeathDetailInput(cause="Změna"),
                        )
                    else:
                        delete_death_detail(death_detail=detail)

                self.assertEqual(lock_order, ["event", "detail"])

    def test_update_rolls_back_invalid_data_and_rejects_deleted_parent(
        self,
    ) -> None:
        detail = create_death_detail(
            event=self.event,
            data=DeathDetailInput(cause="Původní"),
        )
        with self.assertRaises(ValidationError):
            update_death_detail(
                death_detail=detail,
                data=DeathDetailInput(),
            )
        detail.refresh_from_db()
        self.assertEqual(detail.cause, "Původní")

        Event.objects.filter(pk=self.event.pk).update(deleted_at=timezone.now())
        with self.assertRaises(ValidationError) as context:
            update_death_detail(
                death_detail=detail,
                data=DeathDetailInput(cause="Zakázaná změna"),
            )
        self.assert_error_code(
            context,
            key="event",
            code="death_detail_event_deleted",
        )

    def test_update_and_delete_reject_unsaved_or_missing_detail(self) -> None:
        missing = DeathDetail.objects.create(
            event=self.event,
            cause="Chybějící",
        )
        DeathDetail.objects.filter(pk=missing.pk).delete()
        for detail in (DeathDetail(event=self.event), missing):
            with self.subTest(detail=detail.pk):
                with self.assertRaises(ValidationError) as update_context:
                    update_death_detail(
                        death_detail=detail,
                        data=DeathDetailInput(cause="Změna"),
                    )
                self.assert_error_code(
                    update_context,
                    key="death_detail",
                    code="death_detail_unsaved",
                )
                with self.assertRaises(ValidationError) as delete_context:
                    delete_death_detail(death_detail=detail)
                self.assert_error_code(
                    delete_context,
                    key="death_detail",
                    code="death_detail_unsaved",
                )

    def test_delete_is_explicit_and_preserves_parent_event(self) -> None:
        detail = create_death_detail(
            event=self.event,
            data=DeathDetailInput(cause="Příčina"),
        )

        delete_death_detail(death_detail=detail)

        self.assertFalse(DeathDetail.objects.filter(pk=detail.pk).exists())
        self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())

    def test_update_and_delete_allow_archived_parent(self) -> None:
        detail = create_death_detail(
            event=self.event,
            data=DeathDetailInput(cause="Původní"),
        )
        Event.objects.filter(pk=self.event.pk).update(
            archived_at=timezone.now()
        )

        updated = update_death_detail(
            death_detail=detail,
            data=DeathDetailInput(cause="Změna"),
        )
        delete_death_detail(death_detail=updated)

        self.assertFalse(DeathDetail.objects.filter(pk=detail.pk).exists())

    def test_delete_rejects_soft_deleted_parent(self) -> None:
        detail = create_death_detail(
            event=self.event,
            data=DeathDetailInput(cause="Příčina"),
        )
        Event.objects.filter(pk=self.event.pk).update(
            deleted_at=timezone.now()
        )

        with self.assertRaises(ValidationError) as context:
            delete_death_detail(death_detail=detail)

        self.assert_error_code(
            context,
            key="event",
            code="death_detail_event_deleted",
        )
        self.assertTrue(DeathDetail.objects.filter(pk=detail.pk).exists())

    def test_delete_can_repair_detail_after_parent_type_corruption(self) -> None:
        detail = create_death_detail(
            event=self.event,
            data=DeathDetailInput(cause="Příčina"),
        )
        Event.objects.filter(pk=self.event.pk).update(
            event_type=self.other_type
        )

        delete_death_detail(death_detail=detail)

        self.assertFalse(DeathDetail.objects.filter(pk=detail.pk).exists())

    def test_event_type_change_requires_explicit_detail_removal(self) -> None:
        detail = create_death_detail(
            event=self.event,
            data=DeathDetailInput(cause="Příčina"),
        )

        with self.assertRaises(ValidationError) as context:
            update_event(
                event=self.event,
                data=EventInput(
                    event_type=self.other_type,
                    title="Nesmí se uložit",
                ),
                participants=(),
            )
        self.assert_error_code(
            context,
            key="event_type",
            code="death_detail_event_type_required",
        )
        self.event.refresh_from_db()
        self.assertEqual(self.event.event_type, self.death_type)
        self.assertEqual(self.event.title, "Úmrtí")
        self.assertTrue(DeathDetail.objects.filter(pk=detail.pk).exists())


class DeathDetailMigrationTests(SimpleTestCase):
    migration = import_module("events.migrations.0008_deathdetail")

    def test_migration_contains_only_death_detail_model(self) -> None:
        operations = self.migration.Migration.operations

        self.assertEqual(len(operations), 1)
        self.assertIsInstance(operations[0], migrations.CreateModel)
        self.assertEqual(operations[0].name, "DeathDetail")

    def test_migration_has_exact_dependency(self) -> None:
        self.assertEqual(
            self.migration.Migration.dependencies,
            [("events", "0007_event_participant")],
        )


class DeathDetailAdminTests(SimpleTestCase):
    def test_death_detail_is_not_registered(self) -> None:
        self.assertFalse(admin.site.is_registered(DeathDetail))

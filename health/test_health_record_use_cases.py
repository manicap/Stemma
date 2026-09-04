from inspect import Parameter, signature
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import QuerySet
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from common.choices import AccessLevel
from materials.models import (
    Attachment,
    AttachmentRole,
    HealthRecordAttachment,
)
from materials.services import AttachmentLinkInput
from people.models import Person

from . import use_cases
from .models import HealthRecord, HealthRecordType
from .services import HealthRecordInput
from .use_cases import get_health_record_detail, list_health_records


class HealthRecordUseCaseApiTests(SimpleTestCase):
    def test_public_contract_is_exact_and_keyword_only(self) -> None:
        self.assertEqual(
            use_cases.__all__,
            (
                "create_health_record",
                "create_health_record_attachment",
                "get_health_record_detail",
                "list_health_records",
                "update_health_record",
                "update_health_record_attachment",
            ),
        )
        for callable_object, names in (
            (use_cases.create_health_record, ("data", "actor")),
            (
                use_cases.create_health_record_attachment,
                ("health_record", "data", "actor"),
            ),
            (list_health_records, ("person", "actor")),
            (get_health_record_detail, ("health_record_id", "actor")),
            (
                use_cases.update_health_record,
                ("health_record", "data", "actor"),
            ),
            (
                use_cases.update_health_record_attachment,
                ("link", "health_record", "data", "actor"),
            ),
        ):
            with self.subTest(callable=callable_object.__name__):
                parameters = signature(callable_object).parameters
                self.assertEqual(tuple(parameters), names)
                self.assertTrue(
                    all(
                        parameter.kind is Parameter.KEYWORD_ONLY
                        for parameter in parameters.values()
                    )
                )

    def test_collection_is_an_exact_selector_delegation(self) -> None:
        person = Person(pk=17)
        actor = AnonymousUser()
        sentinel = object()
        with patch(
            "health.use_cases.get_visible_health_records",
            return_value=sentinel,
        ) as selector:
            result = list_health_records(person=person, actor=actor)

        self.assertIs(result, sentinel)
        selector.assert_called_once_with(person=person, actor=actor)

    def test_detail_is_an_exact_selector_delegation(self) -> None:
        actor = AnonymousUser()
        sentinel = HealthRecord(pk=29)
        with patch(
            "health.use_cases.get_visible_health_record",
            return_value=sentinel,
        ) as selector:
            result = get_health_record_detail(
                health_record_id=29,
                actor=actor,
            )

        self.assertIs(result, sentinel)
        selector.assert_called_once_with(health_record_id=29, actor=actor)

    def test_detail_preserves_the_exact_selector_exception(self) -> None:
        actor = AnonymousUser()
        unavailable = HealthRecord.DoesNotExist("unavailable")
        with patch(
            "health.use_cases.get_visible_health_record",
            side_effect=unavailable,
        ):
            with self.assertRaises(HealthRecord.DoesNotExist) as raised:
                get_health_record_detail(health_record_id=31, actor=actor)

        self.assertIs(raised.exception, unavailable)

    def test_create_is_an_exact_service_delegation(self) -> None:
        actor = AnonymousUser()
        data = HealthRecordInput(person=Person(), record_type=HealthRecordType())
        sentinel = HealthRecord(pk=37)
        with patch(
            "health.use_cases.create_health_record_service",
            return_value=sentinel,
        ) as service:
            result = use_cases.create_health_record(data=data, actor=actor)

        self.assertIs(result, sentinel)
        service.assert_called_once_with(data=data, actor=actor)

    def test_update_is_an_exact_service_delegation(self) -> None:
        actor = AnonymousUser()
        record = HealthRecord(pk=41)
        data = HealthRecordInput(person=Person(), record_type=HealthRecordType())
        sentinel = HealthRecord(pk=41)
        with patch(
            "health.use_cases.update_health_record_service",
            return_value=sentinel,
        ) as service:
            result = use_cases.update_health_record(
                health_record=record,
                data=data,
                actor=actor,
            )

        self.assertIs(result, sentinel)
        service.assert_called_once_with(
            health_record=record,
            data=data,
            actor=actor,
        )

    def test_write_use_cases_preserve_exact_service_exceptions(self) -> None:
        actor = AnonymousUser()
        record = HealthRecord(pk=43)
        data = HealthRecordInput(person=Person(), record_type=HealthRecordType())
        cases = (
            (
                "health.use_cases.create_health_record_service",
                use_cases.create_health_record,
                {"data": data, "actor": actor},
                PermissionDenied("denied"),
            ),
            (
                "health.use_cases.update_health_record_service",
                use_cases.update_health_record,
                {"health_record": record, "data": data, "actor": actor},
                HealthRecord.DoesNotExist("unavailable"),
            ),
            (
                "health.use_cases.create_health_record_service",
                use_cases.create_health_record,
                {"data": data, "actor": actor},
                ValidationError({"record_type": ["inactive"]}),
            ),
        )
        for target, callable_object, arguments, error in cases:
            with self.subTest(callable=callable_object.__name__):
                with patch(target, side_effect=error):
                    with self.assertRaises(type(error)) as raised:
                        callable_object(**arguments)
                self.assertIs(raised.exception, error)

    def test_attachment_write_use_cases_are_exact_service_delegations(
        self,
    ) -> None:
        actor = AnonymousUser()
        record = HealthRecord(pk=47)
        link = HealthRecordAttachment(pk=53)
        data = AttachmentLinkInput(
            attachment=Attachment(),
            role=AttachmentRole(),
        )
        create_sentinel = HealthRecordAttachment(pk=59)
        update_sentinel = HealthRecordAttachment(pk=61)

        with patch(
            "health.use_cases.create_attachment_service",
            return_value=create_sentinel,
        ) as create_service:
            created = use_cases.create_health_record_attachment(
                health_record=record,
                data=data,
                actor=actor,
            )
        self.assertIs(created, create_sentinel)
        create_service.assert_called_once_with(
            health_record=record,
            data=data,
            actor=actor,
        )

        with patch(
            "health.use_cases.update_attachment_service",
            return_value=update_sentinel,
        ) as update_service:
            updated = use_cases.update_health_record_attachment(
                link=link,
                health_record=record,
                data=data,
                actor=actor,
            )
        self.assertIs(updated, update_sentinel)
        update_service.assert_called_once_with(
            link=link,
            health_record=record,
            data=data,
            actor=actor,
        )

    def test_attachment_write_use_cases_preserve_exact_service_exceptions(
        self,
    ) -> None:
        actor = AnonymousUser()
        record = HealthRecord(pk=67)
        link = HealthRecordAttachment(pk=71)
        data = AttachmentLinkInput(
            attachment=Attachment(),
            role=AttachmentRole(),
        )
        cases = (
            (
                "health.use_cases.create_attachment_service",
                use_cases.create_health_record_attachment,
                {"health_record": record, "data": data, "actor": actor},
                PermissionDenied("denied"),
            ),
            (
                "health.use_cases.update_attachment_service",
                use_cases.update_health_record_attachment,
                {
                    "link": link,
                    "health_record": record,
                    "data": data,
                    "actor": actor,
                },
                HealthRecordAttachment.DoesNotExist("unavailable"),
            ),
            (
                "health.use_cases.create_attachment_service",
                use_cases.create_health_record_attachment,
                {"health_record": record, "data": data, "actor": actor},
                ValidationError({"attachment": ["invalid"]}),
            ),
        )
        for target, callable_object, arguments, error in cases:
            with self.subTest(callable=callable_object.__name__):
                with patch(target, side_effect=error):
                    with self.assertRaises(type(error)) as raised:
                        callable_object(**arguments)
                self.assertIs(raised.exception, error)


class HealthRecordUseCaseIntegrationTests(TestCase):
    def setUp(self) -> None:
        self.person = Person.objects.create(
            first_name="Anna",
            access_level=AccessLevel.PUBLIC,
        )
        self.active_type = HealthRecordType.objects.create(
            code="active",
            name="Aktivní",
        )
        self.inactive_type = HealthRecordType.objects.create(
            code="inactive",
            name="Neaktivní",
            is_active=False,
        )
        self.actor = self.user("reader", "view_restricted_content")

    def user(self, username: str, *codenames: str, **values: object):
        actor = get_user_model().objects.create_user(username=username, **values)
        for codename in codenames:
            actor.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label="accounts",
                    content_type__model="user",
                    codename=codename,
                )
            )
        return actor

    def record(self, **changes: object) -> HealthRecord:
        values = {
            "person": self.person,
            "record_type": self.active_type,
            "title": "Záznam",
            "access_level": AccessLevel.RESTRICTED,
        }
        values.update(changes)
        return HealthRecord.objects.create(**values)

    def grant(self, actor, app_label: str, codename: str) -> None:
        actor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label=app_label,
                codename=codename,
            )
        )

    def ids(self, *, person: Person | None = None, actor=None) -> set[int]:
        return set(
            list_health_records(
                person=person or self.person,
                actor=self.actor if actor is None else actor,
            ).values_list("pk", flat=True)
        )

    def test_actor_with_access_gets_collection_and_detail(self) -> None:
        record = self.record()

        result = list_health_records(person=self.person, actor=self.actor)

        self.assertIsInstance(result, QuerySet)
        self.assertEqual(list(result), [record])
        self.assertEqual(
            get_health_record_detail(
                health_record_id=record.pk,
                actor=self.actor,
            ),
            record,
        )

    def test_person_access_does_not_grant_record_access(self) -> None:
        hidden = self.record(access_level=AccessLevel.ADMIN_ONLY)

        self.assertEqual(self.ids(), set())
        with self.assertRaises(HealthRecord.DoesNotExist):
            get_health_record_detail(
                health_record_id=hidden.pk,
                actor=self.actor,
            )

    def test_inaccessible_person_hides_collection_and_detail(self) -> None:
        hidden_person = Person.objects.create(
            first_name="Skrytá",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        hidden = self.record(person=hidden_person)

        self.assertEqual(self.ids(person=hidden_person), set())
        with self.assertRaises(HealthRecord.DoesNotExist):
            get_health_record_detail(
                health_record_id=hidden.pk,
                actor=self.actor,
            )

    def test_person_lifecycle_hides_collection_and_detail(self) -> None:
        superuser = self.user("superuser", is_superuser=True)
        for index, field in enumerate(("archived_at", "deleted_at")):
            person = Person.objects.create(first_name=f"Osoba {index}")
            record = self.record(person=person)
            Person.objects.filter(pk=person.pk).update(
                **{field: timezone.now()}
            )
            with self.subTest(field=field):
                self.assertEqual(self.ids(person=person, actor=superuser), set())
                with self.assertRaises(HealthRecord.DoesNotExist):
                    get_health_record_detail(
                        health_record_id=record.pk,
                        actor=superuser,
                    )

    def test_record_lifecycle_and_inactive_type_fail_closed(self) -> None:
        records = (
            self.record(title="Archivovaný", archived_at=timezone.now()),
            self.record(title="Odstraněný", deleted_at=timezone.now()),
            self.record(title="Neaktivní typ", record_type=self.inactive_type),
        )

        self.assertEqual(self.ids(), set())
        for record in records:
            with self.subTest(record=record.pk):
                with self.assertRaises(HealthRecord.DoesNotExist):
                    get_health_record_detail(
                        health_record_id=record.pk,
                        actor=self.actor,
                    )

    def test_collection_and_detail_keep_identical_visibility(self) -> None:
        visible = self.record(title="Viditelný")
        hidden = self.record(
            title="Skrytý",
            access_level=AccessLevel.ADMIN_ONLY,
        )

        self.assertEqual(self.ids(), {visible.pk})
        self.assertEqual(
            get_health_record_detail(
                health_record_id=visible.pk,
                actor=self.actor,
            ),
            visible,
        )
        with self.assertRaises(HealthRecord.DoesNotExist):
            get_health_record_detail(
                health_record_id=hidden.pk,
                actor=self.actor,
            )

    def test_hidden_missing_malformed_and_inactive_ids_are_indistinguishable(
        self,
    ) -> None:
        hidden = self.record(access_level=AccessLevel.ADMIN_ONLY)
        archived = self.record(archived_at=timezone.now())
        ids = (hidden.pk, archived.pk, hidden.pk + 1000, "bad-id", None, True)

        for record_id in ids:
            with self.subTest(record_id=record_id):
                with self.assertRaises(HealthRecord.DoesNotExist):
                    get_health_record_detail(
                        health_record_id=record_id,
                        actor=self.actor,
                    )

    def test_invalid_actor_validation_is_preserved(self) -> None:
        record = self.record()
        with self.assertRaises(ValidationError) as collection_error:
            list_health_records(person=self.person, actor=None)
        with self.assertRaises(ValidationError) as detail_error:
            get_health_record_detail(health_record_id=record.pk, actor=None)

        self.assertEqual(
            collection_error.exception.error_dict["actor"][0].code,
            "actor_invalid",
        )
        self.assertEqual(
            detail_error.exception.error_dict["actor"][0].code,
            "actor_invalid",
        )

    def test_authorized_actor_can_create_and_update_through_use_cases(
        self,
    ) -> None:
        self.grant(self.actor, "health", "add_healthrecord")
        self.grant(self.actor, "health", "change_healthrecord")
        data = HealthRecordInput(
            person=self.person,
            record_type=self.active_type,
            title="Nový",
        )

        created = use_cases.create_health_record(data=data, actor=self.actor)
        updated = use_cases.update_health_record(
            health_record=created,
            data=HealthRecordInput(
                person=self.person,
                record_type=self.active_type,
                title="Změněný",
            ),
            actor=self.actor,
        )

        self.assertEqual(created.created_by_id, self.actor.pk)
        self.assertEqual(updated.title, "Změněný")
        self.assertEqual(updated.created_by_id, self.actor.pk)

    def test_unauthorized_actor_cannot_create_or_update_through_use_cases(
        self,
    ) -> None:
        data = HealthRecordInput(
            person=self.person,
            record_type=self.active_type,
            title="Zakázaný",
        )
        with self.assertRaises(PermissionDenied):
            use_cases.create_health_record(data=data, actor=self.actor)

        self.grant(self.actor, "health", "add_healthrecord")
        created = use_cases.create_health_record(data=data, actor=self.actor)
        with self.assertRaises(PermissionDenied):
            use_cases.update_health_record(
                health_record=created,
                data=HealthRecordInput(
                    person=self.person,
                    record_type=self.active_type,
                    title="Obejití",
                ),
                actor=self.actor,
            )

        created.refresh_from_db()
        self.assertEqual(created.title, "Zakázaný")

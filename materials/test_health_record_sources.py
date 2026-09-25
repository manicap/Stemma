from importlib import import_module
from inspect import Parameter, signature
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, migrations, models
from django.db.models import QuerySet
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from common.choices import AccessLevel
from health.models import HealthRecord, HealthRecordType
from health.permissions import get_health_record_visibility_filter
from people.models import Person
from places.models import Place

from . import selectors, source_services
from .choices import SourceSupport
from .models import (
    HealthRecordSource,
    Source,
    SourceLinkModel,
    SourceRole,
    SourceType,
)
from .selectors import get_visible_health_record_source_links
from .source_services import (
    SourceLinkInput,
    create_health_record_source,
    update_health_record_source,
)


class HealthRecordSourceApiTests(SimpleTestCase):
    def test_model_and_public_contract_follow_source_conventions(self) -> None:
        self.assertEqual(HealthRecordSource.__bases__, (SourceLinkModel,))
        health_record = HealthRecordSource._meta.get_field("health_record")
        source = HealthRecordSource._meta.get_field("source")
        self.assertIs(health_record.remote_field.model, HealthRecord)
        self.assertIs(health_record.remote_field.on_delete, models.PROTECT)
        self.assertEqual(health_record.remote_field.related_name, "source_links")
        self.assertIs(source.remote_field.model, Source)
        self.assertIs(source.remote_field.on_delete, models.PROTECT)
        self.assertEqual(
            source.remote_field.related_name,
            "healthrecordsource_links",
        )
        self.assertFalse(admin.site.is_registered(HealthRecordSource))

        expectations = (
            (
                create_health_record_source,
                ("health_record", "data", "actor"),
            ),
            (
                update_health_record_source,
                ("link", "health_record", "data", "actor"),
            ),
            (
                get_visible_health_record_source_links,
                ("health_record", "actor"),
            ),
        )
        for callable_object, names in expectations:
            with self.subTest(callable=callable_object.__name__):
                parameters = signature(callable_object).parameters
                self.assertEqual(tuple(parameters), names)
                self.assertTrue(
                    all(
                        parameter.kind is Parameter.KEYWORD_ONLY
                        for parameter in parameters.values()
                    )
                )

    def test_only_contextual_actor_aware_read_api_is_exposed(self) -> None:
        self.assertIn(
            "get_visible_health_record_source_links",
            selectors.__all__,
        )
        self.assertNotIn("get_health_record_source_links", selectors.__all__)
        self.assertNotIn(
            "get_visible_health_record_source_link",
            selectors.__all__,
        )
        self.assertIn("create_health_record_source", source_services.__all__)
        self.assertIn("update_health_record_source", source_services.__all__)


class HealthRecordSourceServiceTests(TestCase):
    def setUp(self) -> None:
        self.person = Person.objects.create(first_name="Anna")
        self.record_type = HealthRecordType.objects.create(
            code="test",
            name="Test",
        )
        self.health_record = HealthRecord.objects.create(
            person=self.person,
            record_type=self.record_type,
            title="Záznam",
        )
        self.source_type = SourceType.objects.create(
            code="archive",
            name="Archiv",
        )
        self.role = SourceRole.objects.create(code="evidence", name="Doklad")
        self.source = Source.objects.create(
            source_type=self.source_type,
            title="Lékařská zpráva",
        )
        self.actor = get_user_model().objects.create_user(username="writer")
        for app_label, codename in (
            ("materials", "add_healthrecordsource"),
            ("materials", "change_healthrecordsource"),
            ("accounts", "view_restricted_content"),
        ):
            self.actor.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label=app_label,
                    codename=codename,
                )
            )

    def data(self, **changes: object) -> SourceLinkInput:
        values = {
            "source": self.source,
            "role": self.role,
            "support_strength": SourceSupport.CONFIRMS,
            "cited_part": "  strana 2  ",
            "excerpt": "  nález  ",
            "interpretation": "  potvrzení  ",
            "access_level": AccessLevel.RESTRICTED,
        }
        values.update(changes)
        return SourceLinkInput(**values)

    def user(self, username: str, *permissions: str, **values: object):
        actor = get_user_model().objects.create_user(username=username, **values)
        for permission_name in permissions:
            app_label, codename = permission_name.split(".", maxsplit=1)
            actor.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label=app_label,
                    codename=codename,
                )
            )
        return actor

    def test_create_and_update_use_actor_aware_health_service(self) -> None:
        link = create_health_record_source(
            health_record=self.health_record,
            data=self.data(),
            actor=self.actor,
        )
        self.assertIsInstance(link, HealthRecordSource)
        self.assertEqual(link.health_record, self.health_record)
        self.assertEqual(link.cited_part, "strana 2")
        self.assertEqual(link.excerpt, "nález")
        self.assertEqual(link.interpretation, "potvrzení")

        updated = update_health_record_source(
            link=link,
            health_record=self.health_record,
            data=self.data(cited_part="  strana 3  "),
            actor=self.actor,
        )
        self.assertEqual(updated.pk, link.pk)
        self.assertEqual(updated.cited_part, "strana 3")

    def test_create_rejects_archived_or_deleted_health_record(self) -> None:
        now = timezone.now()
        HealthRecord.objects.filter(pk=self.health_record.pk).update(
            archived_at=now
        )
        with self.assertRaises(HealthRecord.DoesNotExist):
            create_health_record_source(
                health_record=self.health_record,
                data=self.data(),
                actor=self.actor,
            )

        HealthRecord.objects.filter(pk=self.health_record.pk).update(
            archived_at=None,
            deleted_at=now,
        )
        with self.assertRaises(HealthRecord.DoesNotExist):
            create_health_record_source(
                health_record=self.health_record,
                data=self.data(),
                actor=self.actor,
            )

    def test_update_rejects_archived_target_and_deleted_link(
        self,
    ) -> None:
        link = create_health_record_source(
            health_record=self.health_record,
            data=self.data(),
            actor=self.actor,
        )
        HealthRecord.objects.filter(pk=self.health_record.pk).update(
            archived_at=timezone.now()
        )
        with self.assertRaises(HealthRecordSource.DoesNotExist):
            update_health_record_source(
                link=link,
                health_record=self.health_record,
                data=self.data(),
                actor=self.actor,
            )

    def test_actor_must_be_current_active_and_have_exact_permission(self) -> None:
        link = create_health_record_source(
            health_record=self.health_record,
            data=self.data(),
            actor=self.actor,
        )
        no_permission = self.user(
            "no-source-permission",
            "accounts.view_restricted_content",
        )
        inactive = self.user(
            "inactive-source-writer",
            "accounts.view_restricted_content",
            "materials.add_healthrecordsource",
            "materials.change_healthrecordsource",
            is_active=False,
        )
        missing = self.user(
            "missing-source-writer",
            "accounts.view_restricted_content",
            "materials.add_healthrecordsource",
            "materials.change_healthrecordsource",
        )
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk
        forged = SimpleNamespace(is_authenticated=True, pk=self.actor.pk)

        for actor in (
            AnonymousUser(),
            no_permission,
            inactive,
            missing,
            forged,
        ):
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionDenied):
                    create_health_record_source(
                        health_record=self.health_record,
                        data=self.data(),
                        actor=actor,
                    )
                with self.assertRaises(PermissionDenied):
                    update_health_record_source(
                        link=link,
                        health_record=self.health_record,
                        data=self.data(cited_part="Zakázáno"),
                        actor=actor,
                    )

        link.refresh_from_db()
        self.assertEqual(link.cited_part, "strana 2")
        self.assertEqual(HealthRecordSource.objects.count(), 1)

    def test_model_permission_does_not_bypass_health_or_person_policy(
        self,
    ) -> None:
        link_writer = self.user(
            "source-link-only",
            "materials.add_healthrecordsource",
            "materials.change_healthrecordsource",
        )
        with self.assertRaises(HealthRecord.DoesNotExist):
            create_health_record_source(
                health_record=self.health_record,
                data=self.data(access_level=AccessLevel.PUBLIC),
                actor=link_writer,
            )

        Person.objects.filter(pk=self.person.pk).update(
            access_level=AccessLevel.ADMIN_ONLY
        )
        with self.assertRaises(HealthRecord.DoesNotExist):
            create_health_record_source(
                health_record=self.health_record,
                data=self.data(),
                actor=self.actor,
            )

    def test_create_rejects_fresh_invalid_health_lifecycle(self) -> None:
        cases = (
            (Person, "archived_at", timezone.now()),
            (Person, "deleted_at", timezone.now()),
            (HealthRecord, "archived_at", timezone.now()),
            (HealthRecord, "deleted_at", timezone.now()),
            (HealthRecordType, "is_active", False),
        )
        ids = {
            Person: self.person.pk,
            HealthRecord: self.health_record.pk,
            HealthRecordType: self.record_type.pk,
        }
        for model, field, value in cases:
            with self.subTest(model=model.__name__, field=field):
                model.objects.filter(pk=ids[model]).update(**{field: value})
                with self.assertRaises(HealthRecord.DoesNotExist):
                    create_health_record_source(
                        health_record=self.health_record,
                        data=self.data(),
                        actor=self.actor,
                    )
                reset = None if field.endswith("_at") else True
                model.objects.filter(pk=ids[model]).update(**{field: reset})

    def test_create_rejects_invalid_or_unavailable_source_fk(self) -> None:
        with self.assertRaises(ValidationError) as unsaved:
            create_health_record_source(
                health_record=self.health_record,
                data=self.data(source=Source()),
                actor=self.actor,
            )
        self.assertEqual(
            unsaved.exception.error_dict["source"][0].code,
            "source_unsaved",
        )

        stale = Source.objects.create(
            source_type=self.source_type,
            title="Stale source",
        )
        stale_pk = stale.pk
        stale.delete()
        stale.pk = stale_pk
        with self.assertRaises(Source.DoesNotExist):
            create_health_record_source(
                health_record=self.health_record,
                data=self.data(source=stale),
                actor=self.actor,
            )

        for change in (
            {"archived_at": timezone.now()},
            {"deleted_at": timezone.now()},
            {"access_level": AccessLevel.ADMIN_ONLY},
        ):
            with self.subTest(change=change):
                values = {
                    "archived_at": None,
                    "deleted_at": None,
                    "access_level": AccessLevel.PUBLIC,
                }
                values.update(change)
                Source.objects.filter(pk=self.source.pk).update(**values)
                with self.assertRaises(Source.DoesNotExist):
                    create_health_record_source(
                        health_record=self.health_record,
                        data=self.data(),
                        actor=self.actor,
                    )

    def test_source_role_must_be_fresh_and_active_for_create_and_update(
        self,
    ) -> None:
        inactive = SourceRole.objects.create(
            code="inactive",
            name="Neaktivní",
            is_active=False,
        )
        for role in (SourceRole(), inactive):
            with self.subTest(role=role):
                with self.assertRaises(ValidationError):
                    create_health_record_source(
                        health_record=self.health_record,
                        data=self.data(role=role),
                        actor=self.actor,
                    )

        link = create_health_record_source(
            health_record=self.health_record,
            data=self.data(),
            actor=self.actor,
        )
        SourceRole.objects.filter(pk=self.role.pk).update(is_active=False)
        with self.assertRaises(ValidationError) as error:
            update_health_record_source(
                link=link,
                health_record=self.health_record,
                data=self.data(),
                actor=self.actor,
            )
        self.assertEqual(
            error.exception.error_dict["role"][0].code,
            "role_inactive",
        )

    def test_update_requires_current_visible_link_and_source(self) -> None:
        link = create_health_record_source(
            health_record=self.health_record,
            data=self.data(),
            actor=self.actor,
        )
        for change in (
            {"archived_at": timezone.now()},
            {"deleted_at": timezone.now()},
            {"access_level": AccessLevel.ADMIN_ONLY},
        ):
            with self.subTest(link_change=change):
                values = {
                    "archived_at": None,
                    "deleted_at": None,
                    "access_level": AccessLevel.RESTRICTED,
                }
                values.update(change)
                HealthRecordSource.objects.filter(pk=link.pk).update(**values)
                with self.assertRaises(HealthRecordSource.DoesNotExist):
                    update_health_record_source(
                        link=link,
                        health_record=self.health_record,
                        data=self.data(),
                        actor=self.actor,
                    )

        HealthRecordSource.objects.filter(pk=link.pk).update(
            archived_at=None,
            deleted_at=None,
            access_level=AccessLevel.RESTRICTED,
        )
        for change in (
            {"archived_at": timezone.now()},
            {"deleted_at": timezone.now()},
            {"access_level": AccessLevel.ADMIN_ONLY},
        ):
            with self.subTest(source_change=change):
                values = {
                    "archived_at": None,
                    "deleted_at": None,
                    "access_level": AccessLevel.PUBLIC,
                }
                values.update(change)
                Source.objects.filter(pk=self.source.pk).update(**values)
                with self.assertRaises(HealthRecordSource.DoesNotExist):
                    update_health_record_source(
                        link=link,
                        health_record=self.health_record,
                        data=self.data(),
                        actor=self.actor,
                    )

    def test_shared_source_and_known_ids_do_not_bypass_health_policy(self) -> None:
        visible_link = create_health_record_source(
            health_record=self.health_record,
            data=self.data(),
            actor=self.actor,
        )
        hidden_record = HealthRecord.objects.create(
            person=self.person,
            record_type=self.record_type,
            title="Skrytý",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        hidden_link = HealthRecordSource.objects.create(
            health_record=hidden_record,
            source=self.source,
            role=self.role,
            support_strength=SourceSupport.CONFIRMS,
            access_level=AccessLevel.PUBLIC,
        )
        with self.assertRaises(HealthRecord.DoesNotExist):
            create_health_record_source(
                health_record=hidden_record,
                data=self.data(access_level=AccessLevel.PUBLIC),
                actor=self.actor,
            )
        with self.assertRaises(HealthRecordSource.DoesNotExist):
            update_health_record_source(
                link=HealthRecordSource(pk=hidden_link.pk),
                health_record=self.health_record,
                data=self.data(),
                actor=self.actor,
            )
        with self.assertRaises(HealthRecord.DoesNotExist):
            update_health_record_source(
                link=visible_link,
                health_record=hidden_record,
                data=self.data(cited_part="Únik"),
                actor=self.actor,
            )
        visible_link.refresh_from_db()
        self.assertEqual(visible_link.cited_part, "strana 2")

    def test_write_services_use_central_health_and_link_visibility(self) -> None:
        with patch(
            "materials.source_services.get_health_record_visibility_filter",
            wraps=get_health_record_visibility_filter,
        ) as health_policy:
            link = create_health_record_source(
                health_record=self.health_record,
                data=self.data(),
                actor=self.actor,
            )
        health_policy.assert_called_once_with(actor=self.actor)

        with (
            patch(
                "materials.source_services._visible_health_record_source_links",
                wraps=source_services._visible_health_record_source_links,
            ) as link_policy,
            patch(
                "materials.source_services.get_health_record_visibility_filter",
                wraps=get_health_record_visibility_filter,
            ) as target_policy,
        ):
            update_health_record_source(
                link=link,
                health_record=self.health_record,
                data=self.data(cited_part="Policy"),
                actor=self.actor,
            )
        link_policy.assert_called_once_with(actor=self.actor)
        target_policy.assert_called_once_with(actor=self.actor)

    def test_update_rejects_unavailable_proposed_source_atomically(self) -> None:
        link = create_health_record_source(
            health_record=self.health_record,
            data=self.data(),
            actor=self.actor,
        )
        replacement = Source.objects.create(
            source_type=self.source_type,
            title="Náhradní zdroj",
        )
        changes = (
            {"archived_at": timezone.now()},
            {"deleted_at": timezone.now()},
            {"access_level": AccessLevel.ADMIN_ONLY},
        )
        for change in changes:
            with self.subTest(change=change):
                values = {
                    "archived_at": None,
                    "deleted_at": None,
                    "access_level": AccessLevel.PUBLIC,
                }
                values.update(change)
                Source.objects.filter(pk=replacement.pk).update(**values)
                with self.assertRaises(Source.DoesNotExist):
                    update_health_record_source(
                        link=link,
                        health_record=self.health_record,
                        data=self.data(
                            source=replacement,
                            cited_part="Nesmí se uložit",
                        ),
                        actor=self.actor,
                    )

        stale = Source.objects.create(
            source_type=self.source_type,
            title="Smazaný zdroj",
        )
        stale_pk = stale.pk
        stale.delete()
        stale.pk = stale_pk
        with self.assertRaises(Source.DoesNotExist):
            update_health_record_source(
                link=link,
                health_record=self.health_record,
                data=self.data(
                    source=stale,
                    cited_part="Nesmí se uložit",
                ),
                actor=self.actor,
            )

        link.refresh_from_db()
        self.assertEqual(link.source_id, self.source.pk)
        self.assertEqual(link.cited_part, "strana 2")

    def test_update_preserves_authorship_and_lifecycle_metadata(self) -> None:
        link = create_health_record_source(
            health_record=self.health_record,
            data=self.data(),
            actor=self.actor,
        )
        other = self.user(
            "other-source-writer",
            "accounts.view_restricted_content",
            "materials.change_healthrecordsource",
        )
        HealthRecordSource.objects.filter(pk=link.pk).update(
            archived_by=self.actor,
            archive_reason="Historie",
            deleted_by=self.actor,
            deletion_reason="Historie smazání",
        )
        updated = update_health_record_source(
            link=link,
            health_record=self.health_record,
            data=self.data(cited_part="Aktualizováno"),
            actor=other,
        )
        self.assertEqual(updated.created_by_id, self.actor.pk)
        self.assertIsNone(updated.archived_at)
        self.assertEqual(updated.archived_by_id, self.actor.pk)
        self.assertEqual(updated.archive_reason, "Historie")
        self.assertIsNone(updated.deleted_at)
        self.assertEqual(updated.deleted_by_id, self.actor.pk)
        self.assertEqual(updated.deletion_reason, "Historie smazání")

    def test_requested_link_access_is_checked_and_write_is_atomic(self) -> None:
        with self.assertRaises(PermissionDenied):
            create_health_record_source(
                health_record=self.health_record,
                data=self.data(access_level=AccessLevel.ADMIN_ONLY),
                actor=self.actor,
            )
        self.assertFalse(HealthRecordSource.objects.exists())

        link = create_health_record_source(
            health_record=self.health_record,
            data=self.data(),
            actor=self.actor,
        )
        with self.assertRaises(PermissionDenied):
            update_health_record_source(
                link=link,
                health_record=self.health_record,
                data=self.data(
                    cited_part="Nesmí se uložit",
                    access_level=AccessLevel.ADMIN_ONLY,
                ),
                actor=self.actor,
            )
        link.refresh_from_db()
        self.assertEqual(link.cited_part, "strana 2")
        self.assertEqual(link.access_level, AccessLevel.RESTRICTED)

        HealthRecord.objects.filter(pk=self.health_record.pk).update(
            archived_at=None
        )
        HealthRecordSource.objects.filter(pk=link.pk).update(
            deleted_at=timezone.now()
        )
        with self.assertRaises(HealthRecordSource.DoesNotExist):
            update_health_record_source(
                link=link,
                health_record=self.health_record,
                data=self.data(),
                actor=self.actor,
            )


class HealthRecordSourceSelectorTests(TestCase):
    def setUp(self) -> None:
        self.person = Person.objects.create(first_name="Anna")
        self.record_type = HealthRecordType.objects.create(
            code="active",
            name="Aktivní",
        )
        self.health_record = HealthRecord.objects.create(
            person=self.person,
            record_type=self.record_type,
            title="Zdravotní záznam",
        )
        self.source_type = SourceType.objects.create(
            code="archive",
            name="Archiv",
        )
        self.role = SourceRole.objects.create(code="evidence", name="Doklad")
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

    def source(self, key: str, **changes: object) -> Source:
        values = {
            "source_type": self.source_type,
            "title": key,
        }
        values.update(changes)
        return Source.objects.create(**values)

    def link(
        self,
        key: str,
        *,
        health_record: HealthRecord | None = None,
        **changes: object,
    ) -> HealthRecordSource:
        source = changes.pop("source", None) or self.source(key)
        values = {
            "health_record": health_record or self.health_record,
            "source": source,
            "role": self.role,
            "support_strength": SourceSupport.CONFIRMS,
        }
        values.update(changes)
        return HealthRecordSource.objects.create(**values)

    def visible(
        self,
        *,
        health_record: HealthRecord | None = None,
        actor=None,
    ) -> QuerySet[HealthRecordSource]:
        return get_visible_health_record_source_links(
            health_record=health_record or self.health_record,
            actor=self.actor if actor is None else actor,
        )

    def test_available_source_of_available_record_is_returned(self) -> None:
        available = self.link("Dostupný")
        result = self.visible()
        self.assertIsInstance(result, QuerySet)
        self.assertEqual(list(result), [available])

    def test_health_target_always_uses_central_policy(self) -> None:
        visible = self.link("Viditelný")
        with patch(
            "materials.selectors.get_health_record_visibility_filter",
            wraps=get_health_record_visibility_filter,
        ) as health_policy:
            self.assertEqual(list(self.visible()), [visible])
        self.assertEqual(health_policy.call_count, 1)

    def test_person_and_record_access_cannot_be_bypassed(self) -> None:
        self.link("Chráněný")
        Person.objects.filter(pk=self.person.pk).update(
            access_level=AccessLevel.ADMIN_ONLY
        )
        with self.assertRaises(HealthRecord.DoesNotExist):
            self.visible()

    def test_actor_matrix_matches_central_health_visibility(self) -> None:
        restricted_link = self.link("Restricted")
        ordinary = self.user("ordinary")
        inactive = self.user(
            "inactive",
            "view_restricted_content",
            is_active=False,
        )
        admin = self.user("admin", "view_admin_only_content")
        superuser = self.user("matrix-superuser", is_superuser=True)

        for actor in (AnonymousUser(), ordinary, inactive, admin):
            with self.subTest(actor=actor):
                with self.assertRaises(HealthRecord.DoesNotExist):
                    self.visible(actor=actor)

        self.assertEqual(list(self.visible()), [restricted_link])
        self.assertEqual(list(self.visible(actor=superuser)), [restricted_link])

        admin_record = HealthRecord.objects.create(
            person=self.person,
            record_type=self.record_type,
            title="Admin only",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        admin_link = self.link("Admin link", health_record=admin_record)
        with self.assertRaises(HealthRecord.DoesNotExist):
            self.visible(health_record=admin_record)
        self.assertEqual(
            list(self.visible(health_record=admin_record, actor=admin)),
            [admin_link],
        )
        self.assertEqual(
            list(self.visible(health_record=admin_record, actor=superuser)),
            [admin_link],
        )

        Person.objects.filter(pk=self.person.pk).update(
            access_level=AccessLevel.PUBLIC
        )
        HealthRecord.objects.filter(pk=self.health_record.pk).update(
            access_level=AccessLevel.ADMIN_ONLY
        )
        with self.assertRaises(HealthRecord.DoesNotExist):
            self.visible()

    def test_health_lifecycle_and_type_are_fail_closed(self) -> None:
        self.link("Lifecycle")
        superuser = self.user("superuser", is_superuser=True)
        cases = (
            (Person, self.person.pk, "archived_at"),
            (Person, self.person.pk, "deleted_at"),
            (HealthRecord, self.health_record.pk, "archived_at"),
            (HealthRecord, self.health_record.pk, "deleted_at"),
        )
        for model, object_id, field in cases:
            model.objects.filter(pk=object_id).update(**{field: timezone.now()})
            with self.subTest(model=model.__name__, field=field):
                with self.assertRaises(HealthRecord.DoesNotExist):
                    self.visible(actor=superuser)
            model.objects.filter(pk=object_id).update(**{field: None})

        HealthRecordType.objects.filter(pk=self.record_type.pk).update(
            is_active=False
        )
        with self.assertRaises(HealthRecord.DoesNotExist):
            self.visible(actor=superuser)

    def test_link_and_source_must_be_visible_and_active(self) -> None:
        available = self.link("Dostupný")
        self.link("Archivovaná vazba", archived_at=timezone.now())
        self.link("Odstraněná vazba", deleted_at=timezone.now())
        self.link("Skrytá vazba", access_level=AccessLevel.ADMIN_ONLY)
        self.link(
            "Archivovaný zdroj",
            source=self.source("Archivovaný", archived_at=timezone.now()),
        )
        self.link(
            "Odstraněný zdroj",
            source=self.source("Odstraněný", deleted_at=timezone.now()),
        )
        self.link(
            "Skrytý zdroj",
            source=self.source(
                "Skrytý",
                access_level=AccessLevel.ADMIN_ONLY,
            ),
        )
        self.assertEqual(list(self.visible()), [available])

    def test_known_source_and_link_ids_do_not_bypass_health_policy(self) -> None:
        hidden_record = HealthRecord.objects.create(
            person=self.person,
            record_type=self.record_type,
            title="Skrytý",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        shared = self.source("Sdílený")
        hidden_link = self.link(
            "Skrytý link",
            health_record=hidden_record,
            source=shared,
        )
        visible_link = self.link("Viditelný link", source=shared)
        hidden_same_record_link = self.link(
            "Skrytý link stejného záznamu",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        hidden_same_record_source_link = self.link(
            "Skrytý zdroj stejného záznamu",
            source=self.source(
                "Skrytý zdroj stejného záznamu",
                access_level=AccessLevel.ADMIN_ONLY,
            ),
        )

        self.assertIsNotNone(hidden_link.pk)
        self.assertIsNotNone(hidden_link.source_id)
        self.assertEqual(list(self.visible()), [visible_link])
        self.assertEqual(list(self.visible().filter(pk=hidden_link.pk)), [])
        self.assertEqual(
            list(self.visible().filter(pk=hidden_same_record_link.pk)),
            [],
        )
        self.assertEqual(
            list(
                self.visible().filter(
                    source_id=hidden_same_record_source_link.source_id
                )
            ),
            [],
        )
        with self.assertRaises(HealthRecord.DoesNotExist):
            self.visible(health_record=hidden_record)

    def test_inactive_role_and_source_type_do_not_hide_history(self) -> None:
        visible = self.link("Historický")
        SourceRole.objects.filter(pk=self.role.pk).update(is_active=False)
        SourceType.objects.filter(pk=self.source_type.pk).update(is_active=False)
        self.assertEqual(list(self.visible()), [visible])

    def test_lazy_result_rechecks_every_visibility_layer(self) -> None:
        mutations = (
            (Person, "person", {"access_level": AccessLevel.ADMIN_ONLY}),
            (Person, "person", {"archived_at": timezone.now()}),
            (Person, "person", {"deleted_at": timezone.now()}),
            (HealthRecord, "record", {"access_level": AccessLevel.ADMIN_ONLY}),
            (HealthRecord, "record", {"archived_at": timezone.now()}),
            (HealthRecord, "record", {"deleted_at": timezone.now()}),
            (HealthRecordType, "record_type", {"is_active": False}),
            (HealthRecordSource, "link", {"access_level": AccessLevel.ADMIN_ONLY}),
            (HealthRecordSource, "link", {"archived_at": timezone.now()}),
            (HealthRecordSource, "link", {"deleted_at": timezone.now()}),
            (Source, "source", {"access_level": AccessLevel.ADMIN_ONLY}),
            (Source, "source", {"archived_at": timezone.now()}),
            (Source, "source", {"deleted_at": timezone.now()}),
        )
        for index, (model, target, change) in enumerate(mutations):
            person = Person.objects.create(first_name=f"Fresh {index}")
            record_type = HealthRecordType.objects.create(
                code=f"fresh-source-{index}",
                name=f"Fresh {index}",
            )
            record = HealthRecord.objects.create(
                person=person,
                record_type=record_type,
                title=f"Fresh {index}",
            )
            source = self.source(f"Fresh source {index}")
            link = HealthRecordSource.objects.create(
                health_record=record,
                source=source,
                role=self.role,
                support_strength=SourceSupport.CONFIRMS,
            )
            queryset = self.visible(health_record=record)
            targets = {
                "person": person,
                "record_type": record_type,
                "record": record,
                "link": link,
                "source": source,
            }
            model.objects.filter(pk=targets[target].pk).update(**change)
            with self.subTest(model=model.__name__, change=change):
                self.assertEqual(list(queryset), [])

    def test_result_is_ordered_and_preloaded_without_n_plus_one(self) -> None:
        link_author = self.user("link-author")
        record_author = self.user("record-author")
        source_author = self.user("source-author")
        place = Place.objects.create(name="Praha", normalized_name="praha")
        HealthRecord.objects.filter(pk=self.health_record.pk).update(
            place=place,
            created_by=record_author,
        )
        later_role = SourceRole.objects.create(
            code="later",
            name="Později",
            sort_order=20,
        )
        later = self.link(
            "Pozdější",
            role=later_role,
            created_by=link_author,
            source=self.source("Pozdější", created_by=source_author),
        )
        earlier = self.link(
            "Dřívější",
            created_by=link_author,
            source=self.source("Dřívější", created_by=source_author),
        )
        queryset = self.visible()

        with CaptureQueriesContext(connection) as queries:
            result = list(queryset)
            for link in result:
                str(link.health_record.person)
                str(link.health_record.record_type)
                str(link.health_record.place)
                link.health_record.created_by.username
                str(link.source.source_type)
                link.source.created_by.username
                str(link.role)
                link.created_by.username

        self.assertEqual(result, [earlier, later])
        self.assertEqual(len(queries), 1)

    def test_invalid_record_and_actor_use_stable_errors(self) -> None:
        with self.assertRaises(ValidationError) as unsaved:
            get_visible_health_record_source_links(
                health_record=HealthRecord(),
                actor=self.actor,
            )
        self.assertEqual(
            unsaved.exception.error_dict["health_record"][0].code,
            "health_record_unsaved",
        )

        missing = HealthRecord.objects.create(
            person=self.person,
            record_type=self.record_type,
            title="Chybějící",
        )
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk
        with self.assertRaises(ValidationError) as missing_error:
            get_visible_health_record_source_links(
                health_record=missing,
                actor=self.actor,
            )
        self.assertEqual(
            missing_error.exception.error_dict["health_record"][0].code,
            "health_record_unsaved",
        )

        with self.assertRaises(ValidationError) as invalid_actor:
            get_visible_health_record_source_links(
                health_record=self.health_record,
                actor=None,
            )
        self.assertEqual(
            invalid_actor.exception.error_dict["actor"][0].code,
            "actor_invalid",
        )


class HealthRecordSourceMigrationTests(TestCase):
    migration = import_module("materials.migrations.0008_health_record_source")

    def test_migration_is_single_structural_model_addition(self) -> None:
        self.assertEqual(
            self.migration.Migration.dependencies,
            [
                ("health", "0002_health_records"),
                ("materials", "0007_health_record_attachment"),
                migrations.swappable_dependency(settings.AUTH_USER_MODEL),
            ],
        )
        self.assertEqual(len(self.migration.Migration.operations), 1)
        operation = self.migration.Migration.operations[0]
        self.assertIsInstance(operation, migrations.CreateModel)
        self.assertEqual(operation.name, "HealthRecordSource")

    def test_table_exists(self) -> None:
        self.assertIn(
            HealthRecordSource._meta.db_table,
            connection.introspection.table_names(),
        )

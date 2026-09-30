from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from common.choices import AccessLevel
from people.models import Person

from .models import HealthRecord, HealthRecordType
from .use_cases import (
    get_soft_deleted_health_record_for_management,
    list_health_records,
    list_soft_deleted_health_records,
)


class SoftDeletedHealthRecordManagementSelectorTests(TestCase):
    def setUp(self) -> None:
        self.person = Person.objects.create(
            first_name="Anna",
            access_level=AccessLevel.PUBLIC,
        )
        self.other_person = Person.objects.create(
            first_name="Jiná",
            access_level=AccessLevel.PUBLIC,
        )
        self.record_type = HealthRecordType.objects.create(
            code="checkup",
            name="Preventivní péče",
        )
        now = timezone.now()
        self.active = self.record("Aktivní")
        self.deleted = self.record("Odstraněný", deleted_at=now)
        self.admin_deleted = self.record(
            "Skrytý administrátorský",
            access_level=AccessLevel.ADMIN_ONLY,
            deleted_at=now,
        )
        self.archived = self.record("Archivovaný", archived_at=now)
        self.combined = self.record(
            "Kombinovaný",
            archived_at=now,
            deleted_at=now,
        )
        self.other = self.record(
            "Cizí",
            person=self.other_person,
            deleted_at=now,
        )
        self.actor = self.user(
            "manager",
            ("health", "delete_healthrecord"),
            ("accounts", "view_restricted_content"),
        )

    def record(self, title: str, **values: object) -> HealthRecord:
        return HealthRecord.objects.create(
            person=values.pop("person", self.person),
            record_type=values.pop("record_type", self.record_type),
            title=title,
            access_level=values.pop("access_level", AccessLevel.RESTRICTED),
            **values,
        )

    @staticmethod
    def user(username: str, *permissions, **values: object):
        actor = get_user_model().objects.create_user(
            username=username,
            password="test-password",
            **values,
        )
        for app_label, codename in permissions:
            actor.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label=app_label,
                    codename=codename,
                )
            )
        return actor

    def test_list_is_person_scoped_deleted_only_and_fail_closed_by_access(
        self,
    ) -> None:
        records = list(
            list_soft_deleted_health_records(
                person=self.person,
                actor=self.actor,
            )
        )

        self.assertEqual(records, [self.deleted])
        self.assertNotIn(
            self.deleted,
            list_health_records(person=self.person, actor=self.actor),
        )

    def test_management_requires_active_permission_not_staff_flag(self) -> None:
        actors = (
            self.user(
                "read-only",
                ("accounts", "view_restricted_content"),
            ),
            self.user(
                "inactive",
                ("health", "delete_healthrecord"),
                ("accounts", "view_restricted_content"),
                is_active=False,
            ),
            self.user("staff", is_staff=True),
        )

        for actor in actors:
            with self.subTest(actor=actor.username):
                with self.assertRaises(PermissionDenied):
                    list_soft_deleted_health_records(
                        person=self.person,
                        actor=actor,
                    )

    def test_active_superuser_uses_central_content_policy(self) -> None:
        superuser = self.user("superuser", is_superuser=True)

        self.assertEqual(
            list(
                list_soft_deleted_health_records(
                    person=self.person,
                    actor=superuser,
                )
            ),
            [self.deleted, self.admin_deleted],
        )

    def test_loader_rejects_active_archived_combined_hidden_and_foreign(
        self,
    ) -> None:
        for record in (
            self.active,
            self.archived,
            self.combined,
            self.admin_deleted,
            self.other,
        ):
            with self.subTest(record=record.title):
                with self.assertRaises(HealthRecord.DoesNotExist):
                    get_soft_deleted_health_record_for_management(
                        health_record_id=record.pk,
                        person=self.person,
                        actor=self.actor,
                    )

    def test_inactive_type_and_person_lifecycle_fail_closed(self) -> None:
        self.record_type.is_active = False
        self.record_type.save(update_fields=("is_active",))
        self.assertEqual(
            list(
                list_soft_deleted_health_records(
                    person=self.person,
                    actor=self.actor,
                )
            ),
            [],
        )
        self.record_type.is_active = True
        self.record_type.save(update_fields=("is_active",))

        for field in ("archived_at", "deleted_at"):
            setattr(self.person, field, timezone.now())
            self.person.save(update_fields=(field,))
            with self.subTest(field=field):
                with self.assertRaises(Person.DoesNotExist):
                    list_soft_deleted_health_records(
                        person=self.person,
                        actor=self.actor,
                    )
            setattr(self.person, field, None)
            self.person.save(update_fields=(field,))

    def test_deleted_list_query_profile_is_constant_and_materials_free(
        self,
    ) -> None:
        def query_count() -> tuple[int, tuple[str, ...]]:
            with CaptureQueriesContext(connection) as captured:
                records = list(
                    list_soft_deleted_health_records(
                        person=self.person,
                        actor=self.actor,
                    )
                )
                tuple(record.record_type.name for record in records)
            return len(captured), tuple(query["sql"] for query in captured)

        base_count, _ = query_count()
        for index in range(3):
            self.record(f"Odstraněný {index}", deleted_at=timezone.now())
        expanded_count, sql = query_count()

        self.assertEqual(expanded_count, base_count)
        self.assertFalse(
            any(
                "materials_healthrecordattachment" in query.lower()
                or "materials_healthrecordsource" in query.lower()
                for query in sql
            )
        )

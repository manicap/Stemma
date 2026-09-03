from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from common.choices import AccessLevel
from people.models import Person
from places.models import Place

from . import selectors
from .models import HealthRecord, HealthRecordType
from .permissions import get_health_record_visibility_filter
from .selectors import (
    get_visible_health_record,
    get_visible_health_records,
)


class HealthRecordSelectorApiTests(SimpleTestCase):
    def test_public_api_is_exact(self) -> None:
        self.assertEqual(
            selectors.__all__,
            (
                "get_visible_health_record",
                "get_visible_health_records",
            ),
        )


class HealthRecordSelectorTests(TestCase):
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

    def create_user(self, username: str, *codenames: str, **values):
        actor = get_user_model().objects.create_user(
            username=username,
            **values,
        )
        for codename in codenames:
            actor.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label="accounts",
                    content_type__model="user",
                    codename=codename,
                )
            )
        return actor

    def create_record(self, **values) -> HealthRecord:
        defaults = {
            "person": self.person,
            "record_type": self.active_type,
            "title": "Záznam",
            "access_level": AccessLevel.RESTRICTED,
        }
        defaults.update(values)
        return HealthRecord.objects.create(**defaults)

    def ids(self, actor, person=None) -> set[int]:
        return set(
            get_visible_health_records(
                person=person or self.person,
                actor=actor,
            ).values_list("pk", flat=True)
        )

    def test_different_actors_see_record_access_not_only_person_access(self) -> None:
        restricted_record = self.create_record()
        admin_record = self.create_record(access_level=AccessLevel.ADMIN_ONLY)
        ordinary = self.create_user("ordinary")
        restricted = self.create_user(
            "restricted",
            "view_restricted_content",
        )
        admin = self.create_user("admin", "view_admin_only_content")
        superuser = self.create_user("superuser", is_superuser=True)

        self.assertEqual(self.ids(AnonymousUser()), set())
        self.assertEqual(self.ids(ordinary), set())
        self.assertEqual(self.ids(restricted), {restricted_record.pk})
        self.assertEqual(self.ids(admin), {admin_record.pk})
        self.assertEqual(
            self.ids(superuser),
            {restricted_record.pk, admin_record.pk},
        )

    def test_record_and_type_lifecycle_are_fail_closed(self) -> None:
        visible = self.create_record(title="Viditelný")
        self.create_record(title="Archivovaný", archived_at=timezone.now())
        self.create_record(title="Odstraněný", deleted_at=timezone.now())
        self.create_record(
            title="Neaktivní typ",
            record_type=self.inactive_type,
        )
        actor = self.create_user("reader", "view_restricted_content")

        self.assertEqual(self.ids(actor), {visible.pk})

    def test_inaccessible_archived_and_deleted_people_return_no_records(self) -> None:
        actor = self.create_user("reader", "view_restricted_content")
        hidden = Person.objects.create(
            first_name="Skrytá",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        archived = Person.objects.create(
            first_name="Archivovaná",
            archived_at=timezone.now(),
        )
        deleted = Person.objects.create(
            first_name="Odstraněná",
            deleted_at=timezone.now(),
        )
        for person in (hidden, archived, deleted):
            self.create_record(person=person)
            with self.subTest(person=person.pk):
                self.assertEqual(self.ids(actor, person), set())

        superuser = self.create_user("lifecycle-superuser", is_superuser=True)
        for person in (archived, deleted):
            record = person.health_records.get()
            with self.subTest(superuser_person=person.pk):
                self.assertEqual(self.ids(superuser, person), set())
                with self.assertRaises(HealthRecord.DoesNotExist):
                    get_visible_health_record(
                        health_record_id=record.pk,
                        actor=superuser,
                    )

    def test_collection_and_detail_have_identical_visibility(self) -> None:
        visible = self.create_record(title="Viditelný")
        hidden = self.create_record(access_level=AccessLevel.ADMIN_ONLY)
        actor = self.create_user("reader", "view_restricted_content")

        collection_ids = self.ids(actor)
        self.assertEqual(collection_ids, {visible.pk})
        self.assertEqual(
            get_visible_health_record(
                health_record_id=visible.pk,
                actor=actor,
            ).pk,
            visible.pk,
        )
        with self.assertRaises(HealthRecord.DoesNotExist):
            get_visible_health_record(
                health_record_id=hidden.pk,
                actor=actor,
            )

    def test_direct_id_cannot_bypass_lifecycle_or_type_policy(self) -> None:
        actor = self.create_user("reader", "view_restricted_content")
        records = (
            self.create_record(archived_at=timezone.now()),
            self.create_record(deleted_at=timezone.now()),
            self.create_record(record_type=self.inactive_type),
        )
        for record in records:
            with self.subTest(record=record.pk):
                with self.assertRaises(HealthRecord.DoesNotExist):
                    get_visible_health_record(
                        health_record_id=record.pk,
                        actor=actor,
                    )

    def test_missing_record_is_indistinguishable_from_hidden_record(self) -> None:
        hidden = self.create_record(access_level=AccessLevel.ADMIN_ONLY)
        actor = self.create_user("reader", "view_restricted_content")
        for record_id in (hidden.pk, hidden.pk + 1000):
            with self.subTest(record_id=record_id):
                with self.assertRaises(HealthRecord.DoesNotExist):
                    get_visible_health_record(
                        health_record_id=record_id,
                        actor=actor,
                    )

    def test_malformed_record_id_is_also_unavailable(self) -> None:
        actor = self.create_user("reader", "view_restricted_content")
        self.create_record()
        for record_id in (
            None,
            "not-an-id",
            True,
            float("inf"),
            2**100,
        ):
            with self.subTest(record_id=record_id):
                with self.assertRaises(HealthRecord.DoesNotExist):
                    get_visible_health_record(
                        health_record_id=record_id,
                        actor=actor,
                    )

    def test_both_public_selectors_use_central_health_policy(self) -> None:
        record = self.create_record()
        actor = self.create_user("reader", "view_restricted_content")
        with patch(
            "health.selectors.get_health_record_visibility_filter",
            wraps=get_health_record_visibility_filter,
        ) as policy:
            list(get_visible_health_records(person=self.person, actor=actor))
            get_visible_health_record(
                health_record_id=record.pk,
                actor=actor,
            )

        self.assertEqual(policy.call_count, 2)

    def test_invalid_person_and_actor_keep_central_validation(self) -> None:
        with self.assertRaises(ValidationError) as person_error:
            get_visible_health_records(person=Person(), actor=AnonymousUser())
        self.assertEqual(
            person_error.exception.error_dict["person"][0].code,
            "person_unsaved",
        )
        wrong_model = self.create_record()
        with self.assertRaises(ValidationError) as wrong_model_error:
            get_visible_health_records(
                person=wrong_model,
                actor=AnonymousUser(),
            )
        self.assertEqual(
            wrong_model_error.exception.error_dict["person"][0].code,
            "person_unsaved",
        )
        with self.assertRaises(ValidationError) as actor_error:
            get_visible_health_records(person=self.person, actor=None)
        self.assertEqual(
            actor_error.exception.error_dict["actor"][0].code,
            "actor_invalid",
        )

    def test_place_is_context_not_a_separate_visibility_layer(self) -> None:
        hidden_place = Place.objects.create(
            name="Skryté místo",
            normalized_name="skryte-misto",
            access_level=AccessLevel.ADMIN_ONLY,
            deleted_at=timezone.now(),
        )
        record = self.create_record(place=hidden_place)
        actor = self.create_user("reader", "view_restricted_content")

        self.assertEqual(self.ids(actor), {record.pk})
        self.assertEqual(
            get_visible_health_record(
                health_record_id=record.pk,
                actor=actor,
            ).place_id,
            hidden_place.pk,
        )

    def test_result_preloads_domain_context_without_n_plus_one(self) -> None:
        place = Place.objects.create(name="Praha", normalized_name="praha")
        author = self.create_user("author")
        actor = self.create_user("reader", "view_restricted_content")
        self.create_record(title="Záznam 0", place=place, created_by=author)

        def evaluated_query_count() -> int:
            with CaptureQueriesContext(connection) as queries:
                records = list(
                    get_visible_health_records(person=self.person, actor=actor)
                )
                for record in records:
                    str(record.person)
                    str(record.record_type)
                    str(record.place)
                    str(record.created_by)
            return len(queries)

        one_record_queries = evaluated_query_count()
        for index in range(1, 3):
            self.create_record(
                title=f"Záznam {index}",
                place=place,
                created_by=author,
            )

        self.assertEqual(evaluated_query_count(), one_record_queries)

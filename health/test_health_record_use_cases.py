from inspect import Parameter, signature
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from common.choices import AccessLevel
from people.models import Person

from . import use_cases
from .models import HealthRecord, HealthRecordType
from .use_cases import get_health_record_detail, list_health_records


class HealthRecordUseCaseApiTests(SimpleTestCase):
    def test_public_contract_is_exact_and_keyword_only(self) -> None:
        self.assertEqual(
            use_cases.__all__,
            ("get_health_record_detail", "list_health_records"),
        )
        for callable_object, names in (
            (list_health_records, ("person", "actor")),
            (get_health_record_detail, ("health_record_id", "actor")),
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

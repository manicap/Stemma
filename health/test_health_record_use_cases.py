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
    HealthRecordSource,
    Source,
    SourceRole,
)
from materials.services import AttachmentLinkInput
from materials.source_services import SourceLinkInput
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
                "archive_health_record",
                "create_health_record",
                "create_health_record_attachment",
                "create_health_record_source",
                "get_archived_health_record_for_management",
                "get_soft_deleted_health_record_for_management",
                "get_health_record_detail",
                "list_archived_health_records",
                "list_health_record_attachments",
                "list_health_records",
                "list_health_record_sources",
                "list_soft_deleted_health_records",
                "restore_archived_health_record",
                "restore_soft_deleted_health_record",
                "soft_delete_health_record",
                "update_health_record",
                "update_health_record_attachment",
                "update_health_record_source",
            ),
        )
        for callable_object, names in (
            (
                use_cases.archive_health_record,
                ("health_record", "person", "actor", "reason"),
            ),
            (use_cases.create_health_record, ("data", "actor")),
            (
                use_cases.create_health_record_attachment,
                ("health_record", "data", "actor"),
            ),
            (
                use_cases.create_health_record_source,
                ("health_record", "data", "actor"),
            ),
            (
                use_cases.get_archived_health_record_for_management,
                ("health_record_id", "person", "actor"),
            ),
            (
                use_cases.get_soft_deleted_health_record_for_management,
                ("health_record_id", "person", "actor"),
            ),
            (list_health_records, ("person", "actor")),
            (use_cases.list_archived_health_records, ("person", "actor")),
            (
                use_cases.list_soft_deleted_health_records,
                ("person", "actor"),
            ),
            (get_health_record_detail, ("health_record_id", "actor")),
            (
                use_cases.list_health_record_attachments,
                ("health_record", "actor"),
            ),
            (
                use_cases.list_health_record_sources,
                ("health_record", "actor"),
            ),
            (
                use_cases.restore_archived_health_record,
                ("health_record", "person", "actor"),
            ),
            (
                use_cases.restore_soft_deleted_health_record,
                ("health_record", "person", "actor"),
            ),
            (
                use_cases.soft_delete_health_record,
                ("health_record", "person", "actor", "reason"),
            ),
            (
                use_cases.update_health_record,
                ("health_record", "data", "actor"),
            ),
            (
                use_cases.update_health_record_attachment,
                ("link", "health_record", "data", "actor"),
            ),
            (
                use_cases.update_health_record_source,
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

    def test_archive_management_reads_are_exact_selector_delegations(self) -> None:
        person = Person(pk=17)
        actor = AnonymousUser()
        sentinel = HealthRecord(pk=29)
        with patch(
            "health.use_cases.list_archived_health_records_for_management",
            return_value=sentinel,
        ) as list_selector:
            list_result = use_cases.list_archived_health_records(
                person=person,
                actor=actor,
            )
        with patch(
            "health.use_cases.get_archived_record",
            return_value=sentinel,
        ) as detail_selector:
            detail_result = (
                use_cases.get_archived_health_record_for_management(
                    health_record_id=29,
                    person=person,
                    actor=actor,
                )
            )

        self.assertIs(list_result, sentinel)
        self.assertIs(detail_result, sentinel)
        list_selector.assert_called_once_with(person=person, actor=actor)
        detail_selector.assert_called_once_with(
            health_record_id=29,
            person=person,
            actor=actor,
        )

    def test_deleted_management_reads_are_exact_selector_delegations(
        self,
    ) -> None:
        person = Person(pk=17)
        actor = AnonymousUser()
        sentinel = HealthRecord(pk=29)
        with patch(
            "health.use_cases.list_soft_deleted_health_records_for_management",
            return_value=sentinel,
        ) as list_selector:
            list_result = use_cases.list_soft_deleted_health_records(
                person=person,
                actor=actor,
            )
        with patch(
            "health.use_cases.get_deleted_record",
            return_value=sentinel,
        ) as detail_selector:
            detail_result = (
                use_cases.get_soft_deleted_health_record_for_management(
                    health_record_id=29,
                    person=person,
                    actor=actor,
                )
            )

        self.assertIs(list_result, sentinel)
        self.assertIs(detail_result, sentinel)
        list_selector.assert_called_once_with(person=person, actor=actor)
        detail_selector.assert_called_once_with(
            health_record_id=29,
            person=person,
            actor=actor,
        )

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

    def test_related_read_use_cases_are_exact_lazy_selector_delegations(
        self,
    ) -> None:
        actor = AnonymousUser()
        record = HealthRecord(pk=33)
        attachment_links = HealthRecordAttachment.objects.all()
        source_links = HealthRecordSource.objects.all()

        with patch(
            "health.use_cases.get_visible_health_record_attachment_links",
            return_value=attachment_links,
        ) as attachment_selector:
            attachments = use_cases.list_health_record_attachments(
                health_record=record,
                actor=actor,
            )

        with patch(
            "health.use_cases.get_visible_health_record_source_links",
            return_value=source_links,
        ) as source_selector:
            sources = use_cases.list_health_record_sources(
                health_record=record,
                actor=actor,
            )

        self.assertIs(attachments, attachment_links)
        self.assertIs(sources, source_links)
        self.assertIsNone(attachment_links._result_cache)
        self.assertIsNone(source_links._result_cache)
        attachment_selector.assert_called_once_with(
            health_record=record,
            actor=actor,
        )
        source_selector.assert_called_once_with(
            health_record=record,
            actor=actor,
        )

    def test_related_read_use_cases_preserve_exact_selector_exceptions(
        self,
    ) -> None:
        actor = AnonymousUser()
        record = HealthRecord(pk=35)
        cases = (
            (
                "health.use_cases.get_visible_health_record_attachment_links",
                use_cases.list_health_record_attachments,
            ),
            (
                "health.use_cases.get_visible_health_record_source_links",
                use_cases.list_health_record_sources,
            ),
        )

        for target, callable_object in cases:
            unavailable = HealthRecord.DoesNotExist("unavailable")
            with self.subTest(callable=callable_object.__name__):
                with patch(target, side_effect=unavailable):
                    with self.assertRaises(HealthRecord.DoesNotExist) as raised:
                        callable_object(health_record=record, actor=actor)
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

    def test_lifecycle_writes_are_exact_service_delegations(self) -> None:
        actor = AnonymousUser()
        person = Person(pk=39)
        record = HealthRecord(pk=41)
        archived = HealthRecord(pk=43)
        restored = HealthRecord(pk=47)
        soft_deleted = HealthRecord(pk=53)
        undeleted = HealthRecord(pk=59)
        with patch(
            "health.use_cases.archive_health_record_service",
            return_value=archived,
        ) as archive_service:
            archive_result = use_cases.archive_health_record(
                health_record=record,
                person=person,
                actor=actor,
                reason="Důvod",
            )
        with patch(
            "health.use_cases.restore_archived_health_record_service",
            return_value=restored,
        ) as restore_service:
            restore_result = use_cases.restore_archived_health_record(
                health_record=archived,
                person=person,
                actor=actor,
            )
        with patch(
            "health.use_cases.soft_delete_health_record_service",
            return_value=soft_deleted,
        ) as soft_delete_service:
            soft_delete_result = use_cases.soft_delete_health_record(
                health_record=record,
                person=person,
                actor=actor,
                reason="Důvod odstranění",
            )
        with patch(
            "health.use_cases.restore_soft_deleted_service",
            return_value=undeleted,
        ) as restore_soft_deleted_service:
            restore_soft_deleted_result = (
                use_cases.restore_soft_deleted_health_record(
                    health_record=soft_deleted,
                    person=person,
                    actor=actor,
                )
            )

        self.assertIs(archive_result, archived)
        self.assertIs(restore_result, restored)
        self.assertIs(soft_delete_result, soft_deleted)
        self.assertIs(restore_soft_deleted_result, undeleted)
        archive_service.assert_called_once_with(
            health_record=record,
            person=person,
            actor=actor,
            reason="Důvod",
        )
        restore_service.assert_called_once_with(
            health_record=archived,
            person=person,
            actor=actor,
        )
        soft_delete_service.assert_called_once_with(
            health_record=record,
            person=person,
            actor=actor,
            reason="Důvod odstranění",
        )
        restore_soft_deleted_service.assert_called_once_with(
            health_record=soft_deleted,
            person=person,
            actor=actor,
        )

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
                "health.use_cases.archive_health_record_service",
                use_cases.archive_health_record,
                {
                    "health_record": record,
                    "person": Person(pk=45),
                    "actor": actor,
                },
                PermissionDenied("denied"),
            ),
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
                "health.use_cases.restore_archived_health_record_service",
                use_cases.restore_archived_health_record,
                {
                    "health_record": record,
                    "person": Person(pk=45),
                    "actor": actor,
                },
                ValidationError({"health_record": ["invalid"]}),
            ),
            (
                "health.use_cases.soft_delete_health_record_service",
                use_cases.soft_delete_health_record,
                {
                    "health_record": record,
                    "person": Person(pk=45),
                    "actor": actor,
                    "reason": "Důvod",
                },
                PermissionDenied("denied"),
            ),
            (
                "health.use_cases.restore_soft_deleted_service",
                use_cases.restore_soft_deleted_health_record,
                {
                    "health_record": record,
                    "person": Person(pk=45),
                    "actor": actor,
                },
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

    def test_source_write_use_cases_are_exact_service_delegations(self) -> None:
        actor = AnonymousUser()
        record = HealthRecord(pk=73)
        link = HealthRecordSource(pk=79)
        data = SourceLinkInput(
            source=Source(),
            role=SourceRole(),
            support_strength="confirms",
        )
        create_sentinel = HealthRecordSource(pk=83)
        update_sentinel = HealthRecordSource(pk=89)

        with patch(
            "health.use_cases.create_source_service",
            return_value=create_sentinel,
        ) as create_service:
            created = use_cases.create_health_record_source(
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
            "health.use_cases.update_source_service",
            return_value=update_sentinel,
        ) as update_service:
            updated = use_cases.update_health_record_source(
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

    def test_source_write_use_cases_preserve_exact_service_exceptions(
        self,
    ) -> None:
        actor = AnonymousUser()
        record = HealthRecord(pk=97)
        link = HealthRecordSource(pk=101)
        data = SourceLinkInput(
            source=Source(),
            role=SourceRole(),
            support_strength="confirms",
        )
        cases = (
            (
                "health.use_cases.create_source_service",
                use_cases.create_health_record_source,
                {"health_record": record, "data": data, "actor": actor},
                PermissionDenied("denied"),
            ),
            (
                "health.use_cases.update_source_service",
                use_cases.update_health_record_source,
                {
                    "link": link,
                    "health_record": record,
                    "data": data,
                    "actor": actor,
                },
                HealthRecordSource.DoesNotExist("unavailable"),
            ),
            (
                "health.use_cases.create_source_service",
                use_cases.create_health_record_source,
                {"health_record": record, "data": data, "actor": actor},
                ValidationError({"source": ["invalid"]}),
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

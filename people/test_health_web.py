from inspect import getsource
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from common.choices import AccessLevel, DatePrecision
from health.models import HealthRecord, HealthRecordType
from health.use_cases import (
    get_health_record_detail,
    list_health_record_attachments,
    list_health_record_sources,
    list_health_records,
)
from materials.choices import FileStatus, SourceSupport
from materials.models import (
    Attachment,
    AttachmentCategory,
    AttachmentRole,
    HealthRecordAttachment,
    HealthRecordSource,
    Source,
    SourceRole,
    SourceType,
)

from .models import Person
from .views import person_health, person_health_record_detail


class PersonHealthWebTests(TestCase):
    def setUp(self) -> None:
        self.person = Person.objects.create(
            first_name="Anna",
            last_name="Nováková",
            access_level=AccessLevel.PUBLIC,
        )
        self.other_person = Person.objects.create(
            first_name="Jiná",
            last_name="Osoba",
            access_level=AccessLevel.PUBLIC,
        )
        self.record_type = HealthRecordType.objects.create(
            code="checkup",
            name="Preventivní péče",
        )
        self.visible_record = HealthRecord.objects.create(
            person=self.person,
            record_type=self.record_type,
            title="Preventivní prohlídka",
            description="Pravidelná kontrola.",
            provider_name="Rodinná ordinace",
            date_precision=DatePrecision.YEAR,
            start_year=2025,
            access_level=AccessLevel.RESTRICTED,
        )
        self.hidden_record = HealthRecord.objects.create(
            person=self.person,
            record_type=self.record_type,
            title="Skrytý odborný nález",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        self.other_record = HealthRecord.objects.create(
            person=self.other_person,
            record_type=self.record_type,
            title="Záznam jiné osoby",
            access_level=AccessLevel.RESTRICTED,
        )
        self.actor = self.user("reader", "view_restricted_content")

        category = AttachmentCategory.objects.create(
            code="medical-document",
            name="Lékařský dokument",
        )
        attachment_role = AttachmentRole.objects.create(
            code="medical-evidence",
            name="Lékařská zpráva",
        )
        self.attachment = Attachment.objects.create(
            category=category,
            display_name="Zpráva z prohlídky",
            original_filename="prohlidka.pdf",
            storage_key="private/never-expose/report-2025.pdf",
            mime_type="application/pdf",
            size_bytes=2048,
            sha256="a" * 64,
            file_status=FileStatus.AVAILABLE,
            access_level=AccessLevel.RESTRICTED,
        )
        self.attachment_link = HealthRecordAttachment.objects.create(
            health_record=self.visible_record,
            attachment=self.attachment,
            role=attachment_role,
            context_description="Výsledek pravidelné kontroly.",
            access_level=AccessLevel.RESTRICTED,
        )
        pending_attachment = Attachment.objects.create(
            category=category,
            display_name="Nevydatelná příloha",
            original_filename="pending.pdf",
            storage_key="private/pending.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            sha256="b" * 64,
            file_status=FileStatus.PENDING,
            access_level=AccessLevel.RESTRICTED,
        )
        HealthRecordAttachment.objects.create(
            health_record=self.visible_record,
            attachment=pending_attachment,
            role=attachment_role,
            access_level=AccessLevel.RESTRICTED,
        )

        source_type = SourceType.objects.create(
            code="medical-register",
            name="Zdravotní dokumentace",
        )
        source_role = SourceRole.objects.create(
            code="medical-source",
            name="Dokládá záznam",
        )
        self.source = Source.objects.create(
            source_type=source_type,
            title="Karta pacienta",
            full_citation="Ambulantní záznam, rok 2025.",
            access_level=AccessLevel.RESTRICTED,
        )
        self.source_link = HealthRecordSource.objects.create(
            health_record=self.visible_record,
            source=self.source,
            role=source_role,
            support_strength=SourceSupport.CONFIRMS,
            cited_part="Kontrola 2025",
            access_level=AccessLevel.RESTRICTED,
        )
        hidden_source = Source.objects.create(
            source_type=source_type,
            title="Skrytý zdroj",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        HealthRecordSource.objects.create(
            health_record=self.visible_record,
            source=hidden_source,
            role=source_role,
            support_strength=SourceSupport.CONFIRMS,
            access_level=AccessLevel.ADMIN_ONLY,
        )

    @staticmethod
    def grant(actor, codename: str) -> None:
        actor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="accounts",
                content_type__model="user",
                codename=codename,
            )
        )

    def user(self, username: str, *permissions: str, **values: object):
        actor = get_user_model().objects.create_user(
            username=username,
            password="test-password",
            **values,
        )
        for codename in permissions:
            self.grant(actor, codename)
        return actor

    def login_actor(self, actor=None) -> None:
        self.client.force_login(actor or self.actor)

    def test_anonymous_and_staff_see_safe_empty_health_section(self) -> None:
        health_url = reverse("people:health", args=(self.person.pk,))
        anonymous_response = self.client.get(health_url)
        staff = self.user("staff", is_staff=True)
        self.login_actor(staff)
        staff_response = self.client.get(health_url)

        for response in (anonymous_response, staff_response):
            with self.subTest(response=response):
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Zdravotní záznamy")
                self.assertContains(response, "nemáte dostupné žádné")
                self.assertNotContains(response, "Preventivní prohlídka")
                self.assertNotContains(response, "Skrytý odborný nález")

    def test_inactive_actor_keeps_anonymous_visibility(self) -> None:
        inactive = self.user(
            "inactive",
            "view_restricted_content",
            is_active=False,
        )
        self.login_actor(inactive)

        response = self.client.get(
            reverse("people:health", args=(self.person.pk,))
        )

        self.assertNotContains(response, "Preventivní prohlídka")

    def test_restricted_actor_sees_only_visible_records(self) -> None:
        self.login_actor()

        response = self.client.get(
            reverse("people:health", args=(self.person.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Preventivní prohlídka")
        self.assertContains(response, "Preventivní péče")
        self.assertContains(response, "2025")
        self.assertNotContains(response, "Skrytý odborný nález")
        self.assertNotContains(response, "Záznam jiné osoby")

    def test_superuser_sees_admin_only_record(self) -> None:
        superuser = self.user("superuser", is_superuser=True)
        self.login_actor(superuser)

        response = self.client.get(
            reverse("people:health", args=(self.person.pk,))
        )

        self.assertContains(response, "Preventivní prohlídka")
        self.assertContains(response, "Skrytý odborný nález")

    def test_hidden_person_health_section_is_not_available(self) -> None:
        hidden_person = Person.objects.create(
            first_name="Skrytá",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        self.login_actor()

        response = self.client.get(
            reverse("people:health", args=(hidden_person.pk,))
        )

        self.assertEqual(response.status_code, 404)

    def test_detail_shows_only_safe_attachment_and_source_metadata(self) -> None:
        self.login_actor()

        response = self.client.get(
            reverse(
                "people:health-record-detail",
                args=(self.person.pk, self.visible_record.pk),
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Preventivní prohlídka")
        self.assertContains(response, "Pravidelná kontrola.")
        self.assertContains(response, "Zpráva z prohlídky")
        self.assertContains(response, "Výsledek pravidelné kontroly.")
        self.assertContains(response, "Karta pacienta")
        self.assertContains(response, "Kontrola 2025")
        self.assertNotContains(response, "Nevydatelná příloha")
        self.assertNotContains(response, "Skrytý zdroj")
        self.assertNotContains(response, self.attachment.storage_key)
        self.assertNotContains(response, "download")
        self.assertNotContains(response, "private/")

    def test_detail_never_uses_storage_key_as_attachment_label(self) -> None:
        storage_key = "private/never-expose/unnamed-health-file.bin"
        unnamed_attachment = Attachment.objects.create(
            category=self.attachment.category,
            display_name="",
            original_filename="",
            storage_key=storage_key,
            mime_type="application/octet-stream",
            size_bytes=1,
            sha256="d" * 64,
            file_status=FileStatus.AVAILABLE,
            access_level=AccessLevel.RESTRICTED,
        )
        HealthRecordAttachment.objects.create(
            health_record=self.visible_record,
            attachment=unnamed_attachment,
            role=self.attachment_link.role,
            access_level=AccessLevel.RESTRICTED,
        )
        self.login_actor()

        response = self.client.get(
            reverse(
                "people:health-record-detail",
                args=(self.person.pk, self.visible_record.pk),
            )
        )

        self.assertContains(response, "<strong>Příloha</strong>", html=True)
        self.assertNotContains(response, storage_key)
        self.assertNotContains(response, "private/")

    @override_settings(DEBUG=False)
    def test_hidden_missing_and_wrong_person_details_fail_closed(self) -> None:
        self.login_actor()
        hidden_response = self.client.get(
            reverse(
                "people:health-record-detail",
                args=(self.person.pk, self.hidden_record.pk),
            )
        )
        missing_response = self.client.get(
            reverse(
                "people:health-record-detail",
                args=(self.person.pk, 999_999),
            )
        )
        wrong_person_response = self.client.get(
            reverse(
                "people:health-record-detail",
                args=(self.person.pk, self.other_record.pk),
            )
        )

        self.assertEqual(hidden_response.status_code, 404)
        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(wrong_person_response.status_code, 404)
        for response in (
            hidden_response,
            missing_response,
            wrong_person_response,
        ):
            self.assertTemplateUsed(response, "404.html")
            self.assertContains(
                response,
                "neexistuje nebo k němu nemáte přístup",
                status_code=404,
            )
        self.assertNotContains(
            hidden_response,
            "Skrytý odborný nález",
            status_code=404,
        )

    @override_settings(DEBUG=False)
    def test_direct_restricted_detail_without_permission_is_fail_closed(
        self,
    ) -> None:
        ordinary = self.user("ordinary")
        self.login_actor(ordinary)
        restricted_response = self.client.get(
            reverse(
                "people:health-record-detail",
                args=(self.person.pk, self.visible_record.pk),
            )
        )
        missing_response = self.client.get(
            reverse(
                "people:health-record-detail",
                args=(self.person.pk, 999_999),
            )
        )

        self.assertEqual(restricted_response.status_code, 404)
        self.assertEqual(missing_response.status_code, 404)
        self.assertTemplateUsed(restricted_response, "404.html")
        self.assertTemplateUsed(missing_response, "404.html")
        self.assertContains(
            restricted_response,
            "neexistuje nebo k němu nemáte přístup",
            status_code=404,
        )
        self.assertNotContains(
            restricted_response,
            "Preventivní prohlídka",
            status_code=404,
        )

    @override_settings(DEBUG=False)
    def test_direct_admin_only_detail_without_permission_is_fail_closed(
        self,
    ) -> None:
        self.login_actor()
        admin_only_response = self.client.get(
            reverse(
                "people:health-record-detail",
                args=(self.person.pk, self.hidden_record.pk),
            )
        )
        missing_response = self.client.get(
            reverse(
                "people:health-record-detail",
                args=(self.person.pk, 999_999),
            )
        )

        self.assertEqual(admin_only_response.status_code, 404)
        self.assertEqual(missing_response.status_code, 404)
        self.assertTemplateUsed(admin_only_response, "404.html")
        self.assertTemplateUsed(missing_response, "404.html")
        self.assertContains(
            admin_only_response,
            "neexistuje nebo k němu nemáte přístup",
            status_code=404,
        )
        self.assertNotContains(
            admin_only_response,
            "Skrytý odborný nález",
            status_code=404,
        )

    def test_hidden_detail_does_not_load_attachments_or_sources(self) -> None:
        self.login_actor()
        with (
            patch("people.views.list_health_record_attachments") as attachments,
            patch("people.views.list_health_record_sources") as sources,
        ):
            response = self.client.get(
                reverse(
                    "people:health-record-detail",
                    args=(self.person.pk, self.hidden_record.pk),
                )
            )

        self.assertEqual(response.status_code, 404)
        attachments.assert_not_called()
        sources.assert_not_called()

    def test_inactive_and_staff_users_do_not_gain_direct_detail_access(
        self,
    ) -> None:
        actors = (
            self.user(
                "inactive-detail",
                "view_restricted_content",
                is_active=False,
            ),
            self.user("staff-detail", is_staff=True),
        )
        detail_url = reverse(
            "people:health-record-detail",
            args=(self.person.pk, self.visible_record.pk),
        )

        for actor in actors:
            with self.subTest(username=actor.username):
                self.login_actor(actor)
                response = self.client.get(detail_url)
                self.assertEqual(response.status_code, 404)
                self.assertNotContains(
                    response,
                    "Preventivní prohlídka",
                    status_code=404,
                )
                self.client.logout()

    def test_active_superuser_can_open_admin_only_detail(self) -> None:
        superuser = self.user("detail-superuser", is_superuser=True)
        self.login_actor(superuser)

        response = self.client.get(
            reverse(
                "people:health-record-detail",
                args=(self.person.pk, self.hidden_record.pk),
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Skrytý odborný nález")

    def test_full_page_and_htmx_use_existing_person_shell_contract(self) -> None:
        self.login_actor()
        health_url = reverse("people:health", args=(self.person.pk,))
        detail_url = reverse(
            "people:health-record-detail",
            args=(self.person.pk, self.visible_record.pk),
        )

        full_response = self.client.get(health_url)
        htmx_response = self.client.get(
            health_url,
            headers={"HX-Request": "true"},
        )
        detail_htmx_response = self.client.get(
            detail_url,
            headers={"HX-Request": "true"},
        )

        self.assertTemplateUsed(full_response, "people/person_shell.html")
        self.assertContains(full_response, "Seznam osob")
        self.assertTemplateUsed(
            htmx_response,
            "people/partials/person_health.html",
        )
        self.assertNotContains(htmx_response, "Seznam osob")
        self.assertTemplateUsed(
            detail_htmx_response,
            "people/partials/person_health_record.html",
        )
        self.assertNotContains(detail_htmx_response, "Seznam osob")

    def test_views_delegate_health_reads_to_application_use_cases(self) -> None:
        self.login_actor()
        with patch(
            "people.views.list_health_records",
            wraps=list_health_records,
        ) as record_list_use_case:
            list_response = self.client.get(
                reverse("people:health", args=(self.person.pk,))
            )

        self.assertEqual(list_response.status_code, 200)
        record_list_use_case.assert_called_once()
        self.assertEqual(
            record_list_use_case.call_args.kwargs["person"],
            self.person,
        )
        self.assertEqual(
            record_list_use_case.call_args.kwargs["actor"].pk,
            self.actor.pk,
        )

        with (
            patch(
                "people.views.get_health_record_detail",
                wraps=get_health_record_detail,
            ) as detail_use_case,
            patch(
                "people.views.list_health_record_attachments",
                wraps=list_health_record_attachments,
            ) as attachment_use_case,
            patch(
                "people.views.list_health_record_sources",
                wraps=list_health_record_sources,
            ) as source_use_case,
        ):
            detail_response = self.client.get(
                reverse(
                    "people:health-record-detail",
                    args=(self.person.pk, self.visible_record.pk),
                )
            )

        self.assertEqual(detail_response.status_code, 200)
        detail_use_case.assert_called_once_with(
            health_record_id=self.visible_record.pk,
            actor=detail_use_case.call_args.kwargs["actor"],
        )
        attachment_record = attachment_use_case.call_args.kwargs[
            "health_record"
        ]
        source_record = source_use_case.call_args.kwargs["health_record"]
        self.assertEqual(attachment_record.pk, self.visible_record.pk)
        self.assertIs(source_record, attachment_record)
        self.assertEqual(
            attachment_use_case.call_args.kwargs["actor"].pk,
            self.actor.pk,
        )
        self.assertEqual(
            source_use_case.call_args.kwargs["actor"].pk,
            self.actor.pk,
        )

    def test_list_does_not_load_attachment_or_source_use_cases(self) -> None:
        self.login_actor()
        with (
            patch("people.views.list_health_record_attachments") as attachments,
            patch("people.views.list_health_record_sources") as sources,
        ):
            response = self.client.get(
                reverse("people:health", args=(self.person.pk,))
            )

        self.assertEqual(response.status_code, 200)
        attachments.assert_not_called()
        sources.assert_not_called()

    def test_health_views_have_no_direct_health_or_materials_orm_path(
        self,
    ) -> None:
        source = getsource(person_health) + getsource(
            person_health_record_detail
        )

        self.assertNotIn(".objects", source)
        self.assertNotIn("health_record.attachment_links", source)
        self.assertNotIn("health_record.source_links", source)

    def test_get_requests_do_not_write_health_or_material_rows(self) -> None:
        self.login_actor()
        before = (
            HealthRecord.objects.count(),
            HealthRecordAttachment.objects.count(),
            HealthRecordSource.objects.count(),
            Attachment.objects.count(),
            Source.objects.count(),
        )

        self.client.get(reverse("people:health", args=(self.person.pk,)))
        self.client.get(
            reverse(
                "people:health-record-detail",
                args=(self.person.pk, self.visible_record.pk),
            )
        )

        self.assertEqual(
            before,
            (
                HealthRecord.objects.count(),
                HealthRecordAttachment.objects.count(),
                HealthRecordSource.objects.count(),
                Attachment.objects.count(),
                Source.objects.count(),
            ),
        )

    def test_read_views_reject_unsafe_http_methods(self) -> None:
        self.login_actor()

        self.assertEqual(
            self.client.post(
                reverse("people:health", args=(self.person.pk,))
            ).status_code,
            405,
        )
        self.assertEqual(
            self.client.post(
                reverse(
                    "people:health-record-detail",
                    args=(self.person.pk, self.visible_record.pk),
                )
            ).status_code,
            405,
        )

    def _query_count(self, url: str) -> int:
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return len(captured)

    def test_health_list_query_count_does_not_grow_with_records(self) -> None:
        self.login_actor()
        url = reverse("people:health", args=(self.person.pk,))
        baseline = self._query_count(url)
        for index in range(5):
            HealthRecord.objects.create(
                person=self.person,
                record_type=self.record_type,
                title=f"Další záznam {index}",
                access_level=AccessLevel.RESTRICTED,
            )

        self.assertEqual(self._query_count(url), baseline)

    def test_health_detail_query_count_does_not_grow_with_links(self) -> None:
        self.login_actor()
        url = reverse(
            "people:health-record-detail",
            args=(self.person.pk, self.visible_record.pk),
        )
        baseline = self._query_count(url)
        for _ in range(5):
            HealthRecordAttachment.objects.create(
                health_record=self.visible_record,
                attachment=self.attachment,
                role=self.attachment_link.role,
                access_level=AccessLevel.RESTRICTED,
            )
            HealthRecordSource.objects.create(
                health_record=self.visible_record,
                source=self.source,
                role=self.source_link.role,
                support_strength=SourceSupport.CONFIRMS,
                access_level=AccessLevel.RESTRICTED,
            )

        self.assertEqual(self._query_count(url), baseline)

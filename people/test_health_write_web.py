from inspect import getsource
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from common.choices import (
    AccessLevel,
    DatePrecision,
    DateQualifier,
    VerificationStatus,
)
from health.forms import HealthRecordForm
from health.models import HealthRecord, HealthRecordType
from health.use_cases import create_health_record, update_health_record
from materials.models import HealthRecordAttachment, HealthRecordSource
from places.models import Place

from .models import Person
from .views import person_health_record_create, person_health_record_edit


class PersonHealthWriteWebTests(TestCase):
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
        self.inactive_type = HealthRecordType.objects.create(
            code="inactive",
            name="Neaktivní typ",
            is_active=False,
        )
        self.place = Place.objects.create(
            name="Praha",
            normalized_name="praha",
            access_level=AccessLevel.PUBLIC,
        )
        self.record = HealthRecord.objects.create(
            person=self.person,
            record_type=self.record_type,
            place=self.place,
            title="Původní název",
            access_level=AccessLevel.RESTRICTED,
        )
        self.admin_record = HealthRecord.objects.create(
            person=self.person,
            record_type=self.record_type,
            title="Administrátorský záznam",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        self.actor = self.user(
            "health-editor",
            ("health", "add_healthrecord"),
            ("health", "change_healthrecord"),
            ("accounts", "view_restricted_content"),
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

    def valid_data(self, **changes: object) -> dict[str, object]:
        values: dict[str, object] = {
            "record_type": self.record_type.pk,
            "title": "Nový zdravotní záznam",
            "description": "Pravidelná kontrola.",
            "provider_name": "Rodinná ordinace",
            "note": "Interní poznámka",
            "access_level": AccessLevel.RESTRICTED,
            "verification_status": VerificationStatus.UNCONFIRMED,
            "date_precision": DatePrecision.YEAR,
            "date_qualifier": DateQualifier.NONE,
            "start_year": 2026,
            "start_month": "",
            "start_day": "",
            "end_year": "",
            "end_month": "",
            "end_day": "",
            "original_date_text": "rok 2026",
            "date_note": "Rok převzatý ze zprávy.",
        }
        values.update(changes)
        return values

    def login(self, actor=None) -> None:
        self.client.force_login(actor or self.actor)

    def test_form_exposes_only_supported_snapshot_fields(self) -> None:
        form = HealthRecordForm(actor=self.actor)

        self.assertEqual(
            tuple(form.fields),
            (
                "record_type",
                "title",
                "description",
                "provider_name",
                "note",
                "access_level",
                "verification_status",
                "date_precision",
                "date_qualifier",
                "start_year",
                "start_month",
                "start_day",
                "end_year",
                "end_month",
                "end_day",
                "original_date_text",
                "date_note",
            ),
        )
        self.assertNotIn(self.inactive_type, form.fields["record_type"].queryset)
        self.assertEqual(
            [value for value, _ in form.fields["access_level"].choices],
            [AccessLevel.RESTRICTED],
        )

    def test_full_page_and_htmx_forms_use_person_shell_contract(self) -> None:
        self.login()
        create_url = reverse(
            "people:health-record-create",
            args=(self.person.pk,),
        )
        edit_url = reverse(
            "people:health-record-edit",
            args=(self.person.pk, self.record.pk),
        )

        full_response = self.client.get(create_url)
        htmx_response = self.client.get(
            edit_url,
            headers={"HX-Request": "true"},
        )

        self.assertTemplateUsed(full_response, "people/person_shell.html")
        self.assertContains(full_response, "Přidat zdravotní záznam")
        self.assertTemplateUsed(
            htmx_response,
            "people/partials/health_record_form.html",
        )
        self.assertNotContains(htmx_response, "Seznam osob")

    def test_write_actions_are_visible_only_with_matching_permissions(self) -> None:
        health_url = reverse("people:health", args=(self.person.pk,))
        detail_url = reverse(
            "people:health-record-detail",
            args=(self.person.pk, self.record.pk),
        )
        self.login()

        allowed_list = self.client.get(health_url)
        allowed_detail = self.client.get(detail_url)

        self.assertContains(allowed_list, "Přidat zdravotní záznam")
        self.assertContains(allowed_detail, "Upravit")

        self.client.logout()
        read_only = self.user(
            "health-read-only",
            ("accounts", "view_restricted_content"),
        )
        self.login(read_only)

        denied_list = self.client.get(health_url)
        denied_detail = self.client.get(detail_url)

        self.assertNotContains(denied_list, "Přidat zdravotní záznam")
        self.assertNotContains(
            denied_detail,
            reverse(
                "people:health-record-edit",
                args=(self.person.pk, self.record.pk),
            ),
        )

    def test_create_delegates_to_use_case_and_ignores_foreign_ownership(self) -> None:
        self.login()
        url = reverse("people:health-record-create", args=(self.person.pk,))
        data = self.valid_data(
            person=self.other_person.pk,
            place=self.place.pk,
        )

        with patch(
            "people.views.create_health_record",
            wraps=create_health_record,
        ) as use_case:
            response = self.client.post(url, data)

        created = HealthRecord.objects.exclude(
            pk__in=(self.record.pk, self.admin_record.pk)
        ).get()
        self.assertRedirects(
            response,
            reverse(
                "people:health-record-detail",
                args=(self.person.pk, created.pk),
            ),
        )
        self.assertEqual(created.person, self.person)
        self.assertIsNone(created.place)
        self.assertEqual(created.created_by, self.actor)
        use_case.assert_called_once()
        self.assertEqual(use_case.call_args.kwargs["data"].person, self.person)
        self.assertIsNone(use_case.call_args.kwargs["data"].place)
        self.assertEqual(use_case.call_args.kwargs["actor"].pk, self.actor.pk)

    def test_htmx_create_returns_detail_and_pushes_canonical_url(self) -> None:
        self.login()

        response = self.client.post(
            reverse("people:health-record-create", args=(self.person.pk,)),
            self.valid_data(),
            headers={"HX-Request": "true"},
        )

        created = HealthRecord.objects.exclude(
            pk__in=(self.record.pk, self.admin_record.pk)
        ).get()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "people/partials/person_health_record.html",
        )
        self.assertEqual(
            response.headers["HX-Push-Url"],
            reverse(
                "people:health-record-detail",
                args=(self.person.pk, created.pk),
            ),
        )
        self.assertContains(response, "Zdravotní záznam byl uložen")

    def test_update_delegates_and_preserves_ownership_place_and_lifecycle(self) -> None:
        self.record.created_by = self.actor
        self.record.save(update_fields=("created_by",))
        original_created_at = self.record.created_at
        self.login()
        url = reverse(
            "people:health-record-edit",
            args=(self.person.pk, self.record.pk),
        )
        before_materials = (
            HealthRecordAttachment.objects.count(),
            HealthRecordSource.objects.count(),
        )

        with patch(
            "people.views.update_health_record",
            wraps=update_health_record,
        ) as use_case:
            response = self.client.post(
                url,
                self.valid_data(
                    person=self.other_person.pk,
                    place="",
                    archived_at="2026-01-01",
                    deleted_at="2026-01-01",
                ),
                headers={"HX-Request": "true"},
            )

        self.record.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "people/partials/person_health_record.html",
        )
        self.assertEqual(
            response.headers["HX-Push-Url"],
            reverse(
                "people:health-record-detail",
                args=(self.person.pk, self.record.pk),
            ),
        )
        self.assertContains(response, "Zdravotní záznam byl uložen")
        self.assertEqual(self.record.title, "Nový zdravotní záznam")
        self.assertEqual(self.record.person, self.person)
        self.assertEqual(self.record.place, self.place)
        self.assertEqual(self.record.created_by, self.actor)
        self.assertEqual(self.record.created_at, original_created_at)
        self.assertIsNone(self.record.archived_at)
        self.assertIsNone(self.record.deleted_at)
        self.assertEqual(
            before_materials,
            (
                HealthRecordAttachment.objects.count(),
                HealthRecordSource.objects.count(),
            ),
        )
        use_case.assert_called_once()
        self.assertEqual(use_case.call_args.kwargs["data"].person, self.person)
        self.assertEqual(use_case.call_args.kwargs["data"].place, self.place)

    def test_full_page_update_redirects_to_canonical_detail(self) -> None:
        self.login()

        response = self.client.post(
            reverse(
                "people:health-record-edit",
                args=(self.person.pk, self.record.pk),
            ),
            self.valid_data(title="Upravený záznam"),
        )

        self.assertRedirects(
            response,
            reverse(
                "people:health-record-detail",
                args=(self.person.pk, self.record.pk),
            ),
        )
        self.record.refresh_from_db()
        self.assertEqual(self.record.title, "Upravený záznam")

    def test_validation_error_keeps_submitted_form_without_writing(self) -> None:
        self.login()
        before = HealthRecord.objects.count()

        response = self.client.post(
            reverse("people:health-record-create", args=(self.person.pk,)),
            self.valid_data(title="", description=""),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(HealthRecord.objects.count(), before)
        self.assertContains(response, "Formulář se nepodařilo uložit")
        self.assertContains(response, "Rodinná ordinace")

    def test_service_validation_error_is_mapped_to_form(self) -> None:
        self.login()
        with patch(
            "people.views.create_health_record",
            side_effect=ValidationError({"title": "Neplatný název."}),
        ):
            response = self.client.post(
                reverse(
                    "people:health-record-create",
                    args=(self.person.pk,),
                ),
                self.valid_data(),
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Neplatný název")

    def test_invalid_update_preserves_record_and_related_state(self) -> None:
        self.record.created_by = self.actor
        self.record.save(update_fields=("created_by",))
        before = {
            "title": self.record.title,
            "description": self.record.description,
            "person_id": self.record.person_id,
            "place_id": self.record.place_id,
            "created_by_id": self.record.created_by_id,
            "archived_at": self.record.archived_at,
            "deleted_at": self.record.deleted_at,
            "attachments": HealthRecordAttachment.objects.count(),
            "sources": HealthRecordSource.objects.count(),
        }
        self.login()

        response = self.client.post(
            reverse(
                "people:health-record-edit",
                args=(self.person.pk, self.record.pk),
            ),
            self.valid_data(
                title="",
                description="",
                person=self.other_person.pk,
                place="",
                archived_at="2026-01-01",
                deleted_at="2026-01-01",
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Formulář se nepodařilo uložit")
        self.assertContains(response, "Rodinná ordinace")
        self.record.refresh_from_db()
        self.assertEqual(self.record.title, before["title"])
        self.assertEqual(self.record.description, before["description"])
        self.assertEqual(self.record.person_id, before["person_id"])
        self.assertEqual(self.record.place_id, before["place_id"])
        self.assertEqual(self.record.created_by_id, before["created_by_id"])
        self.assertEqual(self.record.archived_at, before["archived_at"])
        self.assertEqual(self.record.deleted_at, before["deleted_at"])
        self.assertEqual(
            HealthRecordAttachment.objects.count(),
            before["attachments"],
        )
        self.assertEqual(
            HealthRecordSource.objects.count(),
            before["sources"],
        )

    def test_anonymous_inactive_staff_and_content_only_users_cannot_create(
        self,
    ) -> None:
        actors = (
            None,
            self.user(
                "inactive",
                ("health", "add_healthrecord"),
                ("accounts", "view_restricted_content"),
                is_active=False,
            ),
            self.user("staff", is_staff=True),
            self.user(
                "content-only",
                ("accounts", "view_restricted_content"),
            ),
        )
        url = reverse("people:health-record-create", args=(self.person.pk,))

        for actor in actors:
            with self.subTest(actor=getattr(actor, "username", "anonymous")):
                if actor is not None:
                    self.login(actor)
                response = self.client.post(url, self.valid_data())
                self.assertEqual(response.status_code, 403)
                self.client.logout()

    def test_model_permission_without_health_content_access_cannot_write(
        self,
    ) -> None:
        actor = self.user(
            "model-only",
            ("health", "add_healthrecord"),
            ("health", "change_healthrecord"),
        )
        self.login(actor)

        create_response = self.client.post(
            reverse("people:health-record-create", args=(self.person.pk,)),
            self.valid_data(),
        )
        edit_response = self.client.post(
            reverse(
                "people:health-record-edit",
                args=(self.person.pk, self.record.pk),
            ),
            self.valid_data(),
        )

        self.assertEqual(create_response.status_code, 403)
        self.assertEqual(edit_response.status_code, 404)

    def test_update_denies_missing_write_permission_inactive_and_staff(self) -> None:
        actors_and_statuses = (
            (None, 404),
            (
                self.user(
                    "inactive-update",
                    ("health", "change_healthrecord"),
                    ("accounts", "view_restricted_content"),
                    is_active=False,
                ),
                404,
            ),
            (self.user("staff-update", is_staff=True), 404),
            (
                self.user(
                    "restricted-read-only",
                    ("accounts", "view_restricted_content"),
                ),
                403,
            ),
        )
        url = reverse(
            "people:health-record-edit",
            args=(self.person.pk, self.record.pk),
        )
        original_title = self.record.title

        for actor, expected_status in actors_and_statuses:
            with self.subTest(actor=getattr(actor, "username", "anonymous")):
                if actor is not None:
                    self.login(actor)
                response = self.client.post(url, self.valid_data())
                self.assertEqual(response.status_code, expected_status)
                self.record.refresh_from_db()
                self.assertEqual(self.record.title, original_title)
                self.client.logout()

    def test_admin_only_update_without_write_permission_is_denied(self) -> None:
        actor = self.user(
            "admin-read-only",
            ("accounts", "view_admin_only_content"),
        )
        self.login(actor)

        response = self.client.post(
            reverse(
                "people:health-record-edit",
                args=(self.person.pk, self.admin_record.pk),
            ),
            self.valid_data(
                title="Nesmí se uložit",
                access_level=AccessLevel.ADMIN_ONLY,
            ),
        )

        self.assertEqual(response.status_code, 403)
        self.admin_record.refresh_from_db()
        self.assertEqual(self.admin_record.title, "Administrátorský záznam")

    @override_settings(DEBUG=False)
    def test_hidden_admin_record_and_wrong_person_update_fail_closed(self) -> None:
        self.login()
        hidden_url = reverse(
            "people:health-record-edit",
            args=(self.person.pk, self.admin_record.pk),
        )
        wrong_url = reverse(
            "people:health-record-edit",
            args=(self.other_person.pk, self.record.pk),
        )

        hidden_response = self.client.get(hidden_url)
        wrong_response = self.client.get(wrong_url)

        self.assertEqual(hidden_response.status_code, 404)
        self.assertEqual(wrong_response.status_code, 404)
        self.assertNotContains(
            hidden_response,
            "Administrátorský záznam",
            status_code=404,
        )

    def test_hidden_person_create_fails_closed(self) -> None:
        hidden_person = Person.objects.create(
            first_name="Skrytá",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        self.login()

        response = self.client.get(
            reverse("people:health-record-create", args=(hidden_person.pk,))
        )

        self.assertEqual(response.status_code, 404)

    def test_active_superuser_can_create_and_edit_admin_only_record(self) -> None:
        superuser = self.user("superuser", is_superuser=True)
        self.login(superuser)

        create_response = self.client.post(
            reverse("people:health-record-create", args=(self.person.pk,)),
            self.valid_data(access_level=AccessLevel.ADMIN_ONLY),
        )
        edit_response = self.client.post(
            reverse(
                "people:health-record-edit",
                args=(self.person.pk, self.admin_record.pk),
            ),
            self.valid_data(
                title="Upravený administrátorský záznam",
                access_level=AccessLevel.ADMIN_ONLY,
            ),
        )

        self.assertEqual(create_response.status_code, 302)
        self.assertEqual(edit_response.status_code, 302)
        self.admin_record.refresh_from_db()
        self.assertEqual(
            self.admin_record.title,
            "Upravený administrátorský záznam",
        )

    def test_admin_only_content_permission_can_edit_admin_record(self) -> None:
        actor = self.user(
            "admin-content-editor",
            ("health", "change_healthrecord"),
            ("accounts", "view_admin_only_content"),
        )
        self.login(actor)

        response = self.client.post(
            reverse(
                "people:health-record-edit",
                args=(self.person.pk, self.admin_record.pk),
            ),
            self.valid_data(
                title="Upraveno s admin-only přístupem",
                access_level=AccessLevel.ADMIN_ONLY,
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.admin_record.refresh_from_db()
        self.assertEqual(
            self.admin_record.title,
            "Upraveno s admin-only přístupem",
        )

    def test_unsupported_write_methods_are_rejected(self) -> None:
        self.login()
        create_url = reverse(
            "people:health-record-create",
            args=(self.person.pk,),
        )
        edit_url = reverse(
            "people:health-record-edit",
            args=(self.person.pk, self.record.pk),
        )

        for method in (self.client.put, self.client.patch, self.client.delete):
            with self.subTest(method=method.__name__):
                self.assertEqual(method(create_url).status_code, 405)
                self.assertEqual(method(edit_url).status_code, 405)

    def test_write_views_have_no_direct_health_or_materials_orm_path(self) -> None:
        source = getsource(person_health_record_create) + getsource(
            person_health_record_edit
        )

        self.assertNotIn(".objects", source)
        self.assertNotIn("attachment_links", source)
        self.assertNotIn("source_links", source)

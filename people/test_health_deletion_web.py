from inspect import getsource
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from common.choices import AccessLevel
from health.models import HealthRecord, HealthRecordType
from health.use_cases import (
    restore_soft_deleted_health_record,
    soft_delete_health_record,
)
from materials.models import HealthRecordAttachment, HealthRecordSource

from .models import Person
from .views import (
    person_health_deleted,
    person_health_record_restore_soft_deleted,
    person_health_record_soft_delete,
)


class PersonHealthDeletionWebTests(TestCase):
    def setUp(self) -> None:
        self.person = Person.objects.create(
            first_name="Anna",
            last_name="Nováková",
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
        self.active = self.record("Aktivní záznam")
        self.admin_active = self.record(
            "Administrátorský aktivní",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        self.deleted = self.record(
            "Odstraněný záznam",
            deleted_at=now,
            deletion_reason="Duplicitní zápis",
        )
        self.admin_deleted = self.record(
            "Administrátorský odstraněný",
            access_level=AccessLevel.ADMIN_ONLY,
            deleted_at=now,
            deletion_reason="Citlivý důvod",
        )
        self.archived = self.record("Archivovaný záznam", archived_at=now)
        self.combined = self.record(
            "Kombinovaný legacy stav",
            archived_at=now,
            deleted_at=now,
        )
        self.foreign_active = self.record(
            "Cizí aktivní",
            person=self.other_person,
        )
        self.foreign_deleted = self.record(
            "Cizí odstraněný",
            person=self.other_person,
            deleted_at=now,
        )
        self.actor = self.user(
            "health-deletion-manager",
            ("health", "delete_healthrecord"),
            ("accounts", "view_restricted_content"),
        )

    def record(self, title: str, **values: object) -> HealthRecord:
        return HealthRecord.objects.create(
            person=values.pop("person", self.person),
            record_type=values.pop("record_type", self.record_type),
            title=title,
            description=f"Popis: {title}",
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

    def login(self, actor=None) -> None:
        self.client.force_login(actor or self.actor)

    def delete_url(self, record=None, person=None) -> str:
        return reverse(
            "people:health-record-soft-delete",
            args=((person or self.person).pk, (record or self.active).pk),
        )

    def restore_url(self, record=None, person=None) -> str:
        return reverse(
            "people:health-record-restore-soft-deleted",
            args=((person or self.person).pk, (record or self.deleted).pk),
        )

    def deleted_list_url(self, person=None) -> str:
        return reverse(
            "people:health-deleted",
            args=((person or self.person).pk,),
        )

    def test_delete_get_is_read_only_full_page_and_htmx(self) -> None:
        self.login()

        full = self.client.get(self.delete_url())
        htmx = self.client.get(
            self.delete_url(),
            headers={"HX-Request": "true"},
        )

        self.active.refresh_from_db()
        self.assertIsNone(self.active.deleted_at)
        self.assertTemplateUsed(full, "people/person_shell.html")
        self.assertTemplateUsed(
            htmx,
            "people/partials/health_record_soft_delete_confirm.html",
        )
        self.assertContains(full, "Důvod odstranění")
        self.assertContains(full, "nebude fyzicky smazán")

    def test_delete_post_delegates_reason_and_redirects_to_health_list(
        self,
    ) -> None:
        self.login()
        before_materials = (
            HealthRecordAttachment.objects.count(),
            HealthRecordSource.objects.count(),
        )
        with patch(
            "people.views.soft_delete_health_record",
            wraps=soft_delete_health_record,
        ) as use_case:
            response = self.client.post(
                self.delete_url(),
                {"deletion_reason": "  Chybný zápis  "},
            )

        self.assertRedirects(
            response,
            reverse("people:health", args=(self.person.pk,)),
        )
        self.active.refresh_from_db()
        self.assertEqual(self.active.deletion_reason, "Chybný zápis")
        self.assertEqual(
            before_materials,
            (
                HealthRecordAttachment.objects.count(),
                HealthRecordSource.objects.count(),
            ),
        )
        use_case.assert_called_once()
        self.assertEqual(
            use_case.call_args.kwargs["reason"],
            "  Chybný zápis  ",
        )

    def test_delete_requires_reason_and_preserves_service_error_input(
        self,
    ) -> None:
        self.login()
        missing = self.client.post(self.delete_url(), {"deletion_reason": ""})
        self.assertContains(missing, "Toto pole je třeba vyplnit")
        self.active.refresh_from_db()
        self.assertIsNone(self.active.deleted_at)

        with patch(
            "people.views.soft_delete_health_record",
            side_effect=ValidationError(
                {
                    "deletion_reason": ValidationError(
                        "Důvod odstranění zdravotního záznamu je povinný.",
                        code="health_record_deletion_reason_required",
                    )
                }
            ),
        ):
            invalid = self.client.post(
                self.delete_url(),
                {"deletion_reason": "Zachovaný vstup"},
            )
        self.assertContains(invalid, "Zachovaný vstup")
        self.assertContains(invalid, "Důvod odstranění zdravotního")
        self.active.refresh_from_db()
        self.assertIsNone(self.active.deleted_at)

    def test_delete_htmx_returns_active_list_and_canonical_url(self) -> None:
        self.login()

        response = self.client.post(
            self.delete_url(),
            {"deletion_reason": "Chybný zápis"},
            headers={"HX-Request": "true"},
        )

        self.assertTemplateUsed(response, "people/partials/person_health.html")
        self.assertEqual(
            response.headers["HX-Push-Url"],
            reverse("people:health", args=(self.person.pk,)),
        )
        self.assertNotContains(response, "Aktivní záznam")
        self.assertContains(response, "přesunut do koše")

    def test_delete_denials_and_fail_closed_targets(self) -> None:
        read_only = self.user(
            "read-only",
            ("accounts", "view_restricted_content"),
        )
        self.login(read_only)
        self.assertEqual(self.client.post(self.delete_url()).status_code, 403)

        model_only = self.user(
            "model-only",
            ("health", "delete_healthrecord"),
        )
        self.login(model_only)
        self.assertEqual(self.client.get(self.delete_url()).status_code, 404)

        actors = (
            None,
            self.user(
                "inactive",
                ("health", "delete_healthrecord"),
                ("accounts", "view_restricted_content"),
                is_active=False,
            ),
            self.user("staff", is_staff=True),
        )
        for actor in actors:
            with self.subTest(actor=getattr(actor, "username", "anonymous")):
                self.client.logout()
                if actor is not None:
                    self.login(actor)
                self.assertEqual(self.client.get(self.delete_url()).status_code, 404)

        self.login()
        hidden_urls = (
            self.delete_url(self.admin_active),
            self.delete_url(self.archived),
            self.delete_url(self.deleted),
            self.delete_url(self.combined),
            self.delete_url(self.foreign_active),
            self.delete_url(self.active, self.other_person),
            reverse(
                "people:health-record-soft-delete",
                args=(self.person.pk, 999999),
            ),
        )
        for url in hidden_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url).status_code, 404)

    def test_delete_person_lifecycle_superuser_and_csrf(self) -> None:
        self.login()
        for field in ("archived_at", "deleted_at"):
            setattr(self.person, field, timezone.now())
            self.person.save(update_fields=(field,))
            with self.subTest(field=field):
                self.assertEqual(self.client.get(self.delete_url()).status_code, 404)
            setattr(self.person, field, None)
            self.person.save(update_fields=(field,))

        superuser = self.user("delete-superuser", is_superuser=True)
        self.login(superuser)
        self.assertEqual(
            self.client.post(
                self.delete_url(self.admin_active),
                {"deletion_reason": "Důvod"},
            ).status_code,
            302,
        )

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.actor)
        self.assertEqual(
            csrf_client.post(
                self.delete_url(),
                {"deletion_reason": "Důvod"},
            ).status_code,
            403,
        )

    def test_deleted_list_is_scoped_filtered_and_materials_free(self) -> None:
        self.login()

        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(self.deleted_list_url())

        self.assertContains(response, "Odstraněný záznam")
        self.assertContains(response, "Duplicitní zápis")
        for hidden in (
            "Aktivní záznam",
            "Administrátorský odstraněný",
            "Archivovaný záznam",
            "Kombinovaný legacy stav",
            "Cizí odstraněný",
        ):
            self.assertNotContains(response, hidden)
        self.assertFalse(
            any(
                "materials_healthrecordattachment" in query["sql"].lower()
                or "materials_healthrecordsource" in query["sql"].lower()
                for query in captured
            )
        )

    def test_deleted_list_full_page_htmx_empty_and_permission_contract(
        self,
    ) -> None:
        self.login()
        full = self.client.get(self.deleted_list_url())
        htmx = self.client.get(
            self.deleted_list_url(),
            headers={"HX-Request": "true"},
        )
        empty_person = Person.objects.create(
            first_name="Bez Koše",
            access_level=AccessLevel.PUBLIC,
        )
        empty = self.client.get(self.deleted_list_url(empty_person))

        self.assertTemplateUsed(full, "people/person_shell.html")
        self.assertTemplateUsed(
            htmx,
            "people/partials/person_health_deleted.html",
        )
        self.assertNotContains(htmx, "Seznam osob")
        self.assertContains(empty, "Koš zdravotních záznamů je prázdný")

        denied_actors = (
            None,
            self.user(
                "deleted-read-only",
                ("accounts", "view_restricted_content"),
            ),
            self.user(
                "deleted-inactive",
                ("health", "delete_healthrecord"),
                is_active=False,
            ),
            self.user("deleted-staff", is_staff=True),
        )
        for actor in denied_actors:
            with self.subTest(actor=getattr(actor, "username", "anonymous")):
                self.client.logout()
                if actor is not None:
                    self.login(actor)
                self.assertEqual(
                    self.client.get(self.deleted_list_url()).status_code,
                    403,
                )

    def test_deleted_list_superuser_demo_and_no_content_count_leak(self) -> None:
        superuser = self.user("deleted-superuser", is_superuser=True)
        self.login(superuser)
        response = self.client.get(self.deleted_list_url())
        self.assertContains(response, "Administrátorský odstraněný")

        demo = self.user(
            "stemma-demo-administrator",
            ("health", "delete_healthrecord"),
            ("accounts", "view_restricted_content"),
            ("accounts", "view_admin_only_content"),
        )
        self.login(demo)
        self.assertEqual(self.client.get(self.deleted_list_url()).status_code, 200)

        model_only = self.user(
            "deleted-model-only",
            ("health", "delete_healthrecord"),
        )
        self.login(model_only)
        hidden = self.client.get(self.deleted_list_url())
        self.assertEqual(hidden.status_code, 200)
        self.assertNotContains(hidden, "Odstraněný záznam")
        self.assertNotContains(hidden, "Administrátorský odstraněný")

    def test_restore_get_is_read_only_and_uses_management_loader(self) -> None:
        self.login()
        with patch(
            "people.views.get_soft_deleted_health_record_for_management",
            wraps=lambda **kwargs: self.deleted,
        ) as loader:
            response = self.client.get(self.restore_url())

        self.deleted.refresh_from_db()
        self.assertIsNotNone(self.deleted.deleted_at)
        self.assertTemplateUsed(
            response,
            "people/partials/health_record_restore_soft_deleted_confirm.html",
        )
        loader.assert_called_once()

    def test_restore_post_delegates_and_redirects_to_available_detail(
        self,
    ) -> None:
        self.login()
        with patch(
            "people.views.restore_soft_deleted_health_record",
            wraps=restore_soft_deleted_health_record,
        ) as use_case:
            response = self.client.post(self.restore_url())

        detail_url = reverse(
            "people:health-record-detail",
            args=(self.person.pk, self.deleted.pk),
        )
        self.assertRedirects(response, detail_url)
        self.assertEqual(self.client.get(detail_url).status_code, 200)
        use_case.assert_called_once()

    def test_restore_htmx_returns_detail_and_canonical_url(self) -> None:
        self.login()

        response = self.client.post(
            self.restore_url(),
            headers={"HX-Request": "true"},
        )

        self.assertTemplateUsed(
            response,
            "people/partials/person_health_record.html",
        )
        self.assertEqual(
            response.headers["HX-Push-Url"],
            reverse(
                "people:health-record-detail",
                args=(self.person.pk, self.deleted.pk),
            ),
        )

    def test_restore_denials_and_fail_closed_targets(self) -> None:
        denied_actors = (
            None,
            self.user(
                "restore-read-only",
                ("accounts", "view_restricted_content"),
            ),
            self.user(
                "restore-inactive",
                ("health", "delete_healthrecord"),
                ("accounts", "view_restricted_content"),
                is_active=False,
            ),
            self.user("restore-staff", is_staff=True),
        )
        for actor in denied_actors:
            with self.subTest(actor=getattr(actor, "username", "anonymous")):
                self.client.logout()
                if actor is not None:
                    self.login(actor)
                self.assertEqual(self.client.get(self.restore_url()).status_code, 403)

        self.login()
        hidden_urls = (
            self.restore_url(self.active),
            self.restore_url(self.archived),
            self.restore_url(self.combined),
            self.restore_url(self.foreign_deleted),
            self.restore_url(self.deleted, self.other_person),
            self.restore_url(self.admin_deleted),
        )
        for url in hidden_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url).status_code, 404)

    def test_restore_rejects_inactive_type_person_lifecycle_and_csrf(self) -> None:
        self.login()
        self.record_type.is_active = False
        self.record_type.save(update_fields=("is_active",))
        self.assertEqual(self.client.get(self.restore_url()).status_code, 404)
        self.record_type.is_active = True
        self.record_type.save(update_fields=("is_active",))

        for field in ("archived_at", "deleted_at"):
            setattr(self.person, field, timezone.now())
            self.person.save(update_fields=(field,))
            with self.subTest(field=field):
                self.assertEqual(self.client.get(self.restore_url()).status_code, 404)
            setattr(self.person, field, None)
            self.person.save(update_fields=(field,))

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.actor)
        self.assertEqual(csrf_client.post(self.restore_url()).status_code, 403)

    def test_restore_superuser_and_service_validation(self) -> None:
        superuser = self.user("restore-superuser", is_superuser=True)
        self.login(superuser)
        self.assertEqual(
            self.client.post(self.restore_url(self.admin_deleted)).status_code,
            302,
        )

        self.login()
        with patch(
            "people.views.restore_soft_deleted_health_record",
            side_effect=ValidationError(
                {"health_record": "Obnovení nelze provést."}
            ),
        ):
            response = self.client.post(self.restore_url())
        self.assertContains(response, "Obnovení nelze provést")
        self.deleted.refresh_from_db()
        self.assertIsNotNone(self.deleted.deleted_at)

    def test_presentation_and_unsupported_method_contract(self) -> None:
        self.login()
        health_url = reverse("people:health", args=(self.person.pk,))
        detail_url = reverse(
            "people:health-record-detail",
            args=(self.person.pk, self.active.pk),
        )
        self.assertContains(self.client.get(health_url), "Koš")
        self.assertContains(self.client.get(detail_url), "Přesunout do koše")

        read_only = self.user(
            "presentation-read-only",
            ("accounts", "view_restricted_content"),
        )
        self.login(read_only)
        self.assertNotContains(
            self.client.get(health_url),
            self.deleted_list_url(),
        )
        self.assertNotContains(
            self.client.get(detail_url),
            self.delete_url(),
        )

        self.login()
        self.assertEqual(self.client.post(self.deleted_list_url()).status_code, 405)
        for url in (self.delete_url(), self.restore_url()):
            for method in (
                self.client.put,
                self.client.patch,
                self.client.delete,
            ):
                self.assertEqual(method(url).status_code, 405)

    @override_settings(DEBUG=False)
    def test_hidden_deleted_targets_share_not_found_boundary(self) -> None:
        self.login()
        urls = (
            self.delete_url(self.admin_active),
            self.delete_url(self.archived),
            self.delete_url(self.foreign_active),
            reverse(
                "people:health-record-soft-delete",
                args=(self.person.pk, 999999),
            ),
            self.restore_url(self.active),
            self.restore_url(self.combined),
            self.restore_url(self.foreign_deleted),
            reverse(
                "people:health-record-restore-soft-deleted",
                args=(self.person.pk, 999999),
            ),
        )
        responses = [self.client.get(url) for url in urls]
        self.assertTrue(all(response.status_code == 404 for response in responses))
        self.assertTrue(
            all(
                b"Zdravotn\xc3\xad z\xc3\xa1znam nebyl nalezen"
                not in response.content
                for response in responses
            )
        )

    def test_deletion_views_have_no_direct_orm_or_materials_path(self) -> None:
        source = "".join(
            getsource(view)
            for view in (
                person_health_deleted,
                person_health_record_soft_delete,
                person_health_record_restore_soft_deleted,
            )
        )

        self.assertNotIn(".objects", source)
        self.assertNotIn(".save(", source)
        self.assertNotIn("attachment", source.lower())
        self.assertNotIn("source", source.lower())

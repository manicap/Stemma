from inspect import getsource
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from common.choices import AccessLevel
from health.models import HealthRecord, HealthRecordType
from health.use_cases import (
    archive_health_record,
    restore_archived_health_record,
)

from .models import Person
from .views import (
    person_health_archive,
    person_health_record_archive,
    person_health_record_restore,
)


class PersonHealthLifecycleWebTests(TestCase):
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
        self.active = self.record("Aktivní záznam")
        self.admin_active = self.record(
            "Administrátorský aktivní",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        now = timezone.now()
        self.archived = self.record("Archivovaný záznam", archived_at=now)
        self.admin_archived = self.record(
            "Administrátorský archivovaný",
            access_level=AccessLevel.ADMIN_ONLY,
            archived_at=now,
        )
        self.deleted = self.record(
            "Odstraněný archivovaný",
            archived_at=now,
            deleted_at=now,
        )
        self.combined = self.record(
            "Kombinovaný legacy stav",
            archived_at=now,
            deleted_at=now,
        )
        self.foreign = self.record(
            "Cizí archivovaný",
            person=self.other_person,
            archived_at=now,
        )
        self.actor = self.user(
            "health-manager",
            ("health", "change_healthrecord"),
            ("accounts", "view_restricted_content"),
        )

    def record(self, title: str, **values: object) -> HealthRecord:
        return HealthRecord.objects.create(
            person=values.pop("person", self.person),
            record_type=self.record_type,
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

    def login(self, actor=None) -> None:
        self.client.force_login(actor or self.actor)

    def archive_url(self, record=None, person=None) -> str:
        return reverse(
            "people:health-record-archive",
            args=((person or self.person).pk, (record or self.active).pk),
        )

    def restore_url(self, record=None, person=None) -> str:
        return reverse(
            "people:health-record-restore",
            args=((person or self.person).pk, (record or self.archived).pk),
        )

    def test_archive_get_confirmation_is_read_only_full_page_and_htmx(self) -> None:
        self.login()

        full = self.client.get(self.archive_url())
        htmx = self.client.get(
            self.archive_url(),
            headers={"HX-Request": "true"},
        )

        self.active.refresh_from_db()
        self.assertIsNone(self.active.archived_at)
        self.assertTemplateUsed(full, "people/person_shell.html")
        self.assertTemplateUsed(
            htmx,
            "people/partials/health_record_archive_confirm.html",
        )
        self.assertContains(full, "Důvod archivace")

    def test_archive_post_delegates_reason_and_redirects_to_health_list(self) -> None:
        self.login()
        with patch(
            "people.views.archive_health_record",
            wraps=archive_health_record,
        ) as use_case:
            response = self.client.post(
                self.archive_url(),
                {"reason": "  Historický údaj  "},
            )

        self.assertRedirects(
            response,
            reverse("people:health", args=(self.person.pk,)),
        )
        self.active.refresh_from_db()
        self.assertEqual(self.active.archive_reason, "Historický údaj")
        use_case.assert_called_once()
        self.assertEqual(
            use_case.call_args.kwargs["reason"],
            "  Historický údaj  ",
        )

    def test_archive_htmx_returns_active_list_and_canonical_url(self) -> None:
        self.login()

        response = self.client.post(
            self.archive_url(),
            headers={"HX-Request": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "people/partials/person_health.html")
        self.assertEqual(
            response.headers["HX-Push-Url"],
            reverse("people:health", args=(self.person.pk,)),
        )
        self.assertNotContains(response, "Aktivní záznam")
        self.assertContains(response, "byl archivován")

    def test_archive_denies_anonymous_inactive_staff_and_missing_permission(
        self,
    ) -> None:
        actors_and_statuses = (
            (None, 404),
            (
                self.user(
                    "read-only",
                    ("accounts", "view_restricted_content"),
                ),
                403,
            ),
            (
                self.user(
                    "inactive",
                    ("health", "change_healthrecord"),
                    ("accounts", "view_restricted_content"),
                    is_active=False,
                ),
                404,
            ),
            (self.user("staff", is_staff=True), 404),
        )
        for actor, status in actors_and_statuses:
            with self.subTest(actor=getattr(actor, "username", "anonymous")):
                if actor is not None:
                    self.login(actor)
                self.assertEqual(
                    self.client.post(self.archive_url()).status_code,
                    status,
                )
                self.active.refresh_from_db()
                self.assertIsNone(self.active.archived_at)
                self.client.logout()

    def test_archive_content_access_superuser_and_fail_closed_targets(self) -> None:
        self.login()
        self.assertEqual(
            self.client.get(self.archive_url(self.admin_active)).status_code,
            404,
        )
        superuser = self.user("superuser", is_superuser=True)
        self.login(superuser)
        self.assertEqual(
            self.client.post(self.archive_url(self.admin_active)).status_code,
            302,
        )
        self.login()
        hidden_targets = (
            self.archive_url(self.archived),
            self.archive_url(self.deleted),
            self.archive_url(self.foreign),
            self.archive_url(self.active, self.other_person),
        )
        for url in hidden_targets:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url).status_code, 404)

    def test_archive_fails_closed_for_archived_and_deleted_person(self) -> None:
        self.login()
        for field in ("archived_at", "deleted_at"):
            setattr(self.person, field, timezone.now())
            self.person.save(update_fields=(field,))
            with self.subTest(field=field):
                self.assertEqual(
                    self.client.post(self.archive_url()).status_code,
                    404,
                )
            setattr(self.person, field, None)
            self.person.save(update_fields=(field,))

    def test_archive_csrf_and_service_validation_preserve_reason(self) -> None:
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.actor)
        self.assertEqual(
            csrf_client.post(self.archive_url(), {"reason": "x"}).status_code,
            403,
        )
        self.login()
        with patch(
            "people.views.archive_health_record",
            side_effect=ValidationError(
                {"health_record": "Archivaci nelze provést."}
            ),
        ):
            response = self.client.post(
                self.archive_url(),
                {"reason": "Zachovaný důvod"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Zachovaný důvod")
        self.assertContains(response, "Archivaci nelze provést")
        self.active.refresh_from_db()
        self.assertIsNone(self.active.archived_at)

    def test_archived_list_is_scoped_filtered_and_has_no_count_leak(self) -> None:
        self.login()

        response = self.client.get(
            reverse("people:health-archive", args=(self.person.pk,))
        )

        self.assertContains(response, "Archivovaný záznam")
        for hidden in (
            "Aktivní záznam",
            "Administrátorský archivovaný",
            "Odstraněný archivovaný",
            "Kombinovaný legacy stav",
            "Cizí archivovaný",
        ):
            self.assertNotContains(response, hidden)
        self.assertNotContains(response, "Přílohy")
        self.assertNotContains(response, "Zdroje")

    def test_archived_list_full_page_htmx_and_empty_state_contract(self) -> None:
        self.login()
        url = reverse("people:health-archive", args=(self.person.pk,))

        full = self.client.get(url)
        htmx = self.client.get(url, headers={"HX-Request": "true"})
        empty_person = Person.objects.create(
            first_name="Bez archivu",
            access_level=AccessLevel.PUBLIC,
        )
        empty = self.client.get(
            reverse("people:health-archive", args=(empty_person.pk,))
        )

        self.assertTemplateUsed(full, "people/person_shell.html")
        self.assertTemplateUsed(
            htmx,
            "people/partials/person_health_archive.html",
        )
        self.assertNotContains(htmx, "Seznam osob")
        self.assertContains(empty, "nejsou dostupné žádné archivované")
        self.assertContains(full, reverse("people:health", args=(self.person.pk,)))

    def test_archived_list_requires_permission_not_staff_and_allows_superuser(
        self,
    ) -> None:
        url = reverse("people:health-archive", args=(self.person.pk,))
        actors = (
            None,
            self.user(
                "archive-read-only",
                ("accounts", "view_restricted_content"),
            ),
            self.user(
                "archive-inactive",
                ("health", "change_healthrecord"),
                is_active=False,
            ),
            self.user("archive-staff", is_staff=True),
        )
        for actor in actors:
            with self.subTest(actor=getattr(actor, "username", "anonymous")):
                if actor is not None:
                    self.login(actor)
                self.assertEqual(self.client.get(url).status_code, 403)
                self.client.logout()
        self.login(self.user("archive-superuser", is_superuser=True))
        response = self.client.get(url)
        self.assertContains(response, "Administrátorský archivovaný")

    def test_restore_get_is_read_only_and_uses_archive_management_loader(self) -> None:
        self.login()
        with patch(
            "people.views.get_archived_health_record_for_management",
            wraps=lambda **kwargs: self.archived,
        ) as loader:
            response = self.client.get(self.restore_url())

        self.archived.refresh_from_db()
        self.assertIsNotNone(self.archived.archived_at)
        self.assertTemplateUsed(
            response,
            "people/partials/health_record_restore_confirm.html",
        )
        htmx = self.client.get(
            self.restore_url(),
            headers={"HX-Request": "true"},
        )
        self.assertTemplateUsed(
            htmx,
            "people/partials/health_record_restore_confirm.html",
        )
        self.assertNotContains(htmx, "Seznam osob")
        self.assertContains(
            response,
            reverse("people:health-archive", args=(self.person.pk,)),
        )
        loader.assert_called_once()

    def test_restore_post_delegates_and_redirects_to_available_detail(self) -> None:
        self.login()
        with patch(
            "people.views.restore_archived_health_record",
            wraps=restore_archived_health_record,
        ) as use_case:
            response = self.client.post(self.restore_url())

        detail_url = reverse(
            "people:health-record-detail",
            args=(self.person.pk, self.archived.pk),
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
                args=(self.person.pk, self.archived.pk),
            ),
        )

    def test_restore_denials_and_fail_closed_lifecycle_targets(self) -> None:
        url = self.restore_url()
        actors_and_statuses = (
            (None, 403),
            (
                self.user(
                    "restore-read-only",
                    ("accounts", "view_restricted_content"),
                ),
                403,
            ),
            (
                self.user(
                    "restore-inactive",
                    ("health", "change_healthrecord"),
                    ("accounts", "view_restricted_content"),
                    is_active=False,
                ),
                403,
            ),
            (self.user("restore-staff", is_staff=True), 403),
        )
        for actor, status in actors_and_statuses:
            with self.subTest(actor=getattr(actor, "username", "anonymous")):
                if actor is not None:
                    self.login(actor)
                self.assertEqual(self.client.post(url).status_code, status)
                self.client.logout()
        self.login()
        hidden_targets = (
            self.restore_url(self.active),
            self.restore_url(self.deleted),
            self.restore_url(self.combined),
            self.restore_url(self.foreign),
            self.restore_url(self.archived, self.other_person),
            self.restore_url(self.admin_archived),
        )
        for hidden_url in hidden_targets:
            with self.subTest(url=hidden_url):
                self.assertEqual(self.client.get(hidden_url).status_code, 404)
                self.assertEqual(self.client.post(hidden_url).status_code, 404)

    def test_restore_service_validation_rerenders_safe_confirmation(self) -> None:
        self.login()
        with patch(
            "people.views.restore_archived_health_record",
            side_effect=ValidationError(
                {"health_record": "Obnovení nelze provést."}
            ),
        ):
            response = self.client.post(self.restore_url())

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "people/partials/health_record_restore_confirm.html",
        )
        self.assertContains(response, "Obnovení nelze provést")
        self.archived.refresh_from_db()
        self.assertIsNotNone(self.archived.archived_at)

    def test_restore_fails_closed_for_archived_and_deleted_person(self) -> None:
        self.login()
        for field in ("archived_at", "deleted_at"):
            setattr(self.person, field, timezone.now())
            self.person.save(update_fields=(field,))
            with self.subTest(field=field):
                self.assertEqual(
                    self.client.post(self.restore_url()).status_code,
                    404,
                )
            setattr(self.person, field, None)
            self.person.save(update_fields=(field,))

    def test_superuser_restores_admin_only_and_restore_is_csrf_protected(
        self,
    ) -> None:
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.actor)
        self.assertEqual(csrf_client.post(self.restore_url()).status_code, 403)

        superuser = self.user("restore-superuser", is_superuser=True)
        self.login(superuser)
        self.assertEqual(
            self.client.post(self.restore_url(self.admin_archived)).status_code,
            302,
        )
        self.admin_archived.refresh_from_db()
        self.assertIsNone(self.admin_archived.archived_at)

    def test_invisible_person_and_write_permission_without_content_fail_closed(
        self,
    ) -> None:
        hidden_person = Person.objects.create(
            first_name="Skrytá osoba",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        hidden_active = self.record(
            "Skrytý aktivní",
            person=hidden_person,
        )
        hidden_archived = self.record(
            "Skrytý archivovaný",
            person=hidden_person,
            archived_at=timezone.now(),
        )
        self.login()
        hidden_action_urls = (
            self.archive_url(hidden_active, hidden_person),
            self.restore_url(hidden_archived, hidden_person),
        )
        for url in hidden_action_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url).status_code, 404)
        self.assertEqual(
            self.client.get(
                reverse("people:health-archive", args=(hidden_person.pk,))
            ).status_code,
            404,
        )

        model_only = self.user(
            "model-only",
            ("health", "change_healthrecord"),
        )
        self.login(model_only)
        self.assertEqual(self.client.post(self.archive_url()).status_code, 404)
        archive_list = self.client.get(
            reverse("people:health-archive", args=(self.person.pk,))
        )
        self.assertEqual(archive_list.status_code, 200)
        self.assertNotContains(archive_list, "Archivovaný záznam")
        self.assertEqual(self.client.post(self.restore_url()).status_code, 404)

    def test_lifecycle_actions_follow_server_presentation_booleans(self) -> None:
        health_url = reverse("people:health", args=(self.person.pk,))
        detail_url = reverse(
            "people:health-record-detail",
            args=(self.person.pk, self.active.pk),
        )
        self.login()
        self.assertContains(self.client.get(health_url), "Archivované záznamy")
        self.assertContains(self.client.get(detail_url), "Archivovat")

        read_only = self.user(
            "presentation-read-only",
            ("accounts", "view_restricted_content"),
        )
        self.login(read_only)
        self.assertNotContains(
            self.client.get(health_url),
            reverse("people:health-archive", args=(self.person.pk,)),
        )
        self.assertNotContains(
            self.client.get(detail_url),
            self.archive_url(),
        )

    @override_settings(DEBUG=False)
    def test_hidden_archive_targets_share_not_found_boundary(self) -> None:
        self.login()
        urls = (
            self.restore_url(self.deleted),
            self.restore_url(self.foreign),
            self.restore_url(self.archived, self.other_person),
            reverse(
                "people:health-record-restore",
                args=(self.person.pk, 999999),
            ),
        )
        responses = [self.client.get(url) for url in urls]
        self.assertTrue(all(response.status_code == 404 for response in responses))
        self.assertTrue(
            all(
                b"Zdravotn\xc3\xad z\xc3\xa1znam nebyl nalezen" not in response.content
                for response in responses
            )
        )

    def test_lifecycle_views_do_not_write_through_orm_or_touch_materials(self) -> None:
        source = "".join(
            getsource(view)
            for view in (
                person_health_archive,
                person_health_record_archive,
                person_health_record_restore,
            )
        )

        self.assertNotIn(".objects", source)
        self.assertNotIn(".save(", source)
        self.assertNotIn("attachment", source.lower())
        self.assertNotIn("source", source.lower())

    def test_unsupported_lifecycle_methods_are_rejected(self) -> None:
        self.login()
        archive_list_url = reverse(
            "people:health-archive",
            args=(self.person.pk,),
        )
        self.assertEqual(self.client.post(archive_list_url).status_code, 405)
        for url in (self.archive_url(), self.restore_url()):
            for method in (
                self.client.put,
                self.client.patch,
                self.client.delete,
            ):
                with self.subTest(url=url, method=method.__name__):
                    self.assertEqual(method(url).status_code, 405)

from dataclasses import fields, replace
from inspect import getsource
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from common.choices import AccessLevel, DatePrecision, DateQualifier
from events.models import Event, EventParticipant, EventType, ParticipantRole
from health.models import HealthRecord, HealthRecordType
from places.choices import GraveSiteStatus
from places.models import (
    GraveSite,
    GraveSiteType,
    PersonGraveSite,
    PersonGraveSiteRole,
    Place,
    Residence,
    ResidenceType,
)
from pypdf import PdfReader

from .models import (
    NameType,
    Person,
    PersonName,
    Relationship,
    RelationshipType,
)
from .pdf_exports import (
    PdfListItem,
    PersonPdfExport,
    build_person_pdf,
    get_person_pdf_export,
)
from .views import person_pdf_export


class PersonPdfExportTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.relationship_type = RelationshipType.objects.get(code="partner")
        cls.residence_type = ResidenceType.objects.get(
            code="primary_residence"
        )
        cls.grave_site_type = GraveSiteType.objects.get(code="grave")
        cls.grave_site_role = PersonGraveSiteRole.objects.get(code="buried")
        cls.event_type = EventType.objects.get(code="other")
        cls.participant_role = ParticipantRole.objects.get(code="other")

    def setUp(self) -> None:
        self.person = Person.objects.create(
            first_name="Žofie",
            last_name="Říhová",
            title_before_name="PhDr.",
            biography="Česká kronikářka a vypravěčka.",
            notes="Bezpečná poznámka k osobě.",
        )
        self.partner = Person.objects.create(
            first_name="Bohdan",
            last_name="Černý",
        )
        Relationship.objects.create(
            relationship_type=self.relationship_type,
            person_a=self.person,
            person_b=self.partner,
            date_precision=DatePrecision.YEAR,
            start_year=1910,
        )
        self.place = Place.objects.create(
            name="České Budějovice",
            normalized_name="ceske budejovice",
        )
        Residence.objects.create(
            person=self.person,
            residence_type=self.residence_type,
            place=self.place,
            address_text="Panská 12",
            note="Rodinný dům.",
            date_precision=DatePrecision.YEAR,
            date_qualifier=DateQualifier.APPROXIMATE,
            start_year=1920,
        )
        grave_site = GraveSite.objects.create(
            grave_site_type=self.grave_site_type,
            status=GraveSiteStatus.EXISTING,
            place=self.place,
            cemetery_name="Hřbitov svaté Otýlie",
            section="A",
            row="2",
            grave_number="15",
        )
        PersonGraveSite.objects.create(
            person=self.person,
            grave_site=grave_site,
            role=self.grave_site_role,
            note="Rodinné místo.",
        )
        event = Event.objects.create(
            event_type=self.event_type,
            place=self.place,
            title="Rodinné setkání",
            description="Vzpomínkové odpoledne.",
            date_precision=DatePrecision.YEAR,
            start_year=1930,
        )
        EventParticipant.objects.create(
            event=event,
            person=self.person,
            role=self.participant_role,
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
        for permission in permissions:
            self.grant(actor, permission)
        return actor

    def export(self, actor=None):
        return get_person_pdf_export(
            person_id=self.person.pk,
            actor=actor or AnonymousUser(),
        )

    def test_visible_person_returns_valid_a4_pdf_response(self) -> None:
        response = self.client.get(
            reverse("people:pdf-export", args=(self.person.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(
            response["Content-Disposition"],
            'inline; filename="phdr-zofie-rihova.pdf"',
        )
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertIn(b"/MediaBox [ 0 0 595.2756 841.8898 ]", response.content)
        text = "\n".join(
            page.extract_text()
            for page in PdfReader(BytesIO(response.content)).pages
        )
        for expected in (
            "PhDr. Žofie Říhová",
            "Česká kronikářka a vypravěčka.",
            "Vztahy",
            "Bohdan Černý",
            "Bydliště",
            "České Budějovice",
            "Hrobová místa",
            "Hřbitov svaté Otýlie",
            "Události",
            "Rodinné setkání",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_presentation_contains_only_approved_person_sections(self) -> None:
        export = self.export()

        self.assertEqual(export.display_name, "PhDr. Žofie Říhová")
        self.assertEqual(export.biography, "Česká kronikářka a vypravěčka.")
        self.assertEqual(export.notes, "Bezpečná poznámka k osobě.")
        self.assertEqual(export.relationships[0].title, "Bohdan Černý")
        self.assertTrue(
            any("partner" in line for line in export.relationships[0].lines)
        )
        self.assertEqual(export.residences[0].title, "České Budějovice")
        self.assertIn("přibližně 1920", export.residences[0].lines)
        self.assertEqual(
            export.grave_sites[0].title,
            "Hřbitov svaté Otýlie",
        )
        self.assertIn("Oddíl A · Řada 2 · Hrob 15", export.grave_sites[0].lines)
        self.assertEqual(export.events[0].title, "Rodinné setkání")
        self.assertIn("Vzpomínkové odpoledne.", export.events[0].lines)

    def test_minimal_person_omits_empty_sections_and_renders(self) -> None:
        minimal = Person.objects.create(first_name="Áďa")

        export = get_person_pdf_export(
            person_id=minimal.pk,
            actor=AnonymousUser(),
        )
        pdf = build_person_pdf(export)

        self.assertEqual(export.display_name, "Áďa")
        self.assertEqual(export.relationships, ())
        self.assertEqual(export.residences, ())
        self.assertEqual(export.grave_sites, ())
        self.assertEqual(export.events, ())
        self.assertTrue(pdf.startswith(b"%PDF-"))
        reader = PdfReader(BytesIO(pdf))
        self.assertEqual(len(reader.pages), 1)
        text = reader.pages[0].extract_text()
        self.assertIn("Áďa", text)
        for omitted_heading in (
            "Životopis",
            "Poznámky",
            "Vztahy",
            "Bydliště",
            "Hrobová místa",
            "Události",
        ):
            self.assertNotIn(omitted_heading, text)

    def test_large_export_is_multipage_and_keeps_last_item(self) -> None:
        export = self.export()
        items = tuple(
            PdfListItem(
                title=f"Dlouhá položka {index}",
                lines=(
                    "Bezpečný text s českou diakritikou žluťoučký kůň.",
                    f"Koncový marker {index}",
                ),
            )
            for index in range(80)
        )

        pdf = build_person_pdf(replace(export, events=items))
        reader = PdfReader(BytesIO(pdf))
        text_by_page = [page.extract_text() for page in reader.pages]

        self.assertGreater(len(reader.pages), 1)
        self.assertIn("Koncový marker 79", text_by_page[-1])
        for index in range(80):
            marker_page = next(
                text for text in text_by_page if f"Koncový marker {index}" in text
            )
            self.assertIn(f"Dlouhá položka {index}", marker_page)
        self.assertIn(
            f"Stemma · strana {len(reader.pages)}",
            text_by_page[-1],
        )

    def test_visible_life_events_supply_derived_birth_and_death(self) -> None:
        for event_code, role_code, year in (
            ("birth", "born_person", 1890),
            ("death", "deceased_person", 1975),
        ):
            event = Event.objects.create(
                event_type=EventType.objects.get(code=event_code),
                date_precision=DatePrecision.YEAR,
                start_year=year,
            )
            EventParticipant.objects.create(
                event=event,
                person=self.person,
                role=ParticipantRole.objects.get(code=role_code),
            )

        export = self.export()

        self.assertEqual(export.birth_text, "1890")
        self.assertEqual(export.death_text, "1975")
        self.assertEqual(export.life_status, "Zemřelá osoba")

    @override_settings(DEBUG=False)
    def test_missing_and_hidden_people_fail_closed_identically(self) -> None:
        hidden = Person.objects.create(
            first_name="Skrytá",
            access_level=AccessLevel.RESTRICTED,
        )

        hidden_response = self.client.get(
            reverse("people:pdf-export", args=(hidden.pk,))
        )
        missing_response = self.client.get(
            reverse("people:pdf-export", args=(999_999,))
        )

        self.assertEqual(hidden_response.status_code, 404)
        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(hidden_response.content, missing_response.content)

    def test_anonymous_inactive_staff_and_superuser_follow_central_policy(
        self,
    ) -> None:
        restricted = Person.objects.create(
            first_name="Omezená",
            access_level=AccessLevel.RESTRICTED,
        )
        url = reverse("people:pdf-export", args=(restricted.pk,))

        self.assertEqual(self.client.get(url).status_code, 404)
        actors = (
            self.user(
                "inactive",
                "view_restricted_content",
                is_active=False,
            ),
            self.user("staff", is_staff=True),
        )
        for actor in actors:
            with self.subTest(actor=actor.username):
                self.client.force_login(actor)
                self.assertEqual(self.client.get(url).status_code, 404)
                self.client.logout()

        self.client.force_login(self.user("superuser", is_superuser=True))
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_only_person_requires_matching_content_permission(self) -> None:
        admin_only = Person.objects.create(
            first_name="Administrativní",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        url = reverse("people:pdf-export", args=(admin_only.pk,))
        restricted_actor = self.user(
            "restricted-only",
            "view_restricted_content",
        )
        admin_actor = self.user(
            "admin-only",
            "view_admin_only_content",
        )

        self.client.force_login(restricted_actor)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(admin_actor)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_archived_and_deleted_people_are_not_exportable(self) -> None:
        for lifecycle_field in ("archived_at", "deleted_at"):
            person = Person.objects.create(first_name=lifecycle_field)
            Person.objects.filter(pk=person.pk).update(
                **{lifecycle_field: timezone.now()}
            )
            with self.subTest(lifecycle_field=lifecycle_field):
                response = self.client.get(
                    reverse("people:pdf-export", args=(person.pk,))
                )
                self.assertEqual(response.status_code, 404)

    def test_hidden_related_data_and_participant_do_not_leak(self) -> None:
        hidden_person = Person.objects.create(
            first_name="Přísně skrytá účastnice",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        Relationship.objects.create(
            relationship_type=self.relationship_type,
            person_a=self.person,
            person_b=hidden_person,
            access_level=AccessLevel.ADMIN_ONLY,
            date_precision=DatePrecision.YEAR,
            start_year=1940,
        )
        hidden_event = Event.objects.create(
            event_type=self.event_type,
            title="Tajná událost",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        EventParticipant.objects.create(
            event=hidden_event,
            person=self.person,
            role=self.participant_role,
        )
        EventParticipant.objects.create(
            event=Event.objects.get(title="Rodinné setkání"),
            person=hidden_person,
            role=self.participant_role,
        )
        Residence.objects.create(
            person=self.person,
            residence_type=self.residence_type,
            address_text="Skryté bydliště",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        hidden_site = GraveSite.objects.create(
            grave_site_type=self.grave_site_type,
            location_text="Skryté hrobové místo",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        PersonGraveSite.objects.create(
            person=self.person,
            grave_site=hidden_site,
            role=self.grave_site_role,
        )

        export = self.export()
        serialized = repr(export)

        self.assertNotIn("Přísně skrytá účastnice", serialized)
        self.assertNotIn("Tajná událost", serialized)
        self.assertNotIn("Skryté bydliště", serialized)
        self.assertNotIn("Skryté hrobové místo", serialized)
        self.assertNotIn("id", {field.name for field in fields(PersonPdfExport)})

    def test_health_materials_names_and_internal_metadata_are_not_exported(
        self,
    ) -> None:
        health_type = HealthRecordType.objects.create(
            code="pdf-secret-health",
            name="Citlivý typ",
        )
        HealthRecord.objects.create(
            person=self.person,
            record_type=health_type,
            title="Citlivá diagnóza",
        )
        alternate_type = NameType.objects.create(
            code="pdf-secret-name",
            name="Skryté jméno",
        )
        PersonName.objects.create(
            person=self.person,
            name_type=alternate_type,
            value="Neexportovaná přezdívka",
            normalized_value="neexportovana prezdivka",
        )

        serialized = repr(self.export())
        source = getsource(get_person_pdf_export)

        self.assertNotIn("Citlivá diagnóza", serialized)
        self.assertNotIn("Neexportovaná přezdívka", serialized)
        self.assertNotIn("health", source.lower())
        self.assertNotIn("materials", source.lower())
        self.assertNotIn("storage", source.lower())

    def test_view_is_get_only_and_delegates_without_business_orm(self) -> None:
        url = reverse("people:pdf-export", args=(self.person.pk,))

        self.assertEqual(self.client.post(url).status_code, 405)
        self.assertNotIn(".objects", getsource(person_pdf_export))

    def test_person_header_has_plain_non_htmx_export_link(self) -> None:
        response = self.client.get(
            reverse("people:detail", args=(self.person.pk,))
        )
        export_url = reverse("people:pdf-export", args=(self.person.pk,))

        self.assertContains(response, f'href="{export_url}"')
        self.assertContains(response, "Export PDF")
        export_anchor = response.content.decode().split("Export PDF")[0]
        self.assertNotIn("hx-get", export_anchor.rsplit("<a", 1)[-1])

    def _query_count(self) -> int:
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(
                reverse("people:pdf-export", args=(self.person.pk,))
            )
        self.assertEqual(response.status_code, 200)
        return len(captured)

    def test_query_count_does_not_grow_with_export_items(self) -> None:
        baseline = self._query_count()
        for index in range(5):
            partner = Person.objects.create(first_name=f"Partner {index}")
            Relationship.objects.create(
                relationship_type=self.relationship_type,
                person_a=self.person,
                person_b=partner,
                date_precision=DatePrecision.YEAR,
                start_year=1950 + index,
            )
            place = Place.objects.create(
                name=f"Místo {index}",
                normalized_name=f"misto {index}",
            )
            Residence.objects.create(
                person=self.person,
                residence_type=self.residence_type,
                place=place,
                address_text=f"Adresa {index}",
            )
            grave_site = GraveSite.objects.create(
                grave_site_type=self.grave_site_type,
                place=place,
                cemetery_name=f"Hřbitov {index}",
            )
            PersonGraveSite.objects.create(
                person=self.person,
                grave_site=grave_site,
                role=self.grave_site_role,
            )
            event = Event.objects.create(
                event_type=self.event_type,
                title=f"Událost {index}",
            )
            EventParticipant.objects.create(
                event=event,
                person=self.person,
                role=self.participant_role,
            )

        self.assertEqual(self._query_count(), baseline)

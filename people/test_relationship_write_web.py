from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from common.choices import (
    AccessLevel,
    DatePrecision,
    DateQualifier,
    VerificationStatus,
)

from events.models import Event, EventParticipant, EventType, ParticipantRole

from .models import Person, Relationship, RelationshipType
from .use_cases import (
    RelationshipDetailsInput,
    create_person_relationship,
    update_person_relationship,
)


class PersonRelationshipWriteWebTests(TestCase):
    """HTTP a bezpečnostní integrace úzkého zápisu rodičů, dětí a partnerů."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.parent_type = RelationshipType.objects.get(code="biological_parent")
        cls.partner_type = RelationshipType.objects.get(code="partner")
        cls.spouse_type = RelationshipType.objects.get(code="spouse")
        cls.person = Person.objects.create(
            first_name="Anna",
            last_name="Nováková",
            access_level=AccessLevel.PUBLIC,
        )
        cls.other = Person.objects.create(
            first_name="Jan",
            last_name="Novák",
            access_level=AccessLevel.PUBLIC,
        )
        cls.third = Person.objects.create(
            first_name="Marie",
            last_name="Dvořáková",
            access_level=AccessLevel.PUBLIC,
        )
        cls.hidden = Person.objects.create(
            first_name="Skrytá",
            last_name="Osoba",
            access_level=AccessLevel.RESTRICTED,
        )

    def editor(self, username: str = "relationship-editor"):
        actor = get_user_model().objects.create_user(username=username)
        actor.groups.add(Group.objects.get(name="Editor"))
        return actor

    def reader(self, username: str = "relationship-reader"):
        actor = get_user_model().objects.create_user(username=username)
        actor.groups.add(Group.objects.get(name="Čtenář"))
        return actor

    def create_url(self, kind: str, person: Person | None = None) -> str:
        return reverse(
            f"people:relationship-create-{kind}",
            args=((person or self.person).pk,),
        )

    def edit_url(self, relationship: Relationship, person=None) -> str:
        return reverse(
            "people:relationship-edit",
            args=((person or self.person).pk, relationship.pk),
        )

    def form_data(self, **overrides: object) -> dict[str, object]:
        values: dict[str, object] = {
            "counterpart": self.other.pk,
            "date_precision": DatePrecision.UNKNOWN,
            "date_qualifier": DateQualifier.NONE,
            "start_year": "",
            "start_month": "",
            "start_day": "",
            "end_year": "",
            "end_month": "",
            "end_day": "",
            "original_date_text": "",
            "date_note": "",
            "note": "Podle matriky",
            "access_level": AccessLevel.PUBLIC,
            "verification_status": VerificationStatus.UNCONFIRMED,
        }
        values.update(overrides)
        return values

    def relationship(self, **values: object) -> Relationship:
        defaults: dict[str, object] = {
            "relationship_type": self.parent_type,
            "person_a": self.other,
            "person_b": self.person,
            "access_level": AccessLevel.PUBLIC,
        }
        defaults.update(values)
        return Relationship.objects.create(**defaults)

    def test_editor_htmx_parent_creation_orients_edge_and_offers_edit(
        self,
    ) -> None:
        actor = self.editor()
        self.assertTrue(actor.has_perm("people.add_relationship"))
        self.assertTrue(actor.has_perm("people.change_relationship"))
        self.client.force_login(actor)

        page = self.client.get(
            reverse("people:relationships", args=(self.person.pk,)),
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(page, "Přidat rodiče")
        self.assertContains(page, "Přidat dítě")
        self.assertContains(page, "Přidat partnera")

        response = self.client.post(
            self.create_url("parent") + "?q=anna",
            self.form_data(),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        relationship = Relationship.objects.get()
        self.assertEqual(relationship.relationship_type, self.parent_type)
        self.assertEqual(relationship.person_a, self.other)
        self.assertEqual(relationship.person_b, self.person)
        self.assertEqual(relationship.created_by, actor)
        self.assertEqual(relationship.note, "Podle matriky")
        self.assertEqual(
            response.headers["HX-Push-Url"],
            reverse("people:relationships", args=(self.person.pk,))
            + "?q=anna",
        )
        self.assertContains(response, "Vztah byl uložen.")
        self.assertContains(response, "Jan Novák")
        self.assertContains(response, self.edit_url(relationship) + "?q=anna")

    def test_child_and_partner_creation_full_page(self) -> None:
        self.client.force_login(self.editor())

        child = self.client.post(
            self.create_url("child"),
            self.form_data(counterpart=self.third.pk),
        )
        # Partner zakládaný z osoby s vyšším pk se uloží kanonicky jednou.
        partner = self.client.post(
            self.create_url("partner", person=self.third),
            self.form_data(
                counterpart=self.person.pk,
                date_precision=DatePrecision.RANGE,
                start_year=1910,
                end_year=1950,
            ),
        )

        self.assertRedirects(
            child,
            reverse("people:relationships", args=(self.person.pk,)),
            fetch_redirect_response=False,
        )
        self.assertEqual(partner.status_code, 302)
        child_edge = Relationship.objects.get(relationship_type=self.parent_type)
        self.assertEqual(
            (child_edge.person_a, child_edge.person_b),
            (self.person, self.third),
        )
        partner_edge = Relationship.objects.get(
            relationship_type=self.partner_type
        )
        self.assertEqual(
            (partner_edge.person_a, partner_edge.person_b),
            (self.person, self.third),
        )
        self.assertEqual(
            (partner_edge.start_year, partner_edge.end_year),
            (1910, 1950),
        )

    def test_reader_anonymous_and_inactive_cannot_write(self) -> None:
        relationship = self.relationship(note="Původní")
        self.client.force_login(self.reader())

        page = self.client.get(
            reverse("people:relationships", args=(self.person.pk,))
        )
        self.assertNotContains(page, "Přidat rodiče")
        self.assertNotContains(page, "Upravit vztah")
        self.assertEqual(self.client.get(self.create_url("parent")).status_code, 403)
        self.assertEqual(
            self.client.post(
                self.create_url("child"),
                self.form_data(counterpart=self.third.pk),
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                self.edit_url(relationship),
                self.form_data(note="Změna"),
            ).status_code,
            403,
        )

        self.client.logout()
        self.assertEqual(
            self.client.post(self.create_url("parent"), self.form_data()).status_code,
            403,
        )

        inactive = self.editor("inactive-relationship-editor")
        inactive.is_active = False
        inactive.save(update_fields=("is_active",))
        self.client.force_login(inactive)
        self.assertEqual(
            self.client.post(self.create_url("parent"), self.form_data()).status_code,
            403,
        )

        self.assertEqual(Relationship.objects.count(), 1)
        relationship.refresh_from_db()
        self.assertEqual(relationship.note, "Původní")

    def test_counterpart_must_be_visible_active_and_different(self) -> None:
        archived = Person.objects.create(
            first_name="Archivní",
            last_name="Osoba",
            archived_at=timezone.now(),
        )
        self.client.force_login(self.editor())

        form = self.client.get(self.create_url("parent"))
        self.assertContains(form, "Jan Novák")
        self.assertNotContains(form, "Skrytá")
        self.assertNotContains(form, "Archivní")
        for counterpart in (self.hidden, archived, self.person):
            response = self.client.post(
                self.create_url("parent"),
                self.form_data(counterpart=counterpart.pk),
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Formulář se nepodařilo uložit")
            self.assertNotContains(response, "Skrytá")

        self.assertFalse(Relationship.objects.exists())

    def test_cycle_duplicate_and_parent_range_are_rejected(self) -> None:
        self.relationship()
        self.client.force_login(self.editor())

        duplicate = self.client.post(self.create_url("parent"), self.form_data())
        cycle = self.client.post(self.create_url("child"), self.form_data())
        parent_range = self.client.post(
            self.create_url("parent"),
            self.form_data(
                counterpart=self.third.pk,
                date_precision=DatePrecision.RANGE,
                start_year=1900,
                end_year=1910,
            ),
        )

        self.assertContains(duplicate, "Stejná vazba se stejným časovým")
        self.assertContains(cycle, "vytvořila cyklus")
        self.assertContains(parent_range, "Formulář se nepodařilo uložit")
        self.assertNotContains(parent_range, 'name="end_year"')
        self.assertEqual(Relationship.objects.count(), 1)

    def test_create_form_offers_progressive_person_picker(self) -> None:
        self.client.force_login(self.editor())

        response = self.client.get(self.create_url("partner"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="relationship-person-picker"')
        self.assertContains(response, "data-relationship-person-select")
        self.assertContains(
            response,
            '<div class="form-field" data-form-nondirty '
            "data-relationship-person-search-container hidden>",
            html=False,
        )
        self.assertContains(
            response,
            'aria-controls="id_counterpart"',
        )
        self.assertContains(
            response,
            "data-relationship-person-identification "
            'aria-live="polite" hidden',
        )
        self.assertContains(response, "Dvořáková")
        self.assertNotContains(response, "Skrytá")

    def add_birth(self, person, year, access_level=AccessLevel.PUBLIC):
        event = Event.objects.create(
            event_type=EventType.objects.get(code="birth"),
            access_level=access_level,
            date_precision=DatePrecision.EXACT,
            date_qualifier=DateQualifier.NONE,
            start_year=year,
            start_month=1,
            start_day=1,
        )
        EventParticipant.objects.create(
            event=event,
            person=person,
            role=ParticipantRole.objects.get(code="born_person"),
        )

    def test_picker_distinguishes_namesakes_by_roman_and_birth_year(
        self,
    ) -> None:
        older = Person.objects.create(
            first_name="Josef",
            last_name="Dvořák",
            access_level=AccessLevel.PUBLIC,
        )
        younger = Person.objects.create(
            first_name="Josef",
            last_name="Dvořák",
            access_level=AccessLevel.PUBLIC,
        )
        self.add_birth(older, 1921)
        self.add_birth(younger, 1950)
        self.client.force_login(self.editor())

        response = self.client.get(self.create_url("partner"))

        self.assertContains(response, "Dvořák Josef I. (nar. 1921)")
        self.assertContains(response, "Dvořák Josef II. (nar. 1950)")
        self.assertContains(response, f'value="{older.pk}"')

    def test_picker_label_omits_hidden_birth_year(self) -> None:
        hidden_birth = Person.objects.create(
            first_name="Karel",
            last_name="Skrytý",
            access_level=AccessLevel.PUBLIC,
        )
        self.add_birth(hidden_birth, 1888, AccessLevel.RESTRICTED)
        self.client.force_login(self.editor())

        response = self.client.get(self.create_url("partner"))

        self.assertContains(response, "Skrytý Karel")
        self.assertNotContains(response, "1888")
        self.assertNotContains(response, "Skrytý Karel (nar.")

    def test_invalid_create_keeps_selected_counterpart_in_picker(self) -> None:
        self.client.force_login(self.editor())

        response = self.client.post(
            self.create_url("partner"),
            self.form_data(counterpart=self.third.pk, start_month=13),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="relationship-person-picker"')
        self.assertContains(
            response,
            f'<option value="{self.third.pk}" selected>',
            html=False,
        )
        self.assertFalse(Relationship.objects.exists())

    def test_edit_form_has_no_person_picker(self) -> None:
        relationship = self.relationship()
        self.client.force_login(self.editor())

        response = self.client.get(self.edit_url(relationship))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "relationship-person-picker")
        self.assertNotContains(response, "data-relationship-person-select")
        self.assertNotContains(response, "data-relationship-person-search")

    def test_edit_changes_details_but_never_type_or_participants(self) -> None:
        relationship = self.relationship(note="Původní")
        self.client.force_login(self.editor())

        form = self.client.get(self.edit_url(relationship))
        self.assertContains(form, "Typ vztahu ani zúčastněné osoby nelze měnit")
        self.assertNotContains(form, 'name="counterpart"')
        response = self.client.post(
            self.edit_url(relationship),
            self.form_data(
                counterpart=self.third.pk,
                relationship_type=self.partner_type.pk,
                person_a=self.third.pk,
                person_b=self.third.pk,
                note="Opraveno",
                date_precision=DatePrecision.YEAR,
                date_qualifier=DateQualifier.APPROXIMATE,
                start_year=1890,
                verification_status=VerificationStatus.VERIFIED,
            ),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        relationship.refresh_from_db()
        self.assertEqual(relationship.note, "Opraveno")
        self.assertEqual(relationship.start_year, 1890)
        self.assertEqual(relationship.date_qualifier, DateQualifier.APPROXIMATE)
        self.assertEqual(relationship.relationship_type, self.parent_type)
        self.assertEqual(
            (relationship.person_a, relationship.person_b),
            (self.other, self.person),
        )
        self.assertEqual(Relationship.objects.count(), 1)

    def test_edit_fails_closed_for_unsupported_hidden_or_foreign_edges(
        self,
    ) -> None:
        spouse = self.relationship(
            relationship_type=self.spouse_type,
            person_a=self.person,
            person_b=self.other,
        )
        restricted = self.relationship(
            person_a=self.third,
            access_level=AccessLevel.RESTRICTED,
            note="Tajná poznámka",
        )
        hidden_participant = self.relationship(person_a=self.hidden)
        foreign = self.relationship(person_a=self.other, person_b=self.third)
        deleted = self.relationship(
            relationship_type=self.partner_type,
            person_a=self.person,
            person_b=self.third,
            deleted_at=timezone.now(),
        )
        archived = self.relationship(
            relationship_type=self.partner_type,
            person_a=self.person,
            person_b=self.other,
            archived_at=timezone.now(),
        )
        archived_counterpart = Person.objects.create(
            first_name="Archivní",
            last_name="Rodič",
        )
        archived_counterpart_edge = self.relationship(
            person_a=archived_counterpart,
        )
        Person.objects.filter(pk=archived_counterpart.pk).update(
            archived_at=timezone.now()
        )
        self.client.force_login(self.editor())

        page = self.client.get(
            reverse("people:relationships", args=(self.person.pk,))
        )
        self.assertNotContains(page, self.edit_url(spouse))
        self.assertNotContains(page, self.edit_url(archived_counterpart_edge))
        for relationship in (
            spouse,
            restricted,
            hidden_participant,
            foreign,
            deleted,
            archived,
            archived_counterpart_edge,
        ):
            get_response = self.client.get(self.edit_url(relationship))
            post_response = self.client.post(
                self.edit_url(relationship),
                self.form_data(note="Změna"),
            )
            self.assertEqual(get_response.status_code, 404)
            self.assertEqual(post_response.status_code, 404)
            self.assertNotContains(
                post_response,
                "Tajná poznámka",
                status_code=404,
            )
            relationship.refresh_from_db()
            self.assertNotEqual(relationship.note, "Změna")

    def test_tampered_hidden_access_level_is_refused_over_http(self) -> None:
        relationship = self.relationship(note="Původní")
        self.client.force_login(self.editor())

        create = self.client.post(
            self.create_url("child"),
            self.form_data(
                counterpart=self.third.pk,
                access_level=AccessLevel.RESTRICTED,
            ),
        )
        edit = self.client.post(
            self.edit_url(relationship),
            self.form_data(access_level=AccessLevel.ADMIN_ONLY, note="Změna"),
        )

        self.assertContains(create, "Formulář se nepodařilo uložit")
        self.assertContains(edit, "Formulář se nepodařilo uložit")
        self.assertEqual(Relationship.objects.count(), 1)
        relationship.refresh_from_db()
        self.assertEqual(relationship.access_level, AccessLevel.PUBLIC)
        self.assertEqual(relationship.note, "Původní")

    def test_use_case_rechecks_access_kind_and_revoked_actor(self) -> None:
        actor = self.editor("use-case-editor")
        details = RelationshipDetailsInput(note="Zápis")

        with self.assertRaises(PermissionDenied):
            create_person_relationship(
                person=self.person,
                kind="parent",
                counterpart=self.other,
                data=RelationshipDetailsInput(
                    access_level=AccessLevel.RESTRICTED,
                ),
                actor=actor,
            )
        with self.assertRaisesMessage(Exception, "rodiče, dítě a partnera"):
            create_person_relationship(
                person=self.person,
                kind="spouse",
                counterpart=self.other,
                data=details,
                actor=actor,
            )
        with self.assertRaises(Person.DoesNotExist):
            create_person_relationship(
                person=self.hidden,
                kind="parent",
                counterpart=self.other,
                data=details,
                actor=actor,
            )
        relationship = create_person_relationship(
            person=self.person,
            kind="partner",
            counterpart=self.other,
            data=details,
            actor=actor,
        )
        self.assertEqual(relationship.relationship_type, self.partner_type)

        actor.groups.clear()
        with self.assertRaises(PermissionDenied):
            update_person_relationship(
                person=self.person,
                relationship=relationship,
                data=RelationshipDetailsInput(note="Změna"),
                actor=get_user_model().objects.get(pk=actor.pk),
            )
        relationship.refresh_from_db()
        self.assertEqual(relationship.note, "Zápis")
        self.assertEqual(Relationship.objects.count(), 1)

    def test_archived_person_cannot_be_written(self) -> None:
        relationship = self.relationship()
        Person.objects.filter(pk=self.person.pk).update(
            archived_at=timezone.now()
        )
        admin = get_user_model().objects.create_superuser(
            username="relationship-superuser",
        )
        self.client.force_login(admin)

        page = self.client.get(
            reverse("people:relationships", args=(self.person.pk,))
        )
        create = self.client.post(self.create_url("child"), self.form_data())
        edit = self.client.post(
            self.edit_url(relationship),
            self.form_data(note="Změna"),
        )

        # Archivovaná osoba není v běžném person browseru, proto 404.
        self.assertEqual(page.status_code, 404)
        self.assertEqual(create.status_code, 404)
        self.assertEqual(edit.status_code, 404)
        self.assertEqual(Relationship.objects.count(), 1)

    def test_administrator_sees_buttons_and_creates_parent(self) -> None:
        actor = get_user_model().objects.create_user(
            username="relationship-administrator"
        )
        actor.groups.add(Group.objects.get(name="Správce"))
        self.assertTrue(actor.has_perm("people.add_relationship"))
        self.assertTrue(actor.has_perm("people.change_relationship"))
        self.client.force_login(actor)

        page = self.client.get(
            reverse("people:relationships", args=(self.person.pk,)),
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(page, "Přidat rodiče")
        self.assertContains(page, "Přidat dítě")
        self.assertContains(page, "Přidat partnera")

        response = self.client.post(
            self.create_url("parent"),
            self.form_data(),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        relationship = Relationship.objects.get()
        self.assertEqual(relationship.relationship_type, self.parent_type)
        self.assertEqual(relationship.person_a, self.other)
        self.assertEqual(relationship.person_b, self.person)
        self.assertEqual(relationship.created_by, actor)

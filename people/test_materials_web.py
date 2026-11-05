from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfWriter

from common.choices import AccessLevel
from materials.choices import AttachmentPrivacyStatus, FileStatus
from materials.models import (
    Attachment,
    AttachmentCategory,
    AttachmentRole,
    PersonAttachment,
)
from materials.services import get_or_create_owned_vault

from .models import Person


class PersonMaterialsWebTests(TestCase):
    def setUp(self) -> None:
        self.owner = get_user_model().objects.create_user(
            username="materials-owner",
        )
        self.vault = get_or_create_owned_vault(owner=self.owner)
        self.category = AttachmentCategory.objects.create(
            code="person-material-document",
            name="Dokument",
        )
        self.role = AttachmentRole.objects.create(
            code="person-material-evidence",
            name="Doklad",
        )
        self.person = Person.objects.create(
            first_name="Anna",
            last_name="Nováková",
        )

    def create_link(
        self,
        *,
        privacy_status: str = AttachmentPrivacyStatus.STANDARD,
        marker: str = "a",
    ) -> PersonAttachment:
        attachment = Attachment.objects.create(
            vault=self.vault,
            category=self.category,
            display_name=f"Rodinná kronika {marker}",
            description=f"Bezpečný popis {marker}",
            original_filename=f"kronika-{marker}.pdf",
            storage_key=marker * 64,
            mime_type="application/pdf",
            size_bytes=2048,
            sha256=marker * 64,
            file_status=FileStatus.AVAILABLE,
            privacy_status=privacy_status,
        )
        return PersonAttachment.objects.create(
            person=self.person,
            attachment=attachment,
            role=self.role,
            context_description=f"Vazba k osobě {marker}",
        )

    def test_lists_visible_attachment_with_basic_metadata(self) -> None:
        self.create_link()

        response = self.client.get(
            reverse("people:materials", args=(self.person.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rodinná kronika a")
        self.assertContains(response, "application/pdf")
        self.assertContains(response, "Bezpečný popis a")
        self.assertContains(response, "Dokument")
        self.assertContains(response, "Doklad")

    def test_empty_person_uses_materials_empty_state(self) -> None:
        response = self.client.get(
            reverse("people:materials", args=(self.person.pk,))
        )

        self.assertContains(
            response,
            "K této osobě zatím nejsou dostupné žádné materiály.",
        )

    def test_private_attachment_metadata_is_absent_for_unauthorized_actor(
        self,
    ) -> None:
        self.create_link(
            privacy_status=AttachmentPrivacyStatus.PRIVATE,
            marker="b",
        )

        response = self.client.get(
            reverse("people:materials", args=(self.person.pk,))
        )

        self.assertContains(
            response,
            "K této osobě zatím nejsou dostupné žádné materiály.",
        )
        self.assertNotContains(response, "Rodinná kronika b")
        self.assertNotContains(response, "kronika-b.pdf")
        self.assertNotContains(response, "Bezpečný popis b")
        self.assertNotContains(response, "Vazba k osobě b")

    def test_actions_use_contextual_m34_delivery_urls(self) -> None:
        link = self.create_link()
        open_url = reverse(
            "materials:open-attachment",
            args=("person", self.person.pk, link.pk),
        )
        download_url = reverse(
            "materials:download-attachment",
            args=("person", self.person.pk, link.pk),
        )

        response = self.client.get(
            reverse("people:materials", args=(self.person.pk,))
        )

        self.assertContains(response, f'href="{open_url}"')
        self.assertContains(response, f'href="{download_url}"')
        self.assertContains(response, "Otevřít")
        self.assertContains(response, "Stáhnout")

    def test_htmx_returns_active_materials_fragment(self) -> None:
        response = self.client.get(
            reverse("people:materials", args=(self.person.pk,)),
            headers={"HX-Request": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "people/partials/person_materials.html",
        )
        self.assertNotContains(response, "Seznam osob")
        self.assertEqual(response.context["active_person_tab"], "materials")
        self.assertContains(response, 'class="person-tab is-active"')
        self.assertContains(response, 'aria-current="page"')

    def test_upload_action_is_hidden_and_direct_request_is_denied(self) -> None:
        response = self.client.get(
            reverse("people:materials", args=(self.person.pk,))
        )

        self.assertNotContains(response, "Přidat přílohu")
        denied = self.client.get(
            reverse(
                "people:material-attachment-create",
                args=(self.person.pk,),
            )
        )
        self.assertEqual(denied.status_code, 403)


class PersonAttachmentUploadWebTests(TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.settings_override = override_settings(
            PROTECTED_ATTACHMENTS_ROOT=self.temporary_directory.name,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.actor = get_user_model().objects.create_user(
            username="materials-person-editor"
        )
        self.actor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="people",
                codename="change_person",
            )
        )
        self.person = Person.objects.create(
            first_name="Božena",
            last_name="Němcová",
        )
        self.category = AttachmentCategory.objects.create(
            code="web-person-document",
            name="Dokument",
        )
        self.role = AttachmentRole.objects.create(
            code="web-person-evidence",
            name="Doklad",
        )
        self.client.force_login(self.actor)

    def test_htmx_upload_refreshes_list_with_delivery_actions(self) -> None:
        response = self.client.post(
            reverse(
                "people:material-attachment-create",
                args=(self.person.pk,),
            ),
            data={
                "file": SimpleUploadedFile(
                    "rodokmen.pdf",
                    self.pdf(),
                    content_type="application/pdf",
                ),
                "display_name": "Rodokmen rodiny",
                "description": "Ověřený rodinný dokument",
                "category": self.category.pk,
                "role": self.role.pk,
                "access_level": AccessLevel.AUTHENTICATED,
            },
            headers={"HX-Request": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["HX-Push-Url"],
            reverse("people:materials", args=(self.person.pk,)),
        )
        link = PersonAttachment.objects.select_related("attachment").get()
        self.assertEqual(link.access_level, AccessLevel.AUTHENTICATED)
        self.assertEqual(link.attachment.access_level, link.access_level)
        self.assertEqual(link.attachment.vault.owner, self.actor)
        self.assertContains(response, "Příloha byla nahrána a připojena.")
        self.assertContains(response, "Rodokmen rodiny")
        self.assertContains(
            response,
            reverse(
                "materials:open-attachment",
                args=("person", self.person.pk, link.pk),
            ),
        )
        self.assertContains(
            response,
            reverse(
                "materials:download-attachment",
                args=("person", self.person.pk, link.pk),
            ),
        )

    def test_invalid_form_creates_no_attachment_or_link(self) -> None:
        response = self.client.post(
            reverse(
                "people:material-attachment-create",
                args=(self.person.pk,),
            ),
            data={
                "display_name": "Chybí soubor",
                "category": self.category.pk,
                "role": self.role.pk,
                "access_level": AccessLevel.PUBLIC,
            },
            headers={"HX-Request": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Přílohu se nepodařilo uložit")
        self.assertEqual(Attachment.objects.count(), 0)
        self.assertEqual(PersonAttachment.objects.count(), 0)

    def test_upload_form_exposes_file_constraints_accessibly(self) -> None:
        response = self.client.get(
            reverse(
                "people:material-attachment-create",
                args=(self.person.pk,),
            )
        )

        self.assertContains(
            response,
            'accept="application/pdf,image/jpeg,image/png,.pdf,.jpg,.jpeg,.png"',
        )
        self.assertContains(response, 'aria-describedby="id_file_helptext"')
        self.assertContains(response, 'id="id_file_helptext"')
        self.assertContains(response, "Maximální velikost 25 MiB")

    def test_empty_catalogs_hide_action_and_explain_unavailable_upload(self):
        self.category.delete()
        self.role.delete()

        materials_response = self.client.get(
            reverse("people:materials", args=(self.person.pk,))
        )
        self.assertNotContains(materials_response, "Přidat přílohu")
        self.assertContains(
            materials_response,
            "Nahrávání příloh bude dostupné po nastavení aktivní kategorie",
        )

        form_response = self.client.get(
            reverse(
                "people:material-attachment-create",
                args=(self.person.pk,),
            )
        )
        self.assertContains(
            form_response,
            "Nahrávání příloh není dostupné",
        )
        self.assertNotContains(form_response, "Nahrát přílohu")

    @staticmethod
    def pdf() -> bytes:
        stream = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.write(stream)
        return stream.getvalue()

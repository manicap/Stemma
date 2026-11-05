from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from PIL import Image

from people.models import Person

from .models import PersonAttachment


class AttachmentDeliveryBootstrapTests(TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.settings_override = override_settings(
            DEBUG=True,
            PROTECTED_ATTACHMENTS_ROOT=self.temporary_directory.name,
            PROTECTED_ATTACHMENTS_FILE_PERMISSIONS=0o600,
            PROTECTED_ATTACHMENTS_DIRECTORY_PERMISSIONS=0o700,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.owner = get_user_model().objects.create_user(
            username="local-delivery-owner",
        )
        self.person = Person.objects.create(first_name="Anna")
        self.file_path = Path(self.temporary_directory.name) / "doklad.png"
        image = Image.new("RGB", (2, 2), "white")
        image.save(self.file_path, format="PNG")

    def test_command_creates_real_private_delivery_flow(self) -> None:
        output = StringIO()

        call_command(
            "bootstrap_attachment_delivery",
            str(self.file_path),
            owner=self.owner.username,
            person_id=self.person.pk,
            stdout=output,
        )

        link = PersonAttachment.objects.select_related("attachment").get()
        self.assertNotIn(link.attachment.storage_key, output.getvalue())
        self.assertIn(f"/vazby/{link.pk}/otevrit/", output.getvalue())
        self.assertIn(f"/vazby/{link.pk}/stahnout/", output.getvalue())
        self.client.force_login(self.owner)
        response = self.client.get(
            f"/materialy/person/{self.person.pk}/vazby/{link.pk}/otevrit/"
        )
        self.assertEqual(response.status_code, 200)
        delivered = b"".join(response.streaming_content)
        self.assertTrue(delivered.startswith(b"\x89PNG\r\n\x1a\n"))

    @override_settings(DEBUG=False)
    def test_command_is_disabled_outside_debug(self) -> None:
        with self.assertRaisesMessage(CommandError, "DEBUG režimu"):
            call_command(
                "bootstrap_attachment_delivery",
                str(self.file_path),
                owner=self.owner.username,
                person_id=self.person.pk,
            )

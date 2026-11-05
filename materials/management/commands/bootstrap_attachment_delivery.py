"""Create one local protected attachment flow for manual M3.4 verification."""

from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse

from people.models import Person

from materials.choices import AttachmentPrivacyStatus
from materials.models import AttachmentCategory, AttachmentRole
from materials.services import AttachmentLinkInput, create_person_attachment
from materials.upload_services import AttachmentUploadInput, upload_attachment

_MIME_BY_SUFFIX = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


class Command(BaseCommand):
    help = (
        "Vytvoří lokální fyzickou přílohu osoby a vypíše M3.4 delivery URL."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("file_path")
        parser.add_argument("--owner", required=True)
        parser.add_argument("--person-id", required=True, type=int)
        parser.add_argument(
            "--privacy",
            choices=AttachmentPrivacyStatus.values,
            default=AttachmentPrivacyStatus.PRIVATE,
        )

    def handle(self, *args, **options) -> None:
        if not settings.DEBUG:
            raise CommandError(
                "Delivery bootstrap lze použít pouze v lokálním DEBUG režimu."
            )
        file_path = Path(options["file_path"]).resolve()
        mime_type = _MIME_BY_SUFFIX.get(file_path.suffix.lower())
        if mime_type is None or not file_path.is_file():
            raise CommandError("Zadejte existující PDF, JPEG nebo PNG soubor.")

        user_model = get_user_model()
        try:
            owner = user_model._default_manager.get(
                username=options["owner"],
                is_active=True,
            )
        except user_model.DoesNotExist as error:
            raise CommandError("Aktivní vlastník nebyl nalezen.") from error
        try:
            person = Person.objects.get(
                pk=options["person_id"],
                archived_at__isnull=True,
                deleted_at__isnull=True,
            )
        except Person.DoesNotExist as error:
            raise CommandError("Aktivní osoba nebyla nalezena.") from error

        category, _ = AttachmentCategory.objects.get_or_create(
            code="stemma_local_delivery_document",
            defaults={"name": "Lokální ověření doručení"},
        )
        role, _ = AttachmentRole.objects.get_or_create(
            code="stemma_local_delivery_evidence",
            defaults={"name": "Lokální testovací doklad"},
        )
        if not category.is_active or not role.is_active:
            raise CommandError(
                "Lokální delivery kategorie nebo role není aktivní."
            )

        with file_path.open("rb") as source:
            attachment = upload_attachment(
                actor=owner,
                data=AttachmentUploadInput(
                    category=category,
                    original_filename=file_path.name,
                    declared_mime_type=mime_type,
                    privacy_status=options["privacy"],
                ),
                stream=source,
            )
        link = create_person_attachment(
            person=person,
            data=AttachmentLinkInput(
                attachment=attachment,
                role=role,
                context_description="Lokální ověření M3.4.",
            ),
            created_by=owner,
        )
        route_kwargs = {
            "context_type": "person",
            "context_id": person.pk,
            "link_id": link.pk,
        }
        self.stdout.write(
            self.style.SUCCESS("Lokální delivery příloha byla vytvořena.")
        )
        self.stdout.write(
            f"Otevření: {reverse('materials:open-attachment', kwargs=route_kwargs)}"
        )
        self.stdout.write(
            "Stažení: "
            f"{reverse('materials:download-attachment', kwargs=route_kwargs)}"
        )

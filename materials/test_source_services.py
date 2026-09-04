from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from .choices import SourceSupport
from .models import (
    Attachment,
    AttachmentCategory,
    AttachmentSource,
    Source,
    SourceRole,
    SourceType,
)
from .source_services import (
    SourceLinkInput,
    create_attachment_source,
    update_attachment_source,
)
from . import source_services


class SourceLinkServiceApiTests(SimpleTestCase):
    def test_public_api_exposes_all_six_create_and_update_pairs(self) -> None:
        self.assertEqual(
            set(source_services.__all__),
            {
                "SourceLinkInput",
                "create_attachment_source",
                "create_event_source",
                "create_grave_site_source",
                "create_health_record_source",
                "create_person_name_source",
                "create_relationship_source",
                "create_residence_source",
                "update_attachment_source",
                "update_event_source",
                "update_grave_site_source",
                "update_health_record_source",
                "update_person_name_source",
                "update_relationship_source",
                "update_residence_source",
            },
        )


class SourceLinkServiceTests(TestCase):
    def setUp(self) -> None:
        source_type = SourceType.objects.create(code="archive", name="Archiv")
        self.role = SourceRole.objects.create(code="evidence", name="Doklad")
        self.source = Source.objects.create(
            source_type=source_type,
            title="Matrika",
        )
        category = AttachmentCategory.objects.create(code="scan", name="Sken")
        self.attachment = Attachment.objects.create(
            category=category,
            original_filename="scan.pdf",
            storage_key="attachments/service-source.pdf",
            mime_type="application/pdf",
            size_bytes=1,
            sha256="b" * 64,
        )

    def data(self, **overrides) -> SourceLinkInput:
        values = {
            "source": self.source,
            "role": self.role,
            "support_strength": SourceSupport.CONFIRMS,
            "cited_part": "  fol. 12  ",
            "excerpt": "  Krátký úryvek  ",
            "interpretation": "  Výklad  ",
        }
        values.update(overrides)
        return SourceLinkInput(**values)

    def assert_code(
        self, exception: ValidationError, field: str, code: str,
    ) -> None:
        self.assertEqual(exception.error_dict[field][0].code, code)

    def test_create_reloads_endpoints_and_normalizes_context(self) -> None:
        stale_source = Source.objects.get(pk=self.source.pk)
        self.source.title = "Změněná matrika"
        self.source.save(update_fields={"title"})

        link = create_attachment_source(
            attachment=self.attachment,
            data=self.data(source=stale_source),
        )

        self.assertEqual(link.source.title, "Změněná matrika")
        self.assertEqual(link.cited_part, "fol. 12")
        self.assertEqual(link.excerpt, "Krátký úryvek")
        self.assertEqual(link.interpretation, "Výklad")

    def test_create_rejects_archived_deleted_and_inactive_endpoints(self) -> None:
        cases = (
            ("source", "archived_at", "source_archived"),
            ("attachment", "deleted_at", "attachment_deleted"),
            ("role", "is_active", "role_inactive"),
        )
        for endpoint, attribute, code in cases:
            with self.subTest(endpoint=endpoint):
                value = getattr(self, endpoint)
                changed_value = (
                    False if attribute == "is_active" else timezone.now()
                )
                setattr(value, attribute, changed_value)
                value.save(update_fields={attribute})
                with self.assertRaises(ValidationError) as context:
                    create_attachment_source(
                        attachment=self.attachment,
                        data=self.data(),
                    )
                self.assert_code(context.exception, endpoint, code)
                setattr(value, attribute, True if attribute == "is_active" else None)
                value.save(update_fields={attribute})

    def test_update_preserves_same_archived_endpoints_and_inactive_role(self) -> None:
        link = create_attachment_source(
            attachment=self.attachment,
            data=self.data(),
        )
        now = timezone.now()
        self.source.archived_at = now
        self.source.save(update_fields={"archived_at"})
        self.attachment.archived_at = now
        self.attachment.save(update_fields={"archived_at"})
        self.role.is_active = False
        self.role.save(update_fields={"is_active"})
        AttachmentSource.objects.filter(pk=link.pk).update(archived_at=now)

        updated = update_attachment_source(
            link=link,
            attachment=self.attachment,
            data=self.data(cited_part="  změna  "),
        )

        self.assertEqual(updated.cited_part, "změna")
        self.assertEqual(updated.archived_at, now)

    def test_update_rejects_deleted_link_from_current_database_state(self) -> None:
        link = create_attachment_source(
            attachment=self.attachment,
            data=self.data(),
        )
        AttachmentSource.objects.filter(pk=link.pk).update(
            deleted_at=timezone.now()
        )

        with self.assertRaises(ValidationError) as context:
            update_attachment_source(
                link=link,
                attachment=self.attachment,
                data=self.data(),
            )

        self.assert_code(context.exception, "link", "source_link_deleted")

    def test_invalid_support_strength_uses_model_validation(self) -> None:
        with self.assertRaises(ValidationError) as context:
            create_attachment_source(
                attachment=self.attachment,
                data=self.data(support_strength="unknown"),
            )

        self.assert_code(context.exception, "support_strength", "invalid_choice")

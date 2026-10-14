from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.checks import run_checks
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from .services import get_or_create_owned_vault
from .storage import ProtectedAttachmentStorage, ProtectedStorageError


class ProtectedAttachmentStorageTests(TestCase):
    key = "a" * 64

    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.settings_override = override_settings(
            PROTECTED_ATTACHMENTS_ROOT=self.temporary_directory.name,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        owner = get_user_model().objects.create_user(username="storage-owner")
        self.vault = get_or_create_owned_vault(owner=owner)
        self.storage = ProtectedAttachmentStorage()

    def test_write_open_delete_round_trip(self) -> None:
        self.storage.write(self.vault, self.key, BytesIO(b"protected"))

        self.assertTrue(self.storage.exists(self.vault, self.key))
        with self.storage.open(self.vault, self.key) as stored:
            self.assertEqual(stored.read(), b"protected")

        self.storage.delete(self.vault, self.key)
        self.assertFalse(self.storage.exists(self.vault, self.key))

    def test_same_key_is_isolated_by_vault(self) -> None:
        other_owner = get_user_model().objects.create_user(
            username="other-storage-owner"
        )
        other_vault = get_or_create_owned_vault(owner=other_owner)

        self.storage.write(self.vault, self.key, BytesIO(b"first"))
        self.storage.write(other_vault, self.key, BytesIO(b"second"))

        with self.storage.open(self.vault, self.key) as first:
            self.assertEqual(first.read(), b"first")
        with self.storage.open(other_vault, self.key) as second:
            self.assertEqual(second.read(), b"second")

    def test_public_url_and_path_are_not_exposed(self) -> None:
        self.assertFalse(hasattr(self.storage, "url"))
        self.assertFalse(hasattr(self.storage, "path"))
        with self.assertRaises(ProtectedStorageError):
            self.storage._storage.url("anything")

    def test_public_directory_overlap_is_rejected_fail_closed(self) -> None:
        private_root = self.temporary_directory.name
        overlapping_roots = (
            {"MEDIA_ROOT": private_root},
            {"STATIC_ROOT": private_root},
            {"STATICFILES_DIRS": [private_root]},
            {"MEDIA_ROOT": f"{private_root}/public"},
            {
                "PROTECTED_ATTACHMENTS_ROOT": f"{private_root}/nested",
                "MEDIA_ROOT": private_root,
            },
        )

        for overridden_settings in overlapping_roots:
            with self.subTest(overridden_settings=overridden_settings):
                with (
                    override_settings(**overridden_settings),
                    self.assertRaises(ImproperlyConfigured),
                ):
                    ProtectedAttachmentStorage()

    def test_system_check_reports_public_directory_overlap(self) -> None:
        with override_settings(MEDIA_ROOT=self.temporary_directory.name):
            errors = run_checks(tags=["security"])

        self.assertIn("materials.E001", {error.id for error in errors})

    def test_invalid_key_and_unsaved_vault_are_rejected(self) -> None:
        for invalid in ("", "../escape", "A" * 64, "a" * 63):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ProtectedStorageError):
                    self.storage.write(
                        self.vault,
                        invalid,
                        BytesIO(b"content"),
                    )

        with self.assertRaises(ProtectedStorageError):
            self.storage.write(
                type(self.vault)(),
                self.key,
                BytesIO(b"content"),
            )

    def test_collision_preserves_existing_blob(self) -> None:
        self.storage.write(self.vault, self.key, BytesIO(b"original"))

        with self.assertRaises(ProtectedStorageError):
            self.storage.write(self.vault, self.key, BytesIO(b"replacement"))

        with self.storage.open(self.vault, self.key) as stored:
            self.assertEqual(stored.read(), b"original")

    def test_partial_write_is_cleaned_up(self) -> None:
        original_save = self.storage._storage.save

        def save_then_fail(name, content, max_length=None):
            original_save(name, content, max_length=max_length)
            raise OSError("private filesystem detail")

        with (
            patch.object(
                self.storage._storage,
                "save",
                side_effect=save_then_fail,
            ),
            self.assertRaises(ProtectedStorageError) as context,
        ):
            self.storage.write(self.vault, self.key, BytesIO(b"partial"))

        self.assertFalse(self.storage.exists(self.vault, self.key))
        self.assertNotIn("filesystem", str(context.exception))

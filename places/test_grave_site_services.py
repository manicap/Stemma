from dataclasses import FrozenInstanceError, fields, replace
from datetime import timedelta
from decimal import Decimal
from inspect import Parameter, signature
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from common.choices import AccessLevel, VerificationStatus
from events.models import Event

from . import services
from .choices import GraveSiteStatus
from .models import (
    GraveSite,
    GraveSiteType,
    PersonGraveSite,
    Place,
)
from .services import (
    GraveSiteInput,
    create_grave_site,
    update_grave_site,
)


class GraveSiteServiceApiTests(SimpleTestCase):
    """Ověření veřejného kontraktu služeb hrobových míst."""

    def test_module_exports_exact_approved_api(self) -> None:
        self.assertEqual(
            services.__all__,
            (
                "GraveSiteInput",
                "ResidenceInput",
                "create_grave_site",
                "create_residence",
                "update_grave_site",
                "update_residence",
            ),
        )

    def test_input_is_frozen_slotted_dataclass(self) -> None:
        data = GraveSiteInput(grave_site_type=GraveSiteType())

        self.assertFalse(hasattr(data, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            data.note = "Změna"

    def test_input_has_exact_fields_in_order(self) -> None:
        self.assertEqual(
            tuple(field.name for field in fields(GraveSiteInput)),
            (
                "grave_site_type",
                "status",
                "place",
                "location_text",
                "cemetery_name",
                "section",
                "row",
                "grave_number",
                "inscription",
                "latitude",
                "longitude",
                "note",
                "access_level",
                "verification_status",
            ),
        )

    def test_input_defaults_match_contract(self) -> None:
        data = GraveSiteInput(grave_site_type=GraveSiteType())

        self.assertEqual(data.status, GraveSiteStatus.UNKNOWN)
        self.assertIsNone(data.place)
        for field_name in (
            "location_text",
            "cemetery_name",
            "section",
            "row",
            "grave_number",
            "inscription",
            "note",
        ):
            with self.subTest(field_name=field_name):
                self.assertEqual(getattr(data, field_name), "")
        self.assertIsNone(data.latitude)
        self.assertIsNone(data.longitude)
        self.assertEqual(data.access_level, AccessLevel.PUBLIC)
        self.assertEqual(
            data.verification_status,
            VerificationStatus.UNCONFIRMED,
        )

    def test_coordinate_annotations_are_decimal_or_none(self) -> None:
        self.assertEqual(
            GraveSiteInput.__annotations__["latitude"],
            Decimal | None,
        )
        self.assertEqual(
            GraveSiteInput.__annotations__["longitude"],
            Decimal | None,
        )

    def test_service_signatures_are_keyword_only_with_return_type(
        self,
    ) -> None:
        expectations = (
            (create_grave_site, ("data", "created_by")),
            (update_grave_site, ("grave_site", "data")),
        )
        for service, parameter_names in expectations:
            with self.subTest(service=service.__name__):
                service_signature = signature(service)
                self.assertEqual(
                    tuple(service_signature.parameters),
                    parameter_names,
                )
                self.assertTrue(
                    all(
                        parameter.kind is Parameter.KEYWORD_ONLY
                        for parameter in service_signature.parameters.values()
                    )
                )
                self.assertIs(
                    service_signature.return_annotation,
                    GraveSite,
                )


class GraveSiteServiceTests(TestCase):
    """Integrační testy vytvoření a změny hrobového místa."""

    def setUp(self) -> None:
        self.grave_site_type = self.make_type("service_grave")
        self.other_type = self.make_type("service_memorial")
        self.place = self.make_place("Praha")
        self.other_place = self.make_place("Brno")

    @staticmethod
    def make_type(
        code: str,
        *,
        is_active: bool = True,
    ) -> GraveSiteType:
        return GraveSiteType.objects.create(
            code=code,
            name=code,
            is_active=is_active,
        )

    @staticmethod
    def make_place(name: str) -> Place:
        return Place.objects.create(
            name=name,
            normalized_name=name.casefold(),
        )

    def make_data(self, **changes: object) -> GraveSiteInput:
        data = GraveSiteInput(
            grave_site_type=self.grave_site_type,
            location_text="Základní lokalita",
        )
        return replace(data, **changes)

    def create_base_grave_site(self, **changes: object) -> GraveSite:
        return create_grave_site(data=self.make_data(**changes))

    @staticmethod
    def assert_error(
        context,
        *,
        key: str,
        code: str,
    ) -> None:
        errors = context.exception.error_dict
        if key not in errors:
            raise AssertionError(f"Chybí očekávaný klíč {key!r}: {errors}")
        codes = [error.code for error in errors[key]]
        if code not in codes:
            raise AssertionError(
                f"Chybí očekávaný kód {code!r} v {key!r}: {codes}"
            )

    def test_create_accepts_all_localization_variants(self) -> None:
        variants = (
            self.make_data(place=self.place, location_text=""),
            self.make_data(location_text="Textová lokalita"),
            self.make_data(location_text="", cemetery_name="Hřbitov"),
            self.make_data(
                location_text="",
                latitude=Decimal("50.000001"),
                longitude=Decimal("14.000001"),
            ),
            self.make_data(
                place=self.place,
                location_text="Detail místa",
                cemetery_name="Městský hřbitov",
                latitude=Decimal("50.000001"),
                longitude=Decimal("14.000001"),
            ),
        )

        for data in variants:
            with self.subTest(data=data):
                self.assertIsInstance(
                    create_grave_site(data=data),
                    GraveSite,
                )
        self.assertEqual(GraveSite.objects.count(), len(variants))

    def test_create_stores_all_values_and_created_by(self) -> None:
        creator = get_user_model().objects.create_user(
            username="grave-site-creator"
        )
        data = self.make_data(
            grave_site_type=self.other_type,
            status=GraveSiteStatus.EXISTING,
            place=self.other_place,
            location_text="Historická lokalita",
            cemetery_name="Městský hřbitov",
            section="III/A",
            row="B-2",
            grave_number="127a/1",
            inscription="Přepis nápisu",
            latitude=Decimal("50.123456"),
            longitude=Decimal("14.654321"),
            note="Doložené místo",
            access_level=AccessLevel.RESTRICTED,
            verification_status=VerificationStatus.VERIFIED,
        )

        result = create_grave_site(data=data, created_by=creator)

        self.assertEqual(result.grave_site_type_id, self.other_type.pk)
        self.assertEqual(result.status, GraveSiteStatus.EXISTING)
        self.assertEqual(result.place_id, self.other_place.pk)
        self.assertEqual(result.location_text, "Historická lokalita")
        self.assertEqual(result.cemetery_name, "Městský hřbitov")
        self.assertEqual(result.section, "III/A")
        self.assertEqual(result.row, "B-2")
        self.assertEqual(result.grave_number, "127a/1")
        self.assertEqual(result.inscription, "Přepis nápisu")
        self.assertEqual(result.latitude, Decimal("50.123456"))
        self.assertEqual(result.longitude, Decimal("14.654321"))
        self.assertEqual(result.note, "Doložené místo")
        self.assertEqual(result.access_level, AccessLevel.RESTRICTED)
        self.assertEqual(
            result.verification_status,
            VerificationStatus.VERIFIED,
        )
        self.assertEqual(result.created_by_id, creator.pk)

    def test_create_uses_defaults_and_returns_fresh_instance(self) -> None:
        result = self.create_base_grave_site()

        self.assertFalse(result._state.adding)
        self.assertEqual(result.status, GraveSiteStatus.UNKNOWN)
        self.assertEqual(result.access_level, AccessLevel.PUBLIC)
        self.assertEqual(
            result.verification_status,
            VerificationStatus.UNCONFIRMED,
        )
        self.assertIsNone(result.created_by_id)
        self.assertIsNone(result.archived_at)
        self.assertIsNone(result.deleted_at)
        self.assertEqual(
            set(result._state.fields_cache),
            {"grave_site_type", "place", "created_by"},
        )

    def test_service_strips_only_outer_text_whitespace(self) -> None:
        result = create_grave_site(
            data=self.make_data(
                location_text="  Stará   lokalita  ",
                cemetery_name="  Městský   hřbitov  ",
                section="  III / A  ",
                row="  B - 2  ",
                grave_number="  127 a  ",
                inscription="  Zde   odpočívá  ",
                note="  dvě   mezery  ",
            )
        )

        self.assertEqual(result.location_text, "Stará   lokalita")
        self.assertEqual(result.cemetery_name, "Městský   hřbitov")
        self.assertEqual(result.section, "III / A")
        self.assertEqual(result.row, "B - 2")
        self.assertEqual(result.grave_number, "127 a")
        self.assertEqual(result.inscription, "Zde   odpočívá")
        self.assertEqual(result.note, "dvě   mezery")

    def test_model_save_outside_service_does_not_strip_text(self) -> None:
        grave_site = GraveSite.objects.create(
            grave_site_type=self.grave_site_type,
            location_text="  Beze změny  ",
            cemetery_name="  Hřbitov  ",
            section="  A  ",
            row="  B  ",
            grave_number="  1  ",
            inscription="  Nápis  ",
            note="  Poznámka  ",
        )
        grave_site.refresh_from_db()

        self.assertEqual(grave_site.location_text, "  Beze změny  ")
        self.assertEqual(grave_site.cemetery_name, "  Hřbitov  ")
        self.assertEqual(grave_site.section, "  A  ")
        self.assertEqual(grave_site.row, "  B  ")
        self.assertEqual(grave_site.grave_number, "  1  ")
        self.assertEqual(grave_site.inscription, "  Nápis  ")
        self.assertEqual(grave_site.note, "  Poznámka  ")

    def test_create_location_error_rolls_back(self) -> None:
        with self.assertRaises(ValidationError) as context:
            create_grave_site(
                data=self.make_data(
                    place=None,
                    location_text=" \t ",
                    cemetery_name=" ",
                )
            )

        self.assert_error(
            context,
            key="location_text",
            code="grave_site_location_required",
        )
        self.assertEqual(GraveSite.objects.count(), 0)

    def test_update_location_error_rolls_back(self) -> None:
        grave_site = self.create_base_grave_site(
            location_text="Původní lokalita",
            note="Původní poznámka",
        )
        original_updated_at = grave_site.updated_at

        with self.assertRaises(ValidationError) as context:
            update_grave_site(
                grave_site=grave_site,
                data=self.make_data(
                    place=None,
                    location_text=" ",
                    cemetery_name="\t",
                    note="Nová poznámka",
                ),
            )

        self.assert_error(
            context,
            key="location_text",
            code="grave_site_location_required",
        )
        grave_site.refresh_from_db()
        self.assertEqual(grave_site.location_text, "Původní lokalita")
        self.assertEqual(grave_site.note, "Původní poznámka")
        self.assertEqual(grave_site.updated_at, original_updated_at)

    def test_coordinate_boundaries_are_allowed(self) -> None:
        for latitude, longitude in (
            (Decimal("-90"), Decimal("-180")),
            (Decimal("90"), Decimal("180")),
        ):
            with self.subTest(latitude=latitude, longitude=longitude):
                result = create_grave_site(
                    data=self.make_data(
                        location_text="",
                        latitude=latitude,
                        longitude=longitude,
                    )
                )
                self.assertEqual(result.latitude, latitude)
                self.assertEqual(result.longitude, longitude)

    def test_invalid_coordinates_preserve_model_codes_and_roll_back(
        self,
    ) -> None:
        variants = (
            (
                {"latitude": Decimal("50"), "longitude": None},
                "longitude",
                "grave_site_coordinates_incomplete",
            ),
            (
                {"latitude": None, "longitude": Decimal("14")},
                "latitude",
                "grave_site_coordinates_incomplete",
            ),
            (
                {"latitude": Decimal("-90.000001"), "longitude": Decimal("0")},
                "latitude",
                "grave_site_latitude_out_of_range",
            ),
            (
                {"latitude": Decimal("90.000001"), "longitude": Decimal("0")},
                "latitude",
                "grave_site_latitude_out_of_range",
            ),
            (
                {"latitude": Decimal("0"), "longitude": Decimal("-180.000001")},
                "longitude",
                "grave_site_longitude_out_of_range",
            ),
            (
                {"latitude": Decimal("0"), "longitude": Decimal("180.000001")},
                "longitude",
                "grave_site_longitude_out_of_range",
            ),
        )

        for coordinates, key, code in variants:
            with self.subTest(coordinates=coordinates):
                with self.assertRaises(ValidationError) as context:
                    create_grave_site(
                        data=self.make_data(**coordinates)
                    )
                self.assert_error(context, key=key, code=code)
        self.assertEqual(GraveSite.objects.count(), 0)

    def test_update_can_replace_and_remove_coordinates(self) -> None:
        grave_site = self.create_base_grave_site(
            latitude=Decimal("50.100000"),
            longitude=Decimal("14.100000"),
        )

        replaced = update_grave_site(
            grave_site=grave_site,
            data=self.make_data(
                latitude=Decimal("49.200000"),
                longitude=Decimal("15.300000"),
            ),
        )
        self.assertEqual(replaced.latitude, Decimal("49.200000"))
        self.assertEqual(replaced.longitude, Decimal("15.300000"))

        removed = update_grave_site(
            grave_site=replaced,
            data=self.make_data(latitude=None, longitude=None),
        )
        self.assertIsNone(removed.latitude)
        self.assertIsNone(removed.longitude)

    def test_invalid_coordinate_update_rolls_back(self) -> None:
        grave_site = self.create_base_grave_site(
            latitude=Decimal("50.100000"),
            longitude=Decimal("14.100000"),
        )
        original_updated_at = grave_site.updated_at

        with self.assertRaises(ValidationError) as context:
            update_grave_site(
                grave_site=grave_site,
                data=self.make_data(
                    latitude=Decimal("49.200000"),
                    longitude=None,
                ),
            )

        self.assert_error(
            context,
            key="longitude",
            code="grave_site_coordinates_incomplete",
        )
        grave_site.refresh_from_db()
        self.assertEqual(grave_site.latitude, Decimal("50.100000"))
        self.assertEqual(grave_site.longitude, Decimal("14.100000"))
        self.assertEqual(grave_site.updated_at, original_updated_at)

    def test_valid_statuses_are_stored_without_lifecycle_changes(self) -> None:
        for status in (
            GraveSiteStatus.UNKNOWN,
            GraveSiteStatus.EXISTING,
            GraveSiteStatus.DESTROYED,
        ):
            with self.subTest(status=status):
                result = create_grave_site(
                    data=self.make_data(status=status)
                )
                self.assertEqual(result.status, status)
                self.assertIsNone(result.archived_at)
                self.assertIsNone(result.deleted_at)

    def test_invalid_status_fails_create_and_update(self) -> None:
        with self.assertRaises(ValidationError) as create_context:
            create_grave_site(data=self.make_data(status="invalid"))
        self.assert_error(
            create_context,
            key="status",
            code="invalid_choice",
        )
        self.assertEqual(GraveSite.objects.count(), 0)

        grave_site = self.create_base_grave_site()
        original_updated_at = grave_site.updated_at
        with self.assertRaises(ValidationError) as update_context:
            update_grave_site(
                grave_site=grave_site,
                data=self.make_data(status="invalid"),
            )
        self.assert_error(
            update_context,
            key="status",
            code="invalid_choice",
        )
        grave_site.refresh_from_db()
        self.assertEqual(grave_site.status, GraveSiteStatus.UNKNOWN)
        self.assertEqual(grave_site.updated_at, original_updated_at)

    def test_access_and_verification_defaults_and_explicit_values(
        self,
    ) -> None:
        default = self.create_base_grave_site()
        explicit = create_grave_site(
            data=self.make_data(
                access_level=AccessLevel.ADMIN_ONLY,
                verification_status=VerificationStatus.DISPUTED,
            )
        )

        self.assertEqual(default.access_level, AccessLevel.PUBLIC)
        self.assertEqual(
            default.verification_status,
            VerificationStatus.UNCONFIRMED,
        )
        self.assertEqual(explicit.access_level, AccessLevel.ADMIN_ONLY)
        self.assertEqual(
            explicit.verification_status,
            VerificationStatus.DISPUTED,
        )

    def test_invalid_access_or_verification_rolls_back(self) -> None:
        grave_site = self.create_base_grave_site(note="Původní")
        original_updated_at = grave_site.updated_at

        for field_name in ("access_level", "verification_status"):
            with self.subTest(field_name=field_name):
                with self.assertRaises(ValidationError) as context:
                    update_grave_site(
                        grave_site=grave_site,
                        data=self.make_data(
                            note="Změněná",
                            **{field_name: "invalid"},
                        ),
                    )
                self.assert_error(
                    context,
                    key=field_name,
                    code="invalid_choice",
                )
                grave_site.refresh_from_db()
                self.assertEqual(grave_site.note, "Původní")
                self.assertEqual(
                    grave_site.updated_at,
                    original_updated_at,
                )

    def test_rejects_unsaved_and_physically_missing_type(self) -> None:
        unsaved = GraveSiteType(code="unsaved", name="Neuložený")
        missing = self.make_type("missing_type")
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        for grave_site_type in (unsaved, missing):
            with self.subTest(grave_site_type=grave_site_type.code):
                with self.assertRaises(ValidationError) as context:
                    create_grave_site(
                        data=self.make_data(
                            grave_site_type=grave_site_type
                        )
                    )
                self.assert_error(
                    context,
                    key="grave_site_type",
                    code="grave_site_type_unsaved",
                )

    def test_rejects_unsaved_and_physically_missing_place(self) -> None:
        unsaved = Place(name="Neuložené", normalized_name="neulozene")
        missing = self.make_place("Odstraněné")
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        for place in (unsaved, missing):
            with self.subTest(place=place.name):
                with self.assertRaises(ValidationError) as context:
                    create_grave_site(data=self.make_data(place=place))
                self.assert_error(
                    context,
                    key="place",
                    code="grave_site_place_unsaved",
                )

    def test_rejects_unsaved_and_physically_missing_created_by(
        self,
    ) -> None:
        user_model = get_user_model()
        unsaved = user_model(username="unsaved-grave-author")
        missing = user_model.objects.create_user(
            username="missing-grave-author"
        )
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        for creator in (unsaved, missing):
            with self.subTest(username=creator.username):
                with self.assertRaises(ValidationError) as context:
                    create_grave_site(
                        data=self.make_data(),
                        created_by=creator,
                    )
                self.assert_error(
                    context,
                    key="created_by",
                    code="grave_site_created_by_unsaved",
                )

    def test_create_uses_fresh_inactive_type_state(self) -> None:
        GraveSiteType.objects.filter(pk=self.grave_site_type.pk).update(
            is_active=False
        )
        self.assertTrue(self.grave_site_type.is_active)

        with self.assertRaises(ValidationError) as context:
            self.create_base_grave_site()

        self.assert_error(
            context,
            key="grave_site_type",
            code="grave_site_type_inactive",
        )
        self.assertEqual(GraveSite.objects.count(), 0)

    def test_update_keeps_same_inactive_type_by_primary_key(self) -> None:
        inactive = self.make_type("inactive_same", is_active=False)
        grave_site = GraveSite.objects.create(
            grave_site_type=inactive,
            location_text="Původní",
        )
        stale_same_pk = GraveSiteType(
            pk=inactive.pk,
            code=inactive.code,
            name=inactive.name,
            is_active=True,
        )

        result = update_grave_site(
            grave_site=grave_site,
            data=self.make_data(
                grave_site_type=stale_same_pk,
                note="Doplněno",
            ),
        )

        self.assertEqual(result.grave_site_type_id, inactive.pk)
        self.assertEqual(result.note, "Doplněno")

    def test_update_rejects_transition_to_other_inactive_type(
        self,
    ) -> None:
        inactive_current = self.make_type(
            "inactive_current",
            is_active=False,
        )
        inactive_target = self.make_type(
            "inactive_target",
            is_active=False,
        )
        active_site = self.create_base_grave_site()
        inactive_site = GraveSite.objects.create(
            grave_site_type=inactive_current,
            location_text="Neaktivní původní typ",
        )

        for grave_site in (active_site, inactive_site):
            with self.subTest(grave_site=grave_site.pk):
                with self.assertRaises(ValidationError) as context:
                    update_grave_site(
                        grave_site=grave_site,
                        data=self.make_data(
                            grave_site_type=inactive_target
                        ),
                    )
                self.assert_error(
                    context,
                    key="grave_site_type",
                    code="grave_site_type_inactive",
                )

    def test_update_allows_inactive_to_active_type(self) -> None:
        inactive = self.make_type("inactive_old", is_active=False)
        grave_site = GraveSite.objects.create(
            grave_site_type=inactive,
            location_text="Původní",
        )

        result = update_grave_site(
            grave_site=grave_site,
            data=self.make_data(grave_site_type=self.other_type),
        )

        self.assertEqual(result.grave_site_type_id, self.other_type.pk)

    def test_update_uses_fresh_current_type_for_transition(self) -> None:
        inactive = self.make_type("fresh_inactive", is_active=False)
        grave_site = self.create_base_grave_site()
        GraveSite.objects.filter(pk=grave_site.pk).update(
            grave_site_type=inactive
        )
        self.assertEqual(
            grave_site.grave_site_type_id,
            self.grave_site_type.pk,
        )

        result = update_grave_site(
            grave_site=grave_site,
            data=self.make_data(
                grave_site_type=inactive,
                note="Povoleno",
            ),
        )

        self.assertEqual(result.grave_site_type_id, inactive.pk)
        self.assertEqual(result.note, "Povoleno")

    def test_update_replaces_complete_editable_snapshot(self) -> None:
        grave_site = self.create_base_grave_site(
            place=self.place,
            cemetery_name="Původní hřbitov",
            latitude=Decimal("50.100000"),
            longitude=Decimal("14.100000"),
        )
        data = self.make_data(
            grave_site_type=self.other_type,
            status=GraveSiteStatus.DESTROYED,
            place=None,
            location_text="Nová lokalita",
            cemetery_name="",
            section="A",
            row="2",
            grave_number="15",
            inscription="Nový nápis",
            latitude=None,
            longitude=None,
            note="Nová poznámka",
            access_level=AccessLevel.AUTHENTICATED,
            verification_status=VerificationStatus.PROBABLE,
        )

        result = update_grave_site(
            grave_site=grave_site,
            data=data,
        )

        self.assertEqual(result.grave_site_type_id, self.other_type.pk)
        self.assertEqual(result.status, GraveSiteStatus.DESTROYED)
        self.assertIsNone(result.place_id)
        self.assertEqual(result.location_text, "Nová lokalita")
        self.assertEqual(result.cemetery_name, "")
        self.assertEqual(result.section, "A")
        self.assertEqual(result.row, "2")
        self.assertEqual(result.grave_number, "15")
        self.assertEqual(result.inscription, "Nový nápis")
        self.assertIsNone(result.latitude)
        self.assertIsNone(result.longitude)
        self.assertEqual(result.note, "Nová poznámka")
        self.assertEqual(
            result.access_level,
            AccessLevel.AUTHENTICATED,
        )
        self.assertEqual(
            result.verification_status,
            VerificationStatus.PROBABLE,
        )

    def test_update_preserves_fresh_author_and_lifecycle_metadata(
        self,
    ) -> None:
        original_creator = get_user_model().objects.create_user(
            username="original-grave-creator"
        )
        current_creator = get_user_model().objects.create_user(
            username="current-grave-creator"
        )
        archivist = get_user_model().objects.create_user(
            username="grave-archivist"
        )
        grave_site = create_grave_site(
            data=self.make_data(),
            created_by=original_creator,
        )
        created_at = grave_site.created_at
        archived_at = timezone.now() - timedelta(days=1)
        old_updated_at = grave_site.updated_at - timedelta(days=1)
        GraveSite.objects.filter(pk=grave_site.pk).update(
            created_by=current_creator,
            archived_at=archived_at,
            archived_by=archivist,
            archive_reason="Historický záznam",
            updated_at=old_updated_at,
        )

        result = update_grave_site(
            grave_site=grave_site,
            data=self.make_data(note="Upraveno"),
        )

        self.assertEqual(result.created_by_id, current_creator.pk)
        self.assertEqual(result.created_at, created_at)
        self.assertEqual(result.archived_at, archived_at)
        self.assertEqual(result.archived_by_id, archivist.pk)
        self.assertEqual(result.archive_reason, "Historický záznam")
        self.assertIsNone(result.deleted_at)
        self.assertIsNone(result.deleted_by_id)
        self.assertEqual(result.deletion_reason, "")
        self.assertGreater(result.updated_at, old_updated_at)

    def test_update_rejects_fresh_soft_deleted_state(self) -> None:
        grave_site = self.create_base_grave_site(note="Původní")
        deleted_at = timezone.now()
        GraveSite.objects.filter(pk=grave_site.pk).update(
            deleted_at=deleted_at
        )
        self.assertIsNone(grave_site.deleted_at)

        with self.assertRaises(ValidationError) as context:
            update_grave_site(
                grave_site=grave_site,
                data=self.make_data(note="Změněno"),
            )

        self.assert_error(
            context,
            key="grave_site",
            code="grave_site_deleted",
        )
        grave_site.refresh_from_db()
        self.assertEqual(grave_site.note, "Původní")
        self.assertEqual(grave_site.deleted_at, deleted_at)

    def test_update_rejects_unsaved_and_physically_missing_site(
        self,
    ) -> None:
        unsaved = GraveSite()
        missing = self.create_base_grave_site()
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        for grave_site in (unsaved, missing):
            with self.subTest(grave_site=grave_site.pk):
                with self.assertRaises(ValidationError) as context:
                    update_grave_site(
                        grave_site=grave_site,
                        data=self.make_data(),
                    )
                self.assert_error(
                    context,
                    key="grave_site",
                    code="grave_site_unsaved",
                )

    def test_invalid_update_rolls_back_every_changed_field(self) -> None:
        creator = get_user_model().objects.create_user(
            username="rollback-grave-creator"
        )
        grave_site = create_grave_site(
            data=self.make_data(
                place=self.place,
                cemetery_name="Původní hřbitov",
                section="A",
                row="1",
                grave_number="10",
                inscription="Původní nápis",
                latitude=Decimal("50.100000"),
                longitude=Decimal("14.100000"),
                note="Původní poznámka",
            ),
            created_by=creator,
        )
        original_values = {
            field_name: getattr(grave_site, field_name)
            for field_name in (
                "grave_site_type_id",
                "status",
                "place_id",
                "location_text",
                "cemetery_name",
                "section",
                "row",
                "grave_number",
                "inscription",
                "latitude",
                "longitude",
                "note",
                "access_level",
                "verification_status",
                "created_by_id",
                "created_at",
                "updated_at",
                "archived_at",
                "deleted_at",
            )
        }

        with self.assertRaises(ValidationError):
            update_grave_site(
                grave_site=grave_site,
                data=self.make_data(
                    grave_site_type=self.other_type,
                    status=GraveSiteStatus.DESTROYED,
                    place=self.other_place,
                    location_text="Nová lokalita",
                    cemetery_name="Nový hřbitov",
                    section="B",
                    row="2",
                    grave_number="20",
                    inscription="Nový nápis",
                    latitude=Decimal("49"),
                    longitude=Decimal("15"),
                    note="Nová poznámka",
                    access_level="invalid",
                    verification_status=VerificationStatus.VERIFIED,
                ),
            )

        grave_site.refresh_from_db()
        self.assertEqual(
            {
                field_name: getattr(grave_site, field_name)
                for field_name in original_values
            },
            original_values,
        )

    def test_active_user_type_is_allowed_for_create_and_update(self) -> None:
        user_type = self.make_type("user_grave_type")
        created = create_grave_site(
            data=self.make_data(grave_site_type=user_type)
        )
        updated = update_grave_site(
            grave_site=created,
            data=self.make_data(grave_site_type=self.other_type),
        )

        self.assertFalse(user_type.is_system)
        self.assertEqual(updated.grave_site_type_id, self.other_type.pk)

    def test_archived_and_soft_deleted_places_are_allowed(self) -> None:
        archived = self.make_place("Archivované místo")
        deleted = self.make_place("Měkce odstraněné místo")
        now = timezone.now()
        Place.objects.filter(pk=archived.pk).update(archived_at=now)
        Place.objects.filter(pk=deleted.pk).update(deleted_at=now)

        archived_result = create_grave_site(
            data=self.make_data(place=archived)
        )
        deleted_result = create_grave_site(
            data=self.make_data(place=deleted)
        )

        self.assertEqual(archived_result.place_id, archived.pk)
        self.assertEqual(deleted_result.place_id, deleted.pk)

    def test_service_allows_duplicate_grave_sites(self) -> None:
        first = self.create_base_grave_site()
        second = self.create_base_grave_site()

        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(GraveSite.objects.count(), 2)

    def test_service_has_no_unplanned_side_writes(self) -> None:
        type_values = (
            self.grave_site_type.code,
            self.grave_site_type.name,
            self.grave_site_type.is_active,
        )
        place_values = (
            self.place.name,
            self.place.normalized_name,
            self.place.archived_at,
            self.place.deleted_at,
        )
        event_count = Event.objects.count()
        link_count = PersonGraveSite.objects.count()

        self.create_base_grave_site(place=self.place)

        self.grave_site_type.refresh_from_db()
        self.place.refresh_from_db()
        self.assertEqual(
            (
                self.grave_site_type.code,
                self.grave_site_type.name,
                self.grave_site_type.is_active,
            ),
            type_values,
        )
        self.assertEqual(
            (
                self.place.name,
                self.place.normalized_name,
                self.place.archived_at,
                self.place.deleted_at,
            ),
            place_values,
        )
        self.assertEqual(Event.objects.count(), event_count)
        self.assertEqual(PersonGraveSite.objects.count(), link_count)
        self.assertEqual(GraveSite.objects.count(), 1)

    def test_update_uses_select_for_update_on_grave_site(self) -> None:
        grave_site = self.create_base_grave_site()

        with patch.object(
            GraveSite.objects,
            "select_for_update",
            wraps=GraveSite.objects.select_for_update,
        ) as mocked_lock:
            update_grave_site(
                grave_site=grave_site,
                data=self.make_data(note="Zamčeno"),
            )

        mocked_lock.assert_called_once_with()

    def test_unexpected_integrity_error_is_not_mapped(self) -> None:
        with patch.object(
            GraveSite,
            "save",
            side_effect=IntegrityError("neočekávaná chyba"),
        ):
            with self.assertRaises(IntegrityError):
                self.create_base_grave_site()

        self.assertEqual(GraveSite.objects.count(), 0)

from django.contrib import admin
from django.urls import NoReverseMatch, reverse
from django.test import SimpleTestCase

from .models import (
    GraveSite,
    GraveSiteType,
    PersonGraveSite,
    PersonGraveSiteRole,
    Place,
    PlaceType,
    Residence,
    ResidenceType,
)


class PlacesAdminBoundaryTests(SimpleTestCase):
    """Business entity jsou fail-closed, číselníky spravovatelné."""

    business_models = (Place, Residence, GraveSite, PersonGraveSite)
    lookup_models = (
        PlaceType,
        ResidenceType,
        GraveSiteType,
        PersonGraveSiteRole,
    )

    def test_business_models_have_no_admin_routes(self) -> None:
        for model in self.business_models:
            with self.subTest(model=model.__name__):
                self.assertFalse(admin.site.is_registered(model))
                with self.assertRaises(NoReverseMatch):
                    reverse(
                        f"admin:{model._meta.app_label}_"
                        f"{model._meta.model_name}_changelist"
                    )

    def test_lookup_models_keep_admin_routes(self) -> None:
        for model in self.lookup_models:
            with self.subTest(model=model.__name__):
                self.assertTrue(admin.site.is_registered(model))
                self.assertEqual(
                    reverse(
                        f"admin:{model._meta.app_label}_"
                        f"{model._meta.model_name}_changelist"
                    ),
                    (
                        f"/admin/{model._meta.app_label}/"
                        f"{model._meta.model_name}/"
                    ),
                )

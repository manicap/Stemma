"""Admin configuration for user accounts."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from materials.services import get_or_create_owned_vault

from .models import User


@admin.register(User)
class StemmaUserAdmin(UserAdmin):
    """Admin interface for the Stemma user model."""

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            get_or_create_owned_vault(owner=obj)

"""Admin configuration for user accounts."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class StemmaUserAdmin(UserAdmin):
    """Admin interface for the Stemma user model."""
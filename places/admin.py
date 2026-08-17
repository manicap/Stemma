from django.contrib import admin

from common.admin import SystemValueAdminMixin

from .models import (
    GraveSiteType,
    PersonGraveSiteRole,
    PlaceType,
    ResidenceType,
)


@admin.register(ResidenceType)
class ResidenceTypeAdmin(SystemValueAdminMixin):
    list_display = (
        "code",
        "name",
        "sort_order",
        "is_active",
        "is_system",
    )
    search_fields = (
        "code",
        "name",
    )
    list_filter = (
        "is_active",
        "is_system",
    )


@admin.register(GraveSiteType)
class GraveSiteTypeAdmin(SystemValueAdminMixin):
    list_display = (
        "code",
        "name",
        "sort_order",
        "is_active",
        "is_system",
    )
    search_fields = (
        "code",
        "name",
    )
    list_filter = (
        "is_active",
        "is_system",
    )


@admin.register(PersonGraveSiteRole)
class PersonGraveSiteRoleAdmin(SystemValueAdminMixin):
    list_display = (
        "code",
        "name",
        "sort_order",
        "is_active",
        "is_system",
    )
    search_fields = (
        "code",
        "name",
    )
    list_filter = (
        "is_active",
        "is_system",
    )


admin.site.register(PlaceType, SystemValueAdminMixin)

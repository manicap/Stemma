from django.contrib import admin

from .models import (
    GraveSite,
    GraveSiteType,
    PersonGraveSiteRole,
    Place,
    PlaceType,
    Residence,
    ResidenceType,
)


@admin.register(ResidenceType)
class ResidenceTypeAdmin(admin.ModelAdmin):
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
class GraveSiteTypeAdmin(admin.ModelAdmin):
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
class PersonGraveSiteRoleAdmin(admin.ModelAdmin):
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


@admin.register(GraveSite)
class GraveSiteAdmin(admin.ModelAdmin):
    list_display = (
        "grave_site_type",
        "cemetery_name",
        "place",
        "section",
        "row",
        "grave_number",
        "status",
        "access_level",
        "verification_status",
        "archived_at",
        "deleted_at",
    )
    list_filter = (
        "grave_site_type",
        "status",
        "access_level",
        "verification_status",
        "archived_at",
        "deleted_at",
    )
    search_fields = (
        "cemetery_name",
        "location_text",
        "place__name",
        "section",
        "row",
        "grave_number",
        "inscription",
        "note",
    )


@admin.register(Residence)
class ResidenceAdmin(admin.ModelAdmin):
    list_display = (
        "person",
        "residence_type",
        "place",
        "address_text",
        "date_precision",
        "access_level",
        "verification_status",
        "archived_at",
        "deleted_at",
    )
    list_filter = (
        "residence_type",
        "date_precision",
        "access_level",
        "verification_status",
        "archived_at",
        "deleted_at",
    )
    search_fields = (
        "person__first_name",
        "person__last_name",
        "place__name",
        "address_text",
        "note",
    )


admin.site.register(PlaceType)
admin.site.register(Place)

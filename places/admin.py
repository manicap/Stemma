from django.contrib import admin

from .models import Place, PlaceType, Residence, ResidenceType


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

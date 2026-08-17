from django.contrib import admin
from django.http import HttpRequest

from common.admin import SystemValueAdminMixin
from common.choices import AccessLevel
from common.permissions import can_view_access_level

from .models import (
    NameType,
    Person,
    PersonCategory,
    PersonName,
    Relationship,
    RelationshipType,
)
from .selectors import get_visible_people


class _ReadOnlyAdminMixin:
    """Dočasně zakaž admin zápis mimo doménové služby."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self,
        request: HttpRequest,
        obj=None,
    ) -> bool:
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj=None,
    ) -> bool:
        return False


def _visible_access_levels(request: HttpRequest) -> tuple[str, ...]:
    return tuple(
        access_level
        for access_level in AccessLevel.values
        if can_view_access_level(
            actor=request.user,
            access_level=access_level,
        )
    )


@admin.register(Person)
class PersonAdmin(_ReadOnlyAdminMixin, admin.ModelAdmin):
    """Bezpečný read-only pohled respektující aplikační viditelnost."""

    def get_queryset(self, request: HttpRequest):
        return get_visible_people(actor=request.user)


@admin.register(PersonName)
class PersonNameAdmin(_ReadOnlyAdminMixin, admin.ModelAdmin):
    """Čti pouze jména viditelných aktivních osob."""

    def get_queryset(self, request: HttpRequest):
        return (
            super()
            .get_queryset(request)
            .filter(
                person__in=get_visible_people(actor=request.user),
                access_level__in=_visible_access_levels(request),
                archived_at__isnull=True,
                deleted_at__isnull=True,
            )
            .select_related("person", "name_type")
        )


@admin.register(Relationship)
class RelationshipAdmin(_ReadOnlyAdminMixin, admin.ModelAdmin):
    """Čti pouze vazby mezi dvěma viditelnými aktivními osobami."""

    def get_queryset(self, request: HttpRequest):
        visible_people = get_visible_people(actor=request.user)
        return (
            super()
            .get_queryset(request)
            .filter(
                person_a__in=visible_people,
                person_b__in=visible_people,
                access_level__in=_visible_access_levels(request),
                archived_at__isnull=True,
                deleted_at__isnull=True,
            )
            .select_related("person_a", "person_b", "relationship_type")
        )


admin.site.register(PersonCategory, SystemValueAdminMixin)
admin.site.register(NameType, SystemValueAdminMixin)


@admin.register(RelationshipType)
class RelationshipTypeAdmin(SystemValueAdminMixin):
    system_identity_fields = (
        "code",
        "category",
        "is_symmetric",
        "supports_date_range",
        "is_derivable",
    )

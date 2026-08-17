from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest


class SystemValueAdminMixin(admin.ModelAdmin):
    """Chraň technickou identitu systémových číselníkových hodnot."""

    system_identity_fields = ("code",)

    def get_readonly_fields(
        self,
        request: HttpRequest,
        obj=None,
    ) -> tuple[str, ...]:
        readonly_fields = tuple(super().get_readonly_fields(request, obj))
        if obj is None or not getattr(obj, "is_system", False):
            return readonly_fields
        return tuple(
            dict.fromkeys(readonly_fields + self.system_identity_fields)
        )

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj=None,
    ) -> bool:
        if obj is not None and getattr(obj, "is_system", False):
            return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change: bool) -> None:
        if change and obj.pk is not None:
            current = (
                obj.__class__._default_manager.select_for_update().get(
                    pk=obj.pk
                )
            )
            if current.is_system:
                obj.is_system = True
                for field_name in self.system_identity_fields:
                    setattr(obj, field_name, getattr(current, field_name))
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj) -> None:
        if getattr(obj, "is_system", False):
            raise PermissionDenied
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset) -> None:
        if queryset.filter(is_system=True).exists():
            raise PermissionDenied
        super().delete_queryset(request, queryset)

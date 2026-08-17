from django.contrib import admin

from common.admin import SystemValueAdminMixin

from .models import (
    AllowedEventRole,
    EventType,
    ParticipantRole,
)


admin.site.register(EventType, SystemValueAdminMixin)
admin.site.register(ParticipantRole, SystemValueAdminMixin)


@admin.register(AllowedEventRole)
class AllowedEventRoleAdmin(SystemValueAdminMixin):
    system_identity_fields = ("event_type", "participant_role")

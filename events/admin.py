from django.contrib import admin

from .models import (
    AllowedEventRole,
    Event,
    EventParticipant,
    EventType,
    ParticipantRole,
)


admin.site.register(EventType)
admin.site.register(ParticipantRole)
admin.site.register(AllowedEventRole)
admin.site.register(Event)
admin.site.register(EventParticipant)

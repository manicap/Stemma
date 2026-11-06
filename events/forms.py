from django import forms

from common.choices import AccessLevel, DatePrecision
from common.permissions import can_view_access_level
from places.models import Place

from .models import Event


class PersonLifeEventForm(forms.ModelForm):
    """HTTP validation for the editable birth/death event snapshot."""

    class Meta:
        model = Event
        fields = (
            "date_precision",
            "date_qualifier",
            "start_year",
            "start_month",
            "start_day",
            "original_date_text",
            "date_note",
            "place",
            "location_detail",
            "title",
            "description",
            "access_level",
            "verification_status",
        )
        labels = {
            "date_precision": "Přesnost data",
            "date_qualifier": "Upřesnění data",
            "start_year": "Rok",
            "start_month": "Měsíc",
            "start_day": "Den",
            "original_date_text": "Původní zápis data",
            "date_note": "Poznámka k datu",
            "place": "Strukturované místo",
            "location_detail": "Lokalizační detail",
            "title": "Název",
            "description": "Popis nebo poznámka",
            "access_level": "Přístup",
            "verification_status": "Ověření",
        }
        widgets = {
            "date_note": forms.Textarea(attrs={"rows": 3}),
            "description": forms.Textarea(attrs={"rows": 5}),
            "start_year": forms.NumberInput(attrs={"min": 1, "max": 9999}),
            "start_month": forms.NumberInput(attrs={"min": 1, "max": 12}),
            "start_day": forms.NumberInput(attrs={"min": 1, "max": 31}),
        }

    def __init__(self, *args, actor, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        visible_levels = tuple(
            value
            for value in AccessLevel.values
            if can_view_access_level(actor=actor, access_level=value)
        )
        self.fields["access_level"].choices = tuple(
            (value, label)
            for value, label in AccessLevel.choices
            if value in visible_levels
        )
        self.fields["date_precision"].choices = tuple(
            (value, label)
            for value, label in DatePrecision.choices
            if value != DatePrecision.RANGE
        )
        self.fields["place"].queryset = Place.objects.filter(
            access_level__in=visible_levels,
            archived_at__isnull=True,
            deleted_at__isnull=True,
        )
        self.fields["place"].empty_label = "Bez strukturovaného místa"

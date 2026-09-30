from django import forms

from common.choices import AccessLevel

from .models import HealthRecord, HealthRecordType
from .permissions import can_view_health_record_access


class HealthRecordArchiveForm(forms.Form):
    """Transportní formulář volitelného důvodu archivace."""

    reason = forms.CharField(
        label="Důvod archivace",
        required=False,
        strip=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class HealthRecordRestoreForm(forms.Form):
    """Prázdný potvrzovací formulář obnovy archivovaného záznamu."""


class HealthRecordSoftDeleteForm(forms.Form):
    """Transportní formulář povinného důvodu odstranění."""

    deletion_reason = forms.CharField(
        label="Důvod odstranění",
        required=True,
        strip=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class HealthRecordRestoreSoftDeletedForm(forms.Form):
    """Prázdný potvrzovací formulář obnovy odstraněného záznamu."""


class HealthRecordForm(forms.ModelForm):
    """HTTP validation for the user-editable HealthRecord snapshot."""

    class Meta:
        model = HealthRecord
        fields = (
            "record_type",
            "title",
            "description",
            "provider_name",
            "note",
            "access_level",
            "verification_status",
            "date_precision",
            "date_qualifier",
            "start_year",
            "start_month",
            "start_day",
            "end_year",
            "end_month",
            "end_day",
            "original_date_text",
            "date_note",
        )
        labels = {
            "record_type": "Typ záznamu",
            "title": "Název",
            "description": "Popis",
            "provider_name": "Poskytovatel",
            "note": "Poznámka",
            "access_level": "Přístup",
            "verification_status": "Ověření",
            "date_precision": "Přesnost data",
            "date_qualifier": "Upřesnění data",
            "start_year": "Počáteční rok",
            "start_month": "Počáteční měsíc",
            "start_day": "Počáteční den",
            "end_year": "Koncový rok",
            "end_month": "Koncový měsíc",
            "end_day": "Koncový den",
            "original_date_text": "Původní zápis data",
            "date_note": "Poznámka k datu",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "note": forms.Textarea(attrs={"rows": 4}),
            "date_note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, actor, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["record_type"].queryset = HealthRecordType.objects.filter(
            is_active=True
        )
        self.fields["access_level"].choices = tuple(
            (value, label)
            for value, label in AccessLevel.choices
            if value in (AccessLevel.RESTRICTED, AccessLevel.ADMIN_ONLY)
            and can_view_health_record_access(
                actor=actor,
                access_level=value,
            )
        )

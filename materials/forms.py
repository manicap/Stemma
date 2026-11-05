"""HTTP forms for the focused Materials UI slices."""

from django import forms
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser

from common.choices import AccessLevel
from common.permissions import can_view_access_level

from .models import AttachmentCategory, AttachmentRole


class PersonAttachmentUploadForm(forms.Form):
    """Validate user-editable metadata for one person attachment upload."""

    file = forms.FileField(
        label="Soubor",
        help_text=(
            "Povolené formáty: PDF, JPEG a PNG. Maximální velikost 25 MiB."
        ),
        widget=forms.ClearableFileInput(
            attrs={
                "accept": (
                    "application/pdf,image/jpeg,image/png,.pdf,.jpg,.jpeg,.png"
                )
            }
        ),
    )
    display_name = forms.CharField(
        label="Název",
        max_length=255,
        required=False,
    )
    description = forms.CharField(
        label="Popis",
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    category = forms.ModelChoiceField(
        label="Kategorie",
        queryset=AttachmentCategory.objects.none(),
    )
    role = forms.ModelChoiceField(
        label="Role u osoby",
        queryset=AttachmentRole.objects.none(),
    )
    access_level = forms.ChoiceField(label="Přístup")

    def __init__(
        self,
        *args,
        actor: AbstractBaseUser | AnonymousUser,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = AttachmentCategory.objects.filter(
            is_active=True
        )
        self.fields["role"].queryset = AttachmentRole.objects.filter(
            is_active=True
        )
        self.fields["access_level"].choices = tuple(
            (value, label)
            for value, label in AccessLevel.choices
            if can_view_access_level(actor=actor, access_level=value)
        )
        self.fields["access_level"].initial = AccessLevel.PUBLIC
        self.is_configured = (
            self.fields["category"].queryset.exists()
            and self.fields["role"].queryset.exists()
        )

from django import forms
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q

from common.choices import AccessLevel
from common.permissions import can_view_access_level

from .models import Person, PersonCategory


class PersonForm(forms.ModelForm):
    """RC formulář pro základní identifikační údaje osoby."""

    class Meta:
        model = Person
        fields = (
            "first_name",
            "last_name",
            "gender",
            "category",
            "notes",
        )
        labels = {
            "first_name": "Jméno",
            "last_name": "Příjmení",
            "gender": "Pohlaví",
            "category": "Kategorie",
            "notes": "Poznámka",
        }
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        category_id = self.instance.category_id
        category_filter = Q(is_active=True)
        if category_id is not None:
            category_filter |= Q(pk=category_id)
        self.fields["category"].queryset = PersonCategory.objects.filter(
            category_filter
        )
        self.fields["category"].empty_label = "Bez kategorie"

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        if not (cleaned_data.get("first_name") or "").strip() and not (
            cleaned_data.get("last_name") or ""
        ).strip():
            message = "Vyplňte alespoň jméno nebo příjmení."
            self.add_error("first_name", message)
            self.add_error("last_name", message)
        return cleaned_data


class PersonCreateForm(forms.ModelForm):
    """Validate the approved person-creation fields for one current actor."""

    access_level = forms.ChoiceField(label="Přístup")

    class Meta:
        model = Person
        fields = (
            "title_before_name",
            "first_name",
            "last_name",
            "title_after_name",
            "gender",
            "category",
            "notes",
            "access_level",
        )
        labels = {
            "title_before_name": "Titul před jménem",
            "first_name": "Jméno",
            "last_name": "Příjmení",
            "title_after_name": "Titul za jménem",
            "gender": "Pohlaví",
            "category": "Kategorie",
            "notes": "Poznámka",
        }
        widgets = {"notes": forms.Textarea(attrs={"rows": 6})}

    def __init__(
        self,
        *args,
        actor: AbstractBaseUser | AnonymousUser,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = PersonCategory.objects.filter(
            is_active=True
        )
        self.fields["category"].empty_label = "Bez kategorie"
        self.fields["access_level"].choices = tuple(
            (value, label)
            for value, label in AccessLevel.choices
            if can_view_access_level(actor=actor, access_level=value)
        )
        self.fields["access_level"].initial = AccessLevel.PUBLIC

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        if not (cleaned_data.get("first_name") or "").strip() and not (
            cleaned_data.get("last_name") or ""
        ).strip():
            message = "Vyplňte alespoň jméno nebo příjmení."
            self.add_error("first_name", message)
            self.add_error("last_name", message)
        return cleaned_data

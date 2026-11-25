from django import forms
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q

from common.choices import AccessLevel, DatePrecision
from common.permissions import can_view_access_level

from .models import Person, PersonCategory, Relationship, RelationshipType


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


class PersonRelationshipForm(forms.ModelForm):
    """Validate editable relationship attributes and an optional person."""

    other_person = forms.TypedChoiceField(
        label="Propojit s osobou",
        coerce=int,
        empty_value=None,
        required=False,
    )

    class Meta:
        model = Relationship
        fields = (
            "other_person",
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
            "note",
            "access_level",
            "verification_status",
        )
        labels = {
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
            "note": "Poznámka ke vztahu",
            "access_level": "Přístup",
            "verification_status": "Ověření",
        }
        widgets = {
            "date_note": forms.Textarea(attrs={"rows": 3}),
            "note": forms.Textarea(attrs={"rows": 5}),
            "start_year": forms.NumberInput(attrs={"min": 1, "max": 9999}),
            "start_month": forms.NumberInput(attrs={"min": 1, "max": 12}),
            "start_day": forms.NumberInput(attrs={"min": 1, "max": 31}),
            "end_year": forms.NumberInput(attrs={"min": 1, "max": 9999}),
            "end_month": forms.NumberInput(attrs={"min": 1, "max": 12}),
            "end_day": forms.NumberInput(attrs={"min": 1, "max": 31}),
        }

    def __init__(
        self,
        *args,
        actor: AbstractBaseUser | AnonymousUser,
        relationship_type: RelationshipType,
        person_choices: tuple[tuple[int, str], ...] = (),
        include_other_person: bool,
        **kwargs,
    ) -> None:
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
        if relationship_type.supports_date_range:
            date_precision_choices = DatePrecision.choices
        else:
            date_precision_choices = tuple(
                (value, label)
                for value, label in DatePrecision.choices
                if value != DatePrecision.RANGE
            )
        self.fields["date_precision"].choices = date_precision_choices
        if include_other_person:
            self.fields["other_person"].required = True
            self.fields["other_person"].choices = (
                ("", "Vyberte existující osobu"),
                *person_choices,
            )
            self.fields["other_person"].widget.attrs.update(
                {"data-relationship-person-select": ""}
            )
        else:
            self.fields.pop("other_person")

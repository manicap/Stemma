from django import forms
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q

from common.choices import AccessLevel, DatePrecision
from common.permissions import can_view_access_level

from .models import Person, PersonCategory, Relationship


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


_RELATIONSHIP_COUNTERPART_LABELS = {
    "parent": "Rodič",
    "child": "Dítě",
    "partner": "Partner nebo partnerka",
}
_RELATIONSHIP_RANGE_FIELDS = ("end_year", "end_month", "end_day")


class PersonRelationshipForm(forms.ModelForm):
    """HTTP validace úzkého zápisu rodičovské a partnerské vazby.

    Typ vazby a účastníky formulář nikdy nepřijímá; protistranu lze zvolit
    jen při vytvoření, a to výhradně z osob předaných autorizovaným
    person browserem.
    """

    counterpart = forms.ModelChoiceField(
        queryset=Person.objects.none(),
        label="Osoba",
        empty_label="Vyberte osobu",
    )

    class Meta:
        model = Relationship
        fields = (
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
            "start_year": "Rok začátku",
            "start_month": "Měsíc začátku",
            "start_day": "Den začátku",
            "end_year": "Rok konce",
            "end_month": "Měsíc konce",
            "end_day": "Den konce",
            "original_date_text": "Původní zápis data",
            "date_note": "Poznámka k datu",
            "note": "Poznámka",
            "access_level": "Přístup",
            "verification_status": "Ověření",
        }
        widgets = {
            "date_note": forms.Textarea(attrs={"rows": 3}),
            "note": forms.Textarea(attrs={"rows": 4}),
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
        kind: str | None = None,
        counterpart_ids: tuple[int, ...] = (),
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        if kind is None:
            del self.fields["counterpart"]
        else:
            self.fields["counterpart"].label = (
                _RELATIONSHIP_COUNTERPART_LABELS[kind]
            )
            self.fields["counterpart"].queryset = Person.objects.filter(
                pk__in=counterpart_ids,
            ).order_by("last_name", "first_name", "pk")
            self.fields["counterpart"].widget.attrs[
                "data-relationship-person-select"
            ] = ""
            self.order_fields(("counterpart",))
        self.fields["access_level"].choices = tuple(
            (value, label)
            for value, label in AccessLevel.choices
            if can_view_access_level(actor=actor, access_level=value)
        )
        if not self.instance.relationship_type.supports_date_range:
            for field_name in _RELATIONSHIP_RANGE_FIELDS:
                del self.fields[field_name]
            self.fields["date_precision"].choices = tuple(
                (value, label)
                for value, label in DatePrecision.choices
                if value != DatePrecision.RANGE
            )

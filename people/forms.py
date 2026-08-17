from django import forms
from django.db.models import Q

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

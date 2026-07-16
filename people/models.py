from common.models import LookupModel


class PersonCategory(LookupModel):
    """Kategorie obecného zařazení osoby v rodinném příběhu."""

    class Meta(LookupModel.Meta):
        verbose_name = "Kategorie osoby"
        verbose_name_plural = "Kategorie osob"

    def __str__(self) -> str:
        return self.name

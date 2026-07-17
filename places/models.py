from common.models import LookupModel


class PlaceType(LookupModel):
    """Typ geografického nebo fyzického místa."""

    class Meta(LookupModel.Meta):
        verbose_name = "Typ místa"
        verbose_name_plural = "Typy míst"

    def __str__(self) -> str:
        return self.name

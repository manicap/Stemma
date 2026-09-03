from common.models import LookupModel


class HealthRecordType(LookupModel):
    """Uživatelsky rozšiřitelná klasifikace zdravotního záznamu."""

    class Meta(LookupModel.Meta):
        verbose_name = "Typ zdravotního záznamu"
        verbose_name_plural = "Typy zdravotních záznamů"

    def __str__(self) -> str:
        return self.name

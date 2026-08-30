from common.models import LookupModel


class AttachmentCategory(LookupModel):
    """Uživatelsky rozšiřitelná kategorie digitální přílohy."""

    class Meta(LookupModel.Meta):
        verbose_name = "Kategorie přílohy"
        verbose_name_plural = "Kategorie příloh"

    def __str__(self) -> str:
        return self.name


class AttachmentRole(LookupModel):
    """Význam explicitního propojení přílohy s doménovým objektem."""

    class Meta(LookupModel.Meta):
        verbose_name = "Role přílohy"
        verbose_name_plural = "Role příloh"

    def __str__(self) -> str:
        return self.name

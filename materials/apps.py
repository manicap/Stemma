from django.apps import AppConfig


class MaterialsConfig(AppConfig):
    """Konfigurace domény příloh, zdrojů a jejich vazeb."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "materials"
    verbose_name = "Materiály a zdroje"

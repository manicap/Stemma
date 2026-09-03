from django.apps import AppConfig


class HealthConfig(AppConfig):
    """Konfigurace domény citlivých zdravotních informací."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "health"
    verbose_name = "Zdravotní informace"

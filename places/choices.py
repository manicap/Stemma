"""Pevné výčty domény míst."""

from django.db import models


class GraveSiteStatus(models.TextChoices):
    """Současný nebo evidovaný fyzický stav hrobového místa."""

    EXISTING = "existing", "Existující"
    DESTROYED = "destroyed", "Zaniklé"
    UNKNOWN = "unknown", "Existence neznámá"

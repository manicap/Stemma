from django.db import models


class RelationshipCategory(models.TextChoices):
    """Pevné kategorie vztahů mezi osobami."""

    PARENT_CHILD = "parent_child", "Rodič a dítě"
    PARTNER = "partner", "Partnerství"
    SIBLING = "sibling", "Sourozenectví"
    GODPARENT = "godparent", "Kmotrovství"
    CARE = "care", "Péče a poručenství"
    SOCIAL = "social", "Sociální vazba"
    OTHER = "other", "Jiná vazba"

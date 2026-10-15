from django.db import models


class FileStatus(models.TextChoices):
    """Fyzický a provozní stav souboru přílohy."""

    PENDING = "pending", "Čeká na potvrzení"
    AVAILABLE = "available", "Dostupný"
    MISSING = "missing", "Nedostupný"
    QUARANTINED = "quarantined", "V karanténě"


class AttachmentPrivacyStatus(models.TextChoices):
    """Soukromí přílohy nezávislé na obsahové přístupové úrovni."""

    STANDARD = "standard", "Standardní"
    PRIVATE = "private", "Soukromá"


class AttachmentAccessRequestStatus(models.TextChoices):
    """Stav historické žádosti o přístup k soukromé příloze."""

    PENDING = "pending", "Čeká na rozhodnutí"
    APPROVED = "approved", "Schválená"
    DENIED = "denied", "Zamítnutá"
    CANCELLED = "cancelled", "Zrušená"


class SourceSupport(models.TextChoices):
    """Síla podpory konkrétního tvrzení zdrojovou vazbou."""

    CONFIRMS = "confirms", "Potvrzuje"
    SUGGESTS = "suggests", "Naznačuje"
    SUPPLEMENTS = "supplements", "Doplňuje"
    CONTRADICTS = "contradicts", "Odporuje"

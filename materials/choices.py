from django.db import models


class FileStatus(models.TextChoices):
    """Fyzický a provozní stav souboru přílohy."""

    PENDING = "pending", "Čeká na potvrzení"
    AVAILABLE = "available", "Dostupný"
    MISSING = "missing", "Nedostupný"
    QUARANTINED = "quarantined", "V karanténě"


class SourceSupport(models.TextChoices):
    """Síla podpory konkrétního tvrzení zdrojovou vazbou."""

    CONFIRMS = "confirms", "Potvrzuje"
    SUGGESTS = "suggests", "Naznačuje"
    SUPPLEMENTS = "supplements", "Doplňuje"
    CONTRADICTS = "contradicts", "Odporuje"

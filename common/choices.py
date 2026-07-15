"""Pevné výčty sdílené napříč aplikací Stemma."""

from django.db import models


class Gender(models.TextChoices):
    """Pohlaví osoby."""

    MALE = "male", "Muž"
    FEMALE = "female", "Žena"
    UNKNOWN = "unknown", "Neznámé"


class AccessLevel(models.TextChoices):
    """Přístupová úroveň záznamu."""

    PUBLIC = "public", "Veřejné"
    AUTHENTICATED = "authenticated", "Pouze přihlášení"
    RESTRICTED = "restricted", "Omezené"
    ADMIN_ONLY = "admin_only", "Pouze správce"


class VerificationStatus(models.TextChoices):
    """Stav ověření evidované informace."""

    VERIFIED = "verified", "Ověřeno"
    PROBABLE = "probable", "Pravděpodobné"
    UNCERTAIN = "uncertain", "Nejisté"
    DISPUTED = "disputed", "Sporné"
    UNCONFIRMED = "unconfirmed", "Nepotvrzené"


class DatePrecision(models.TextChoices):
    """Přesnost uloženého časového údaje."""

    EXACT = "exact", "Přesné datum"
    MONTH = "month", "Měsíc a rok"
    YEAR = "year", "Pouze rok"
    RANGE = "range", "Rozmezí"
    UNKNOWN = "unknown", "Neznámé datum"


class DateQualifier(models.TextChoices):
    """Kvalifikátor časového údaje."""

    NONE = "none", "Bez kvalifikátoru"
    APPROXIMATE = "approximate", "Přibližně"
    BEFORE = "before", "Před"
    AFTER = "after", "Po"
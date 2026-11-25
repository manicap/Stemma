from .settings import *  # noqa: F403


DATABASES["default"]["NAME"] = (  # noqa: F405
    BASE_DIR / ".tmp_relationship_smoke" / "db.sqlite3"  # noqa: F405
)
PROTECTED_ATTACHMENTS_ROOT = (
    BASE_DIR / ".tmp_relationship_smoke" / "attachments"  # noqa: F405
)

"""Django system checks for the private Materials storage boundary."""

from django.core.checks import Error, Tags, register
from django.core.exceptions import ImproperlyConfigured

from .storage import validate_protected_storage_root


@register(Tags.security)
def protected_storage_root_check(app_configs, **kwargs):
    """Report protected/public storage overlap before serving traffic."""

    try:
        validate_protected_storage_root()
    except ImproperlyConfigured as error:
        return [Error(str(error), id="materials.E001")]
    return []

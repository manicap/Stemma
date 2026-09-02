from django.contrib import admin

from common.admin import SystemValueAdminMixin

from .models import (
    AttachmentCategory,
    AttachmentRole,
    SourceRole,
    SourceType,
)


admin.site.register(AttachmentCategory, SystemValueAdminMixin)
admin.site.register(AttachmentRole, SystemValueAdminMixin)
admin.site.register(SourceType, SystemValueAdminMixin)
admin.site.register(SourceRole, SystemValueAdminMixin)

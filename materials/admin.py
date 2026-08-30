from django.contrib import admin

from common.admin import SystemValueAdminMixin

from .models import AttachmentCategory, AttachmentRole


admin.site.register(AttachmentCategory, SystemValueAdminMixin)
admin.site.register(AttachmentRole, SystemValueAdminMixin)

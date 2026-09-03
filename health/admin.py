from django.contrib import admin

from common.admin import SystemValueAdminMixin

from .models import HealthRecordType


admin.site.register(HealthRecordType, SystemValueAdminMixin)

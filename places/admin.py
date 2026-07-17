from django.contrib import admin

from .models import Place, PlaceType


admin.site.register(PlaceType)
admin.site.register(Place)

from django.contrib import admin

from .models import Person, PersonCategory


admin.site.register(PersonCategory)
admin.site.register(Person)

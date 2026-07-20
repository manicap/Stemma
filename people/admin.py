from django.contrib import admin

from .models import (
    NameType,
    Person,
    PersonCategory,
    PersonName,
    RelationshipType,
)


admin.site.register(PersonCategory)
admin.site.register(NameType)
admin.site.register(RelationshipType)
admin.site.register(Person)
admin.site.register(PersonName)

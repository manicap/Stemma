from django.contrib import admin

from .models import (
    NameType,
    Person,
    PersonCategory,
    PersonName,
    Relationship,
    RelationshipType,
)


admin.site.register(PersonCategory)
admin.site.register(NameType)
admin.site.register(RelationshipType)
admin.site.register(Relationship)
admin.site.register(Person)
admin.site.register(PersonName)

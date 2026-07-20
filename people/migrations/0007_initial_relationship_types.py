from django.db import migrations


INITIAL_RELATIONSHIP_TYPES = (
    {
        "code": "biological_parent",
        "name": "Biologický rodič",
        "description": "Vztah biologického rodiče a dítěte.",
        "category": "parent_child",
        "sort_order": 10,
        "is_symmetric": False,
        "supports_date_range": False,
        "is_derivable": False,
        "forward_label_male": "syn",
        "forward_label_female": "dcera",
        "forward_label_unknown": "dítě",
        "reverse_label_male": "otec",
        "reverse_label_female": "matka",
        "reverse_label_unknown": "rodič",
    },
    {
        "code": "adoptive_parent",
        "name": "Adoptivní rodič",
        "description": (
            "Vztah adoptivního rodiče a adoptovaného dítěte."
        ),
        "category": "parent_child",
        "sort_order": 20,
        "is_symmetric": False,
        "supports_date_range": False,
        "is_derivable": False,
        "forward_label_male": "adoptovaný syn",
        "forward_label_female": "adoptovaná dcera",
        "forward_label_unknown": "adoptované dítě",
        "reverse_label_male": "adoptivní otec",
        "reverse_label_female": "adoptivní matka",
        "reverse_label_unknown": "adoptivní rodič",
    },
    {
        "code": "step_parent",
        "name": "Nevlastní rodič",
        "description": (
            "Vztah nevlastního rodiče a nevlastního dítěte."
        ),
        "category": "parent_child",
        "sort_order": 30,
        "is_symmetric": False,
        "supports_date_range": True,
        "is_derivable": False,
        "forward_label_male": "nevlastní syn",
        "forward_label_female": "nevlastní dcera",
        "forward_label_unknown": "nevlastní dítě",
        "reverse_label_male": "nevlastní otec",
        "reverse_label_female": "nevlastní matka",
        "reverse_label_unknown": "nevlastní rodič",
    },
    {
        "code": "foster_parent",
        "name": "Pěstoun",
        "description": "Vztah pěstouna a dítěte v pěstounské péči.",
        "category": "parent_child",
        "sort_order": 40,
        "is_symmetric": False,
        "supports_date_range": True,
        "is_derivable": False,
        "forward_label_male": "pěstounský syn",
        "forward_label_female": "pěstounská dcera",
        "forward_label_unknown": "dítě v pěstounské péči",
        "reverse_label_male": "pěstoun",
        "reverse_label_female": "pěstounka",
        "reverse_label_unknown": "pěstoun nebo pěstounka",
    },
    {
        "code": "guardian",
        "name": "Poručník",
        "description": "Vztah poručníka a osoby v poručenství.",
        "category": "care",
        "sort_order": 50,
        "is_symmetric": False,
        "supports_date_range": True,
        "is_derivable": False,
        "forward_label_male": "svěřenec",
        "forward_label_female": "svěřenkyně",
        "forward_label_unknown": "osoba v poručenství",
        "reverse_label_male": "poručník",
        "reverse_label_female": "poručnice",
        "reverse_label_unknown": "poručník nebo poručnice",
    },
    {
        "code": "spouse",
        "name": "Manželství",
        "description": "Manželský vztah mezi dvěma osobami.",
        "category": "partner",
        "sort_order": 60,
        "is_symmetric": True,
        "supports_date_range": True,
        "is_derivable": False,
        "forward_label_male": "manžel",
        "forward_label_female": "manželka",
        "forward_label_unknown": "manžel nebo manželka",
        "reverse_label_male": "manžel",
        "reverse_label_female": "manželka",
        "reverse_label_unknown": "manžel nebo manželka",
    },
    {
        "code": "partner",
        "name": "Partnerství",
        "description": "Partnerský vztah mezi dvěma osobami.",
        "category": "partner",
        "sort_order": 70,
        "is_symmetric": True,
        "supports_date_range": True,
        "is_derivable": False,
        "forward_label_male": "partner",
        "forward_label_female": "partnerka",
        "forward_label_unknown": "partner nebo partnerka",
        "reverse_label_male": "partner",
        "reverse_label_female": "partnerka",
        "reverse_label_unknown": "partner nebo partnerka",
    },
    {
        "code": "sibling",
        "name": "Biologické sourozenectví",
        "description": "Biologické sourozenectví.",
        "category": "sibling",
        "sort_order": 80,
        "is_symmetric": True,
        "supports_date_range": False,
        "is_derivable": True,
        "forward_label_male": "bratr",
        "forward_label_female": "sestra",
        "forward_label_unknown": "sourozenec",
        "reverse_label_male": "bratr",
        "reverse_label_female": "sestra",
        "reverse_label_unknown": "sourozenec",
    },
    {
        "code": "adoptive_sibling",
        "name": "Adoptivní sourozenectví",
        "description": "Sourozenectví vzniklé adopcí.",
        "category": "sibling",
        "sort_order": 90,
        "is_symmetric": True,
        "supports_date_range": False,
        "is_derivable": False,
        "forward_label_male": "adoptivní bratr",
        "forward_label_female": "adoptivní sestra",
        "forward_label_unknown": "adoptivní sourozenec",
        "reverse_label_male": "adoptivní bratr",
        "reverse_label_female": "adoptivní sestra",
        "reverse_label_unknown": "adoptivní sourozenec",
    },
    {
        "code": "step_sibling",
        "name": "Nevlastní sourozenectví",
        "description": "Nevlastní sourozenectví.",
        "category": "sibling",
        "sort_order": 100,
        "is_symmetric": True,
        "supports_date_range": True,
        "is_derivable": False,
        "forward_label_male": "nevlastní bratr",
        "forward_label_female": "nevlastní sestra",
        "forward_label_unknown": "nevlastní sourozenec",
        "reverse_label_male": "nevlastní bratr",
        "reverse_label_female": "nevlastní sestra",
        "reverse_label_unknown": "nevlastní sourozenec",
    },
    {
        "code": "social_sibling",
        "name": "Sourozenecká sociální vazba",
        "description": (
            "Sourozenecká sociální vazba bez biologického nebo právního "
            "základu."
        ),
        "category": "sibling",
        "sort_order": 110,
        "is_symmetric": True,
        "supports_date_range": True,
        "is_derivable": False,
        "forward_label_male": "blízký jako bratr",
        "forward_label_female": "blízká jako sestra",
        "forward_label_unknown": "blízký jako sourozenec",
        "reverse_label_male": "blízký jako bratr",
        "reverse_label_female": "blízká jako sestra",
        "reverse_label_unknown": "blízký jako sourozenec",
    },
    {
        "code": "godparent",
        "name": "Kmotrovství",
        "description": "Vztah kmotra nebo kmotry a kmotřence.",
        "category": "godparent",
        "sort_order": 120,
        "is_symmetric": False,
        "supports_date_range": False,
        "is_derivable": False,
        "forward_label_male": "kmotřenec",
        "forward_label_female": "kmotřenka",
        "forward_label_unknown": "kmotřenec nebo kmotřenka",
        "reverse_label_male": "kmotr",
        "reverse_label_female": "kmotra",
        "reverse_label_unknown": "kmotr nebo kmotra",
    },
    {
        "code": "family_friend",
        "name": "Rodinné přátelství",
        "description": "Blízká přátelská vazba osoby k rodině.",
        "category": "social",
        "sort_order": 130,
        "is_symmetric": True,
        "supports_date_range": True,
        "is_derivable": False,
        "forward_label_male": "rodinný přítel",
        "forward_label_female": "rodinná přítelkyně",
        "forward_label_unknown": "rodinný přítel nebo přítelkyně",
        "reverse_label_male": "rodinný přítel",
        "reverse_label_female": "rodinná přítelkyně",
        "reverse_label_unknown": "rodinný přítel nebo přítelkyně",
    },
    {
        "code": "other",
        "name": "Jiná vazba",
        "description": "Jiná rodinná nebo sociální vazba.",
        "category": "other",
        "sort_order": 140,
        "is_symmetric": True,
        "supports_date_range": True,
        "is_derivable": False,
        "forward_label_male": "související osoba",
        "forward_label_female": "související osoba",
        "forward_label_unknown": "související osoba",
        "reverse_label_male": "související osoba",
        "reverse_label_female": "související osoba",
        "reverse_label_unknown": "související osoba",
    },
)
INITIAL_RELATIONSHIP_TYPE_CODES = tuple(
    relationship_type["code"]
    for relationship_type in INITIAL_RELATIONSHIP_TYPES
)


def create_initial_relationship_types(apps, schema_editor) -> None:
    relationship_type_model = apps.get_model(
        "people",
        "RelationshipType",
    )

    for relationship_type in INITIAL_RELATIONSHIP_TYPES:
        defaults = relationship_type.copy()
        code = defaults.pop("code")
        defaults.update(is_active=True, is_system=True)
        relationship_type_model.objects.update_or_create(
            code=code,
            defaults=defaults,
        )


def remove_initial_relationship_types(apps, schema_editor) -> None:
    relationship_type_model = apps.get_model(
        "people",
        "RelationshipType",
    )
    relationship_type_model.objects.filter(
        code__in=INITIAL_RELATIONSHIP_TYPE_CODES,
        is_system=True,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("people", "0006_relationship_type"),
    ]

    operations = [
        migrations.RunPython(
            create_initial_relationship_types,
            remove_initial_relationship_types,
        ),
    ]

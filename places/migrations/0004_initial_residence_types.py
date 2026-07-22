from django.db import migrations


INITIAL_RESIDENCE_TYPES = (
    {
        "code": "primary_residence",
        "name": "Hlavní bydliště",
        "description": (
            "Obvyklé nebo hlavní bydliště osoby v daném období."
        ),
        "sort_order": 10,
    },
    {
        "code": "temporary_residence",
        "name": "Dočasné bydliště",
        "description": (
            "Časově omezené bydliště nebo pobyt mimo hlavní bydliště."
        ),
        "sort_order": 20,
    },
    {
        "code": "official_residence",
        "name": "Úřední bydliště",
        "description": (
            "Administrativně nebo úředně evidovaná adresa, která nemusí "
            "odpovídat skutečnému pobytu."
        ),
        "sort_order": 30,
    },
    {
        "code": "institutional_residence",
        "name": "Institucionální pobyt",
        "description": (
            "Pobyt v instituci, například internátu, kasárnách, nemocnici, "
            "ústavu nebo domově."
        ),
        "sort_order": 40,
    },
    {
        "code": "other",
        "name": "Jiné bydliště",
        "description": (
            "Jiný druh bydliště nebo pobytu nezařaditelný do předchozích "
            "typů."
        ),
        "sort_order": 90,
    },
)
INITIAL_RESIDENCE_TYPE_CODES = tuple(
    residence_type["code"] for residence_type in INITIAL_RESIDENCE_TYPES
)


def create_initial_residence_types(apps, schema_editor) -> None:
    residence_type_model = apps.get_model("places", "ResidenceType")
    conflicting_codes = tuple(
        residence_type_model.objects.filter(
            code__in=INITIAL_RESIDENCE_TYPE_CODES,
            is_system=False,
        )
        .order_by("code")
        .values_list("code", flat=True)
    )
    if conflicting_codes:
        raise RuntimeError(
            "Systémové kódy typů bydliště kolidují s uživatelskými "
            f"záznamy: {', '.join(conflicting_codes)}."
        )

    for residence_type in INITIAL_RESIDENCE_TYPES:
        residence_type_model.objects.update_or_create(
            code=residence_type["code"],
            defaults={
                "name": residence_type["name"],
                "description": residence_type["description"],
                "sort_order": residence_type["sort_order"],
                "is_active": True,
                "is_system": True,
            },
        )


def remove_initial_residence_types(apps, schema_editor) -> None:
    residence_type_model = apps.get_model("places", "ResidenceType")
    residence_type_model.objects.filter(
        code__in=INITIAL_RESIDENCE_TYPE_CODES,
        is_system=True,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("places", "0003_residence_type"),
    ]

    operations = [
        migrations.RunPython(
            create_initial_residence_types,
            remove_initial_residence_types,
        ),
    ]

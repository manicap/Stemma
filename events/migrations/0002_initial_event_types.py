from django.db import migrations


INITIAL_EVENT_TYPES = (
    {
        "code": "birth",
        "name": "Narození",
        "description": "Narození osoby.",
        "sort_order": 10,
        "supports_date_range": False,
        "allows_place": True,
        "default_show_in_overview": True,
        "default_access_level": "public",
    },
    {
        "code": "baptism",
        "name": "Křest",
        "description": "Křest osoby.",
        "sort_order": 20,
        "supports_date_range": False,
        "allows_place": True,
        "default_show_in_overview": False,
        "default_access_level": "public",
    },
    {
        "code": "marriage",
        "name": "Sňatek",
        "description": "Uzavření manželství.",
        "sort_order": 30,
        "supports_date_range": False,
        "allows_place": True,
        "default_show_in_overview": True,
        "default_access_level": "public",
    },
    {
        "code": "divorce",
        "name": "Rozvod",
        "description": "Ukončení manželství rozvodem.",
        "sort_order": 40,
        "supports_date_range": False,
        "allows_place": True,
        "default_show_in_overview": False,
        "default_access_level": "public",
    },
    {
        "code": "relocation",
        "name": "Stěhování",
        "description": "Přestěhování osoby nebo domácnosti.",
        "sort_order": 50,
        "supports_date_range": False,
        "allows_place": True,
        "default_show_in_overview": False,
        "default_access_level": "public",
    },
    {
        "code": "education",
        "name": "Studium",
        "description": (
            "Studium na škole nebo v jiném vzdělávacím programu."
        ),
        "sort_order": 60,
        "supports_date_range": True,
        "allows_place": True,
        "default_show_in_overview": False,
        "default_access_level": "public",
    },
    {
        "code": "graduation",
        "name": "Maturita",
        "description": (
            "Složení maturity nebo obdobné závěrečné zkoušky."
        ),
        "sort_order": 70,
        "supports_date_range": False,
        "allows_place": True,
        "default_show_in_overview": False,
        "default_access_level": "public",
    },
    {
        "code": "military_service",
        "name": "Vojenská služba",
        "description": "Výkon vojenské služby.",
        "sort_order": 80,
        "supports_date_range": True,
        "allows_place": True,
        "default_show_in_overview": False,
        "default_access_level": "public",
    },
    {
        "code": "employment",
        "name": "Zaměstnání",
        "description": "Pracovní nebo profesní působení.",
        "sort_order": 90,
        "supports_date_range": True,
        "allows_place": True,
        "default_show_in_overview": False,
        "default_access_level": "public",
    },
    {
        "code": "death",
        "name": "Úmrtí",
        "description": "Úmrtí osoby.",
        "sort_order": 100,
        "supports_date_range": False,
        "allows_place": True,
        "default_show_in_overview": True,
        "default_access_level": "public",
    },
    {
        "code": "funeral",
        "name": "Pohřeb",
        "description": "Pohřeb nebo jiné rozloučení se zemřelým.",
        "sort_order": 110,
        "supports_date_range": False,
        "allows_place": True,
        "default_show_in_overview": False,
        "default_access_level": "public",
    },
    {
        "code": "other",
        "name": "Jiná událost",
        "description": "Jiná životní událost.",
        "sort_order": 120,
        "supports_date_range": True,
        "allows_place": True,
        "default_show_in_overview": False,
        "default_access_level": "public",
    },
)
INITIAL_EVENT_TYPE_CODES = tuple(
    event_type["code"] for event_type in INITIAL_EVENT_TYPES
)


def create_initial_event_types(apps, schema_editor) -> None:
    event_type = apps.get_model("events", "EventType")

    for values in INITIAL_EVENT_TYPES:
        event_type.objects.update_or_create(
            code=values["code"],
            defaults={
                "name": values["name"],
                "description": values["description"],
                "sort_order": values["sort_order"],
                "is_active": True,
                "is_system": True,
                "supports_date_range": values[
                    "supports_date_range"
                ],
                "allows_place": values["allows_place"],
                "default_show_in_overview": values[
                    "default_show_in_overview"
                ],
                "default_access_level": values[
                    "default_access_level"
                ],
            },
        )


def remove_initial_event_types(apps, schema_editor) -> None:
    event_type = apps.get_model("events", "EventType")
    event_type.objects.filter(
        code__in=INITIAL_EVENT_TYPE_CODES
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0001_event_type"),
    ]

    operations = [
        migrations.RunPython(
            create_initial_event_types,
            remove_initial_event_types,
        ),
    ]

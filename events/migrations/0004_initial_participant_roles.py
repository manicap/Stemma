from django.db import migrations


INITIAL_PARTICIPANT_ROLES = (
    {
        "code": "subject",
        "name": "Hlavní osoba",
        "description": "Osoba, které se událost primárně týká.",
        "sort_order": 10,
    },
    {
        "code": "born_person",
        "name": "Narozená osoba",
        "description": "Osoba, jejíž narození událost eviduje.",
        "sort_order": 20,
    },
    {
        "code": "baptized_person",
        "name": "Křtěná osoba",
        "description": "Osoba, jejíž křest událost eviduje.",
        "sort_order": 30,
    },
    {
        "code": "deceased_person",
        "name": "Zemřelá osoba",
        "description": (
            "Osoba, jejíž úmrtí nebo pohřeb událost eviduje."
        ),
        "sort_order": 40,
    },
    {
        "code": "spouse",
        "name": "Manželský partner",
        "description": "Partner při sňatku nebo rozvodu.",
        "sort_order": 50,
    },
    {
        "code": "parent",
        "name": "Rodič",
        "description": "Rodič hlavní osoby nebo jiného účastníka.",
        "sort_order": 60,
    },
    {
        "code": "child",
        "name": "Dítě",
        "description": "Dítě hlavní osoby nebo jiného účastníka.",
        "sort_order": 70,
    },
    {
        "code": "godparent",
        "name": "Kmotr nebo kmotra",
        "description": "Kmotr nebo kmotra při křtu.",
        "sort_order": 80,
    },
    {
        "code": "witness",
        "name": "Svědek",
        "description": "Svědek události.",
        "sort_order": 90,
    },
    {
        "code": "participant",
        "name": "Účastník",
        "description": "Další osoba přímo účastná události.",
        "sort_order": 100,
    },
    {
        "code": "other",
        "name": "Jiná role",
        "description": "Jiná role osoby v události.",
        "sort_order": 110,
    },
)
INITIAL_PARTICIPANT_ROLE_CODES = tuple(
    role["code"] for role in INITIAL_PARTICIPANT_ROLES
)


def create_initial_participant_roles(apps, schema_editor) -> None:
    participant_role = apps.get_model("events", "ParticipantRole")

    for role in INITIAL_PARTICIPANT_ROLES:
        participant_role.objects.update_or_create(
            code=role["code"],
            defaults={
                "name": role["name"],
                "description": role["description"],
                "sort_order": role["sort_order"],
                "is_active": True,
                "is_system": True,
            },
        )


def remove_initial_participant_roles(apps, schema_editor) -> None:
    participant_role = apps.get_model("events", "ParticipantRole")
    participant_role.objects.filter(
        code__in=INITIAL_PARTICIPANT_ROLE_CODES
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0003_participant_role_allowed_event_role"),
    ]

    operations = [
        migrations.RunPython(
            create_initial_participant_roles,
            remove_initial_participant_roles,
        ),
    ]

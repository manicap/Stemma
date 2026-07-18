from django.db import migrations


INITIAL_ALLOWED_EVENT_ROLES = (
    ("birth", "born_person", 1, 1, 10),
    ("birth", "parent", 0, 2, 20),
    ("birth", "witness", 0, None, 30),
    ("birth", "participant", 0, None, 80),
    ("birth", "other", 0, None, 90),
    ("baptism", "baptized_person", 1, 1, 10),
    ("baptism", "parent", 0, 2, 20),
    ("baptism", "godparent", 0, None, 30),
    ("baptism", "witness", 0, None, 40),
    ("baptism", "participant", 0, None, 80),
    ("baptism", "other", 0, None, 90),
    ("marriage", "spouse", 2, 2, 10),
    ("marriage", "parent", 0, None, 20),
    ("marriage", "witness", 0, None, 30),
    ("marriage", "participant", 0, None, 80),
    ("marriage", "other", 0, None, 90),
    ("divorce", "spouse", 1, 2, 10),
    ("divorce", "witness", 0, None, 30),
    ("divorce", "participant", 0, None, 80),
    ("divorce", "other", 0, None, 90),
    ("relocation", "subject", 1, None, 10),
    ("relocation", "participant", 0, None, 80),
    ("relocation", "other", 0, None, 90),
    ("education", "subject", 1, 1, 10),
    ("education", "participant", 0, None, 80),
    ("education", "other", 0, None, 90),
    ("graduation", "subject", 1, 1, 10),
    ("graduation", "witness", 0, None, 30),
    ("graduation", "participant", 0, None, 80),
    ("graduation", "other", 0, None, 90),
    ("military_service", "subject", 1, 1, 10),
    ("military_service", "participant", 0, None, 80),
    ("military_service", "other", 0, None, 90),
    ("employment", "subject", 1, 1, 10),
    ("employment", "participant", 0, None, 80),
    ("employment", "other", 0, None, 90),
    ("death", "deceased_person", 1, 1, 10),
    ("death", "witness", 0, None, 30),
    ("death", "participant", 0, None, 80),
    ("death", "other", 0, None, 90),
    ("funeral", "deceased_person", 1, 1, 10),
    ("funeral", "witness", 0, None, 30),
    ("funeral", "participant", 0, None, 80),
    ("funeral", "other", 0, None, 90),
    ("other", "subject", 1, None, 10),
    ("other", "parent", 0, None, 20),
    ("other", "child", 0, None, 30),
    ("other", "spouse", 0, None, 40),
    ("other", "godparent", 0, None, 50),
    ("other", "witness", 0, None, 60),
    ("other", "participant", 0, None, 80),
    ("other", "other", 0, None, 90),
)


def _get_by_code(model, code: str, label: str):
    try:
        return model.objects.get(code=code)
    except model.DoesNotExist as exc:
        raise RuntimeError(
            f"Chybí systémový záznam {label} s kódem '{code}'."
        ) from exc


def create_initial_allowed_event_roles(apps, schema_editor) -> None:
    event_type = apps.get_model("events", "EventType")
    participant_role = apps.get_model("events", "ParticipantRole")
    allowed_event_role = apps.get_model("events", "AllowedEventRole")

    event_types = {
        code: _get_by_code(event_type, code, "EventType")
        for code in {
            rule[0] for rule in INITIAL_ALLOWED_EVENT_ROLES
        }
    }
    participant_roles = {
        code: _get_by_code(participant_role, code, "ParticipantRole")
        for code in {
            rule[1] for rule in INITIAL_ALLOWED_EVENT_ROLES
        }
    }

    for (
        event_type_code,
        participant_role_code,
        min_count,
        max_count,
        sort_order,
    ) in INITIAL_ALLOWED_EVENT_ROLES:
        allowed_event_role.objects.update_or_create(
            event_type=event_types[event_type_code],
            participant_role=participant_roles[participant_role_code],
            defaults={
                "min_count": min_count,
                "max_count": max_count,
                "sort_order": sort_order,
                "is_active": True,
                "is_system": True,
            },
        )


def remove_initial_allowed_event_roles(apps, schema_editor) -> None:
    allowed_event_role = apps.get_model("events", "AllowedEventRole")

    for event_type_code, participant_role_code, *_ in (
        INITIAL_ALLOWED_EVENT_ROLES
    ):
        allowed_event_role.objects.filter(
            event_type__code=event_type_code,
            participant_role__code=participant_role_code,
            is_system=True,
        ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0004_initial_participant_roles"),
    ]

    operations = [
        migrations.RunPython(
            create_initial_allowed_event_roles,
            remove_initial_allowed_event_roles,
        ),
    ]

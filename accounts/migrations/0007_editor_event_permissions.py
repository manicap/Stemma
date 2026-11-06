from django.db import migrations


EVENT_PERMISSION_CODENAMES = ("add_event", "change_event")


def grant_editor_event_permissions(apps, schema_editor) -> None:
    content_type_model = apps.get_model("contenttypes", "ContentType")
    group_model = apps.get_model("auth", "Group")
    permission_model = apps.get_model("auth", "Permission")

    content_type, _ = content_type_model.objects.get_or_create(
        app_label="events",
        model="event",
    )
    permissions = tuple(
        permission_model.objects.get_or_create(
            content_type=content_type,
            codename=codename,
            defaults={"name": f"Can {codename.replace('_', ' ')}"},
        )[0]
        for codename in EVENT_PERMISSION_CODENAMES
    )
    editor, _ = group_model.objects.get_or_create(name="Editor")
    editor.permissions.add(*permissions)


def revoke_editor_event_permissions(apps, schema_editor) -> None:
    group_model = apps.get_model("auth", "Group")
    permission_model = apps.get_model("auth", "Permission")
    editor = group_model.objects.filter(name="Editor").first()
    if editor is None:
        return
    permissions = permission_model.objects.filter(
        content_type__app_label="events",
        content_type__model="event",
        codename__in=EVENT_PERMISSION_CODENAMES,
    )
    editor.permissions.remove(*permissions)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_editor_add_person_permission"),
        ("events", "0008_deathdetail"),
    ]

    operations = [
        migrations.RunPython(
            grant_editor_event_permissions,
            revoke_editor_event_permissions,
        ),
    ]

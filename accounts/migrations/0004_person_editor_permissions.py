from django.db import migrations


ROLE_GROUP_NAMES = ("Editor", "Správce")


def grant_person_editor_permission(apps, schema_editor) -> None:
    content_type_model = apps.get_model("contenttypes", "ContentType")
    group_model = apps.get_model("auth", "Group")
    permission_model = apps.get_model("auth", "Permission")

    content_type, _ = content_type_model.objects.get_or_create(
        app_label="people",
        model="person",
    )
    permission, _ = permission_model.objects.get_or_create(
        content_type=content_type,
        codename="change_person",
        defaults={"name": "Can change Osoba"},
    )
    reader, _ = group_model.objects.get_or_create(name="Čtenář")
    reader.permissions.remove(permission)
    for group_name in ROLE_GROUP_NAMES:
        group, _ = group_model.objects.get_or_create(name=group_name)
        group.permissions.add(permission)


def revoke_person_editor_permission(apps, schema_editor) -> None:
    group_model = apps.get_model("auth", "Group")
    permission_model = apps.get_model("auth", "Permission")
    permission = permission_model.objects.filter(
        content_type__app_label="people",
        content_type__model="person",
        codename="change_person",
    ).first()
    if permission is None:
        return
    for group in group_model.objects.filter(name__in=ROLE_GROUP_NAMES):
        group.permissions.remove(permission)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_initial_permission_groups"),
        ("people", "0009_alter_person_options"),
    ]

    operations = [
        migrations.RunPython(
            grant_person_editor_permission,
            revoke_person_editor_permission,
        ),
    ]

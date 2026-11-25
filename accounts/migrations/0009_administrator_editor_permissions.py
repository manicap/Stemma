from django.db import migrations


ADMINISTRATOR_GROUP_NAME = "Správce"
EDITOR_WRITE_PERMISSIONS = (
    ("people", "person", "add_person"),
    ("events", "event", "add_event"),
    ("events", "event", "change_event"),
    ("people", "relationship", "add_relationship"),
    ("people", "relationship", "change_relationship"),
)


def grant_administrator_editor_permissions(apps, schema_editor) -> None:
    content_type_model = apps.get_model("contenttypes", "ContentType")
    group_model = apps.get_model("auth", "Group")
    permission_model = apps.get_model("auth", "Permission")

    permissions = []
    for app_label, model, codename in EDITOR_WRITE_PERMISSIONS:
        content_type, _ = content_type_model.objects.get_or_create(
            app_label=app_label,
            model=model,
        )
        permission, _ = permission_model.objects.get_or_create(
            content_type=content_type,
            codename=codename,
            defaults={"name": f"Can {codename.replace('_', ' ')}"},
        )
        permissions.append(permission)
    administrator, _ = group_model.objects.get_or_create(
        name=ADMINISTRATOR_GROUP_NAME
    )
    administrator.permissions.add(*permissions)


def revoke_administrator_editor_permissions(apps, schema_editor) -> None:
    group_model = apps.get_model("auth", "Group")
    permission_model = apps.get_model("auth", "Permission")
    administrator = group_model.objects.filter(
        name=ADMINISTRATOR_GROUP_NAME
    ).first()
    if administrator is None:
        return
    for app_label, model, codename in EDITOR_WRITE_PERMISSIONS:
        administrator.permissions.remove(
            *permission_model.objects.filter(
                content_type__app_label=app_label,
                content_type__model=model,
                codename=codename,
            )
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0008_editor_relationship_permissions"),
    ]

    operations = [
        migrations.RunPython(
            grant_administrator_editor_permissions,
            revoke_administrator_editor_permissions,
        ),
    ]

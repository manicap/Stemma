from django.db import migrations


PERMISSION_DEFINITIONS = (
    (
        "accounts",
        "user",
        "view_restricted_content",
        "Může zobrazit omezený obsah",
    ),
    (
        "accounts",
        "user",
        "view_admin_only_content",
        "Může zobrazit obsah pouze pro správce",
    ),
    (
        "people",
        "person",
        "view_archived_person",
        "Může zobrazit archivované osoby",
    ),
    (
        "people",
        "person",
        "view_deleted_person",
        "Může zobrazit měkce odstraněné osoby",
    ),
)
SYSTEM_GROUP_NAMES = ("Čtenář", "Editor", "Správce")


def _get_permissions(apps):
    content_type_model = apps.get_model("contenttypes", "ContentType")
    permission_model = apps.get_model("auth", "Permission")
    permissions = []

    for app_label, model, codename, name in PERMISSION_DEFINITIONS:
        content_type, _ = content_type_model.objects.get_or_create(
            app_label=app_label,
            model=model,
        )
        permission, _ = permission_model.objects.get_or_create(
            content_type=content_type,
            codename=codename,
            defaults={"name": name},
        )
        if permission.name != name:
            permission.name = name
            permission.save(update_fields=("name",))
        permissions.append(permission)

    return permissions


def configure_permission_groups(apps, schema_editor) -> None:
    group_model = apps.get_model("auth", "Group")
    permissions = _get_permissions(apps)
    groups = {
        name: group_model.objects.get_or_create(name=name)[0]
        for name in SYSTEM_GROUP_NAMES
    }

    groups["Čtenář"].permissions.remove(*permissions)
    groups["Editor"].permissions.remove(*permissions)
    groups["Správce"].permissions.add(*permissions)


def unconfigure_permission_groups(apps, schema_editor) -> None:
    group_model = apps.get_model("auth", "Group")
    permission_model = apps.get_model("auth", "Permission")
    permission_filters = [
        {
            "content_type__app_label": app_label,
            "content_type__model": model,
            "codename": codename,
        }
        for app_label, model, codename, _ in PERMISSION_DEFINITIONS
    ]
    permissions = []
    for permission_filter in permission_filters:
        permission = permission_model.objects.filter(
            **permission_filter
        ).first()
        if permission is not None:
            permissions.append(permission)

    for group in group_model.objects.filter(name__in=SYSTEM_GROUP_NAMES):
        group.permissions.remove(*permissions)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_alter_user_options"),
        ("people", "0009_alter_person_options"),
    ]

    operations = [
        migrations.RunPython(
            configure_permission_groups,
            unconfigure_permission_groups,
        ),
    ]

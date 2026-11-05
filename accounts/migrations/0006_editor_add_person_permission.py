from django.db import migrations


def grant_editor_add_person_permission(apps, schema_editor) -> None:
    content_type_model = apps.get_model("contenttypes", "ContentType")
    group_model = apps.get_model("auth", "Group")
    permission_model = apps.get_model("auth", "Permission")

    content_type, _ = content_type_model.objects.get_or_create(
        app_label="people",
        model="person",
    )
    permission, _ = permission_model.objects.get_or_create(
        content_type=content_type,
        codename="add_person",
        defaults={"name": "Can add Osoba"},
    )
    editor, _ = group_model.objects.get_or_create(name="Editor")
    editor.permissions.add(permission)


def revoke_editor_add_person_permission(apps, schema_editor) -> None:
    group_model = apps.get_model("auth", "Group")
    permission_model = apps.get_model("auth", "Permission")
    permission = permission_model.objects.filter(
        content_type__app_label="people",
        content_type__model="person",
        codename="add_person",
    ).first()
    if permission is None:
        return
    editor = group_model.objects.filter(name="Editor").first()
    if editor is not None:
        editor.permissions.remove(permission)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_alter_user_managers"),
        ("people", "0010_person_titles_biography"),
    ]

    operations = [
        migrations.RunPython(
            grant_editor_add_person_permission,
            revoke_editor_add_person_permission,
        ),
    ]

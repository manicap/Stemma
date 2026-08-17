from dataclasses import dataclass
from getpass import getpass

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


@dataclass(frozen=True, slots=True)
class _DemoAccount:
    username: str
    group_name: str
    first_name: str
    last_name: str

    @property
    def marker_email(self) -> str:
        return f"{self.username}@example.invalid"


_DEMO_ACCOUNTS = (
    _DemoAccount(
        username="stemma-demo-reader",
        group_name="Čtenář",
        first_name="Demo",
        last_name="Čtenář",
    ),
    _DemoAccount(
        username="stemma-demo-editor",
        group_name="Editor",
        first_name="Demo",
        last_name="Editor",
    ),
    _DemoAccount(
        username="stemma-demo-administrator",
        group_name="Správce",
        first_name="Demo",
        last_name="Správce",
    ),
)
_PERSON_EDITOR_PERMISSION = ("people", "change_person")
_ELEVATED_PERMISSIONS = (
    ("accounts", "view_restricted_content"),
    ("accounts", "view_admin_only_content"),
    ("people", "view_archived_person"),
    ("people", "view_deleted_person"),
)
_ROLE_PERMISSIONS = (_PERSON_EDITOR_PERMISSION, *_ELEVATED_PERMISSIONS)


class Command(BaseCommand):
    help = (
        "Vytvoří nebo resetuje lokální demo účty Čtenáře, Editora a Správce."
    )

    def handle(self, *args, **options) -> None:
        if not settings.DEBUG:
            raise CommandError(
                "Demo účty lze spravovat pouze v lokálním režimu DEBUG."
            )

        groups = {
            group.name: group
            for group in Group.objects.filter(
                name__in={account.group_name for account in _DEMO_ACCOUNTS}
            )
        }
        missing_groups = sorted(
            account.group_name
            for account in _DEMO_ACCOUNTS
            if account.group_name not in groups
        )
        if missing_groups:
            raise CommandError(
                "Chybí systémové skupiny: "
                f"{', '.join(missing_groups)}. Nejdříve spusťte migrace."
            )

        permissions = {
            (permission.content_type.app_label, permission.codename): permission
            for permission in Permission.objects.select_related(
                "content_type"
            ).filter(
                content_type__app_label__in={
                    app_label for app_label, _ in _ROLE_PERMISSIONS
                },
                codename__in={
                    codename for _, codename in _ROLE_PERMISSIONS
                },
            )
            if (
                permission.content_type.app_label,
                permission.codename,
            ) in _ROLE_PERMISSIONS
        }
        missing_permissions = sorted(set(_ROLE_PERMISSIONS) - permissions.keys())
        if missing_permissions:
            formatted = ", ".join(
                f"{app_label}.{codename}"
                for app_label, codename in missing_permissions
            )
            raise CommandError(
                f"Chybí systémová oprávnění: {formatted}. "
                "Nejdříve spusťte migrace."
            )

        user_model = get_user_model()
        existing_users = {
            user.username: user
            for user in user_model._default_manager.filter(
                username__in={account.username for account in _DEMO_ACCOUNTS}
            )
        }
        for account in _DEMO_ACCOUNTS:
            existing = existing_users.get(account.username)
            if (
                existing is not None
                and existing.email != account.marker_email
            ):
                raise CommandError(
                    f"Uživatelské jméno {account.username!r} již používá "
                    "účet, který nevytvořil lokální demo bootstrap."
                )

        password = getpass("Nové lokální demo heslo: ")
        confirmation = getpass("Heslo znovu pro potvrzení: ")
        if password != confirmation:
            raise CommandError("Zadaná hesla se neshodují.")
        try:
            for account in _DEMO_ACCOUNTS:
                candidate = user_model(
                    username=account.username,
                    first_name=account.first_name,
                    last_name=account.last_name,
                    email=account.marker_email,
                )
                validate_password(password, user=candidate)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from error

        created_count = 0
        reset_count = 0
        with transaction.atomic():
            all_role_permissions = tuple(permissions.values())
            elevated_permissions = tuple(
                permissions[key] for key in _ELEVATED_PERMISSIONS
            )
            editor_permission = permissions[_PERSON_EDITOR_PERMISSION]
            groups["Čtenář"].permissions.remove(*all_role_permissions)
            groups["Editor"].permissions.remove(*elevated_permissions)
            groups["Editor"].permissions.add(editor_permission)
            groups["Správce"].permissions.add(*all_role_permissions)

            for account in _DEMO_ACCOUNTS:
                user, created = user_model._default_manager.get_or_create(
                    username=account.username,
                    defaults={"email": account.marker_email},
                )
                if user.email != account.marker_email:
                    raise CommandError(
                        f"Účet {account.username!r} přestal patřit demo "
                        "bootstrapu; nebyl změněn."
                    )
                user.first_name = account.first_name
                user.last_name = account.last_name
                user.is_active = True
                user.is_staff = False
                user.is_superuser = False
                user.set_password(password)
                user.save()
                user.groups.set((groups[account.group_name],))
                user.user_permissions.clear()
                if created:
                    created_count += 1
                else:
                    reset_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Hotovo: "
                f"nové účty {created_count}, resetované účty {reset_count}."
            )
        )
        self.stdout.write("Lokální demo uživatelská jména:")
        for account in _DEMO_ACCOUNTS:
            self.stdout.write(
                f"- {account.group_name}: {account.username}"
            )
        self.stdout.write(
            "Použijte heslo zadané v tomto běhu. Příkaz lze kdykoli "
            "spustit znovu pro bezpečný reset."
        )

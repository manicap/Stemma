from dataclasses import dataclass

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from common.choices import AccessLevel, Gender, VerificationStatus
from people.models import Person
from people.services import PersonInput, create_person


@dataclass(frozen=True, slots=True)
class _DemoPerson:
    first_name: str
    last_name: str
    gender: str
    access_level: str
    marker: str
    description: str


_DEMO_PEOPLE = (
    _DemoPerson(
        first_name="Anna",
        last_name="Nováková",
        gender=Gender.FEMALE,
        access_level=AccessLevel.PUBLIC,
        marker="[stemma-demo:public]",
        description="Ukázkový veřejný profil.",
    ),
    _DemoPerson(
        first_name="Jan",
        last_name="Novák",
        gender=Gender.MALE,
        access_level=AccessLevel.AUTHENTICATED,
        marker="[stemma-demo:authenticated]",
        description="Ukázkový profil pro přihlášené.",
    ),
    _DemoPerson(
        first_name="Klára",
        last_name="Svobodová",
        gender=Gender.FEMALE,
        access_level=AccessLevel.RESTRICTED,
        marker="[stemma-demo:restricted]",
        description="Ukázkový omezený profil.",
    ),
)


class Command(BaseCommand):
    help = "Bezpečně doplní označené syntetické osoby pro lokální UI."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Pouze vypíše plán bez zápisu do databáze.",
        )

    def handle(self, *args, **options) -> None:
        if not settings.DEBUG:
            raise CommandError(
                "Ukázková data lze vytvořit pouze v lokálním režimu DEBUG."
            )

        dry_run = options["dry_run"]
        created_count = 0
        existing_count = 0

        with transaction.atomic():
            for demo in _DEMO_PEOPLE:
                if Person.objects.filter(notes__contains=demo.marker).exists():
                    existing_count += 1
                    continue
                if dry_run:
                    created_count += 1
                    continue
                create_person(
                    data=PersonInput(
                        first_name=demo.first_name,
                        last_name=demo.last_name,
                        gender=demo.gender,
                        notes=f"{demo.description} {demo.marker}",
                        access_level=demo.access_level,
                        verification_status=VerificationStatus.UNCONFIRMED,
                    )
                )
                created_count += 1

            if dry_run:
                transaction.set_rollback(True)

        mode = "Plán" if dry_run else "Hotovo"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: nové {created_count}, již existující {existing_count}."
            )
        )

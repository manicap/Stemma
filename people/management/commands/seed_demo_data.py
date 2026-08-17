from dataclasses import dataclass

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from common.choices import (
    AccessLevel,
    DatePrecision,
    Gender,
    VerificationStatus,
)
from events.models import Event, EventParticipant, EventType, ParticipantRole
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


@dataclass(frozen=True, slots=True)
class _DemoLifeEvent:
    person_marker: str
    event_type_code: str
    role_code: str
    marker: str
    year: int
    month: int = 1
    day: int = 1


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
    _DemoPerson(
        first_name="Josef",
        last_name="Dvořák",
        gender=Gender.MALE,
        access_level=AccessLevel.PUBLIC,
        marker="[stemma-demo:derived:older]",
        description="Starší ukázka odvozených životních údajů.",
    ),
    _DemoPerson(
        first_name="Josef",
        last_name="Dvořák",
        gender=Gender.MALE,
        access_level=AccessLevel.PUBLIC,
        marker="[stemma-demo:derived:younger]",
        description="Mladší ukázka odvozených životních údajů.",
    ),
)
_DEMO_LIFE_EVENTS = (
    _DemoLifeEvent(
        person_marker="[stemma-demo:derived:older]",
        event_type_code="birth",
        role_code="born_person",
        marker="[stemma-demo-event:derived:older:birth]",
        year=1900,
    ),
    _DemoLifeEvent(
        person_marker="[stemma-demo:derived:older]",
        event_type_code="death",
        role_code="deceased_person",
        marker="[stemma-demo-event:derived:older:death]",
        year=1980,
    ),
    _DemoLifeEvent(
        person_marker="[stemma-demo:derived:younger]",
        event_type_code="birth",
        role_code="born_person",
        marker="[stemma-demo-event:derived:younger:birth]",
        year=1950,
    ),
)


class Command(BaseCommand):
    help = (
        "Bezpečně doplní označené syntetické osoby a životní události "
        "pro lokální UI."
    )

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
        created_event_count = 0
        existing_event_count = 0

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

            people_by_marker = {
                demo.marker: Person.objects.get(notes__contains=demo.marker)
                for demo in _DEMO_PEOPLE
                if demo.marker.startswith("[stemma-demo:derived:")
                and not dry_run
            }
            event_types = {
                event_type.code: event_type
                for event_type in EventType.objects.filter(
                    code__in={
                        item.event_type_code for item in _DEMO_LIFE_EVENTS
                    }
                )
            }
            roles = {
                role.code: role
                for role in ParticipantRole.objects.filter(
                    code__in={item.role_code for item in _DEMO_LIFE_EVENTS}
                )
            }
            if len(event_types) != 2 or len(roles) != 2:
                raise CommandError(
                    "Chybí systémové typy nebo role událostí. "
                    "Nejdříve spusťte migrace."
                )

            for demo_event in _DEMO_LIFE_EVENTS:
                if Event.objects.filter(
                    title__contains=demo_event.marker
                ).exists():
                    existing_event_count += 1
                    continue
                if dry_run:
                    created_event_count += 1
                    continue
                event = Event(
                    event_type=event_types[demo_event.event_type_code],
                    title=demo_event.marker,
                    date_precision=DatePrecision.EXACT,
                    start_year=demo_event.year,
                    start_month=demo_event.month,
                    start_day=demo_event.day,
                    access_level=AccessLevel.PUBLIC,
                    verification_status=VerificationStatus.UNCONFIRMED,
                )
                event.full_clean()
                event.save()
                participant = EventParticipant(
                    event=event,
                    person=people_by_marker[demo_event.person_marker],
                    role=roles[demo_event.role_code],
                )
                participant.full_clean()
                participant.save()
                created_event_count += 1

            if dry_run:
                transaction.set_rollback(True)

        mode = "Plán" if dry_run else "Hotovo"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: osoby nové {created_count}, "
                f"osoby existující {existing_count}; "
                f"události nové {created_event_count}, "
                f"události existující {existing_event_count}."
            )
        )

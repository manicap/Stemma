from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from common.choices import (
    AccessLevel,
    DatePrecision,
    Gender,
    VerificationStatus,
)
from events.models import Event, EventType, ParticipantRole
from events.services import EventInput, EventParticipantInput, create_event
from health.models import HealthRecord, HealthRecordType
from health.services import HealthRecordInput
from health.use_cases import (
    create_health_record,
    create_health_record_attachment,
    create_health_record_source,
)
from materials.choices import FileStatus, SourceSupport
from materials.models import (
    Attachment,
    AttachmentCategory,
    AttachmentRole,
    HealthRecordAttachment,
    HealthRecordSource,
    Source,
    SourceRole,
    SourceType,
)
from materials.services import AttachmentLinkInput
from materials.source_services import SourceLinkInput
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
_DEMO_HEALTH_PERSON_MARKER = "[stemma-demo:restricted]"
_DEMO_HEALTH_RECORD_MARKER = "[stemma-demo-health:checkup]"
_DEMO_HEALTH_ACTOR_USERNAME = "stemma-demo-health-writer"
_DEMO_HEALTH_ACTOR_PERMISSIONS = (
    ("accounts", "user", "view_restricted_content"),
    ("health", "healthrecord", "add_healthrecord"),
    ("materials", "healthrecordattachment", "add_healthrecordattachment"),
    ("materials", "healthrecordsource", "add_healthrecordsource"),
)


def _seed_demo_health_data(*, person: Person) -> None:
    record_type, _ = HealthRecordType.objects.get_or_create(
        code="stemma_demo_checkup",
        defaults={"name": "Preventivní péče"},
    )
    health_record = HealthRecord.objects.filter(
        note__contains=_DEMO_HEALTH_RECORD_MARKER
    ).first()
    required_permissions = tuple(
        Permission.objects.get(
            content_type__app_label=app_label,
            content_type__model=model,
            codename=codename,
        )
        for app_label, model, codename in _DEMO_HEALTH_ACTOR_PERMISSIONS
    )
    user_model = get_user_model()
    seed_actor = user_model.objects.filter(
        username=_DEMO_HEALTH_ACTOR_USERNAME
    ).first()
    if seed_actor is None:
        seed_actor = user_model.objects.create_user(
            username=_DEMO_HEALTH_ACTOR_USERNAME,
        )
    elif (
        seed_actor.has_usable_password()
        or not seed_actor.is_active
        or seed_actor.is_staff
        or seed_actor.is_superuser
    ):
        raise CommandError(
            "Technický actor health ukázky existuje v neočekávaném stavu."
        )
    if (
        seed_actor.groups.exists()
        or seed_actor.user_permissions.exclude(
            pk__in=(permission.pk for permission in required_permissions)
        ).exists()
    ):
        raise CommandError(
            "Technický actor health ukázky má neočekávaná oprávnění."
        )
    seed_actor.user_permissions.add(*required_permissions)

    if health_record is None:
        health_record = create_health_record(
            data=HealthRecordInput(
                person=person,
                record_type=record_type,
                title="Preventivní prohlídka",
                description=(
                    "Syntetická ukázka read-only zdravotního detailu."
                ),
                provider_name="Ukázková rodinná ordinace",
                note=_DEMO_HEALTH_RECORD_MARKER,
                date_precision=DatePrecision.YEAR,
                start_year=2025,
                access_level=AccessLevel.RESTRICTED,
                verification_status=VerificationStatus.UNCONFIRMED,
            ),
            actor=seed_actor,
        )

    category, _ = AttachmentCategory.objects.get_or_create(
        code="stemma_demo_health_document",
        defaults={"name": "Ukázkový zdravotní dokument"},
    )
    attachment_role, _ = AttachmentRole.objects.get_or_create(
        code="stemma_demo_health_evidence",
        defaults={"name": "Lékařská zpráva"},
    )
    attachment, _ = Attachment.objects.get_or_create(
        storage_key="stemma-demo/health/preventive-checkup.pdf",
        defaults={
            "category": category,
            "display_name": "Ukázková zpráva z prohlídky",
            "original_filename": "preventivni-prohlidka.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 2048,
            "sha256": "d" * 64,
            "file_status": FileStatus.AVAILABLE,
            "access_level": AccessLevel.RESTRICTED,
        },
    )
    if not HealthRecordAttachment.objects.filter(
        health_record=health_record,
        attachment=attachment,
        role=attachment_role,
    ).exists():
        create_health_record_attachment(
            health_record=health_record,
            data=AttachmentLinkInput(
                attachment=attachment,
                role=attachment_role,
                context_description=(
                    "Syntetická metadata bez fyzického souboru."
                ),
                access_level=AccessLevel.RESTRICTED,
            ),
            actor=seed_actor,
        )

    source_type, _ = SourceType.objects.get_or_create(
        code="stemma_demo_health_register",
        defaults={"name": "Ukázková zdravotní dokumentace"},
    )
    source_role, _ = SourceRole.objects.get_or_create(
        code="stemma_demo_health_source",
        defaults={"name": "Dokládá záznam"},
    )
    source, _ = Source.objects.get_or_create(
        external_identifier="stemma-demo-health-source",
        defaults={
            "source_type": source_type,
            "title": "Ukázková karta pacienta",
            "full_citation": "Syntetický ambulantní záznam, rok 2025.",
            "access_level": AccessLevel.RESTRICTED,
        },
    )
    if not HealthRecordSource.objects.filter(
        health_record=health_record,
        source=source,
        role=source_role,
    ).exists():
        create_health_record_source(
            health_record=health_record,
            data=SourceLinkInput(
                source=source,
                role=source_role,
                support_strength=SourceSupport.CONFIRMS,
                cited_part="Preventivní kontrola 2025",
                access_level=AccessLevel.RESTRICTED,
            ),
            actor=seed_actor,
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
        created_health_count = 0
        existing_health_count = 0

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
                create_event(
                    data=EventInput(
                        event_type=event_types[
                            demo_event.event_type_code
                        ],
                        title=demo_event.marker,
                        date_precision=DatePrecision.EXACT,
                        start_year=demo_event.year,
                        start_month=demo_event.month,
                        start_day=demo_event.day,
                        access_level=AccessLevel.PUBLIC,
                        verification_status=(
                            VerificationStatus.UNCONFIRMED
                        ),
                    ),
                    participants=(
                        EventParticipantInput(
                            person=people_by_marker[
                                demo_event.person_marker
                            ],
                            role=roles[demo_event.role_code],
                        ),
                    ),
                    require_complete=True,
                )
                created_event_count += 1

            health_exists = HealthRecord.objects.filter(
                note__contains=_DEMO_HEALTH_RECORD_MARKER
            ).exists()
            if health_exists:
                existing_health_count += 1
            else:
                created_health_count += 1
            if not dry_run:
                health_person = Person.objects.get(
                    notes__contains=_DEMO_HEALTH_PERSON_MARKER
                )
                _seed_demo_health_data(person=health_person)

            if dry_run:
                transaction.set_rollback(True)

        mode = "Plán" if dry_run else "Hotovo"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: osoby nové {created_count}, "
                f"osoby existující {existing_count}; "
                f"události nové {created_event_count}, "
                f"události existující {existing_event_count}; "
                f"health ukázky nové {created_health_count}, "
                f"health ukázky existující {existing_health_count}."
            )
        )

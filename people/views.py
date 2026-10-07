from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import (
    ObjectDoesNotExist,
    PermissionDenied,
    ValidationError,
)
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from common.choices import AccessLevel
from health.forms import (
    HealthRecordArchiveForm,
    HealthRecordForm,
    HealthRecordRestoreForm,
    HealthRecordRestoreSoftDeletedForm,
    HealthRecordSoftDeleteForm,
)
from health.models import HealthRecord
from health.permissions import can_view_health_record_access
from health.services import HealthRecordInput
from health.use_cases import (
    archive_health_record,
    create_health_record,
    get_archived_health_record_for_management,
    get_soft_deleted_health_record_for_management,
    get_health_record_detail,
    list_archived_health_records,
    list_health_record_attachments,
    list_health_record_sources,
    list_health_records,
    list_soft_deleted_health_records,
    restore_archived_health_record,
    restore_soft_deleted_health_record,
    soft_delete_health_record,
    update_health_record,
)
from places.models import Place

from .derived_selectors import (
    PersonPresentation,
    get_visible_person_presentations,
)
from .forms import PersonForm
from .models import Person
from .selectors import get_visible_person, get_visible_relationship_overview
from .services import BasicPersonInput, update_person_basic


def _shell_context(
    request: HttpRequest,
    *,
    selected_person: Person | None = None,
    presentations: tuple[PersonPresentation, ...] | None = None,
) -> dict[str, object]:
    if presentations is None:
        presentations = get_visible_person_presentations(actor=request.user)
    facts_by_person_id = {
        presentation.person.pk: presentation.facts
        for presentation in presentations
    }
    return {
        "person_presentations": presentations,
        "selected_person": selected_person,
        "selected_facts": (
            facts_by_person_id.get(selected_person.pk)
            if selected_person is not None
            else None
        ),
    }


def _visible_person_page(
    request: HttpRequest,
    person_id: int,
) -> tuple[tuple[PersonPresentation, ...], PersonPresentation]:
    presentations = get_visible_person_presentations(actor=request.user)
    presentation = next(
        (item for item in presentations if item.person.pk == person_id),
        None,
    )
    if presentation is None:
        raise Http404("Osoba nebyla nalezena.")
    return presentations, presentation


def _render_person_content(
    request: HttpRequest,
    *,
    presentations: tuple[PersonPresentation, ...],
    presentation: PersonPresentation,
    template_name: str,
    context: dict[str, object] | None = None,
) -> HttpResponse:
    content_context = {
        "selected_person": presentation.person,
        "selected_facts": presentation.facts,
    }
    if context is not None:
        content_context.update(context)
    if request.headers.get("HX-Request") == "true":
        return render(request, template_name, content_context)
    return render(
        request,
        "people/person_shell.html",
        _shell_context(
            request,
            selected_person=presentation.person,
            presentations=presentations,
        )
        | content_context
        | {"person_content_template": template_name},
    )


@require_GET
def person_index(request: HttpRequest) -> HttpResponse:
    """Zobraz hlavní obrazovku se seznamem skutečných osob."""

    return render(
        request,
        "people/person_shell.html",
        _shell_context(request),
    )


@require_GET
def person_detail(
    request: HttpRequest,
    person_id: int,
) -> HttpResponse:
    """Zobraz bezpečně autorizovaný detail osoby."""

    presentations, presentation = _visible_person_page(request, person_id)
    return _render_person_content(
        request,
        presentations=presentations,
        presentation=presentation,
        template_name="people/partials/person_detail.html",
        context={"active_person_tab": "overview"},
    )


@require_GET
def person_relationships(
    request: HttpRequest,
    person_id: int,
) -> HttpResponse:
    """Zobraz bezpečný read-only přehled vztahů osoby."""

    presentations, presentation = _visible_person_page(request, person_id)
    relationship_overview = get_visible_relationship_overview(
        person=presentation.person,
        actor=request.user,
    )
    detail_person_ids = {
        item.person.pk for item in presentations
    }
    relationship_presentations = tuple(
        {
            "person": item.person,
            "reasons": item.reasons,
            "detail_url": (
                reverse("people:detail", args=(item.person.pk,))
                if item.person.pk in detail_person_ids
                else None
            ),
        }
        for item in relationship_overview
    )
    return _render_person_content(
        request,
        presentations=presentations,
        presentation=presentation,
        template_name="people/partials/person_relationships.html",
        context={
            "active_person_tab": "relationships",
            "relationship_overview": relationship_presentations,
        },
    )


@require_GET
def person_health(request: HttpRequest, person_id: int) -> HttpResponse:
    """Zobraz bezpečný read-only seznam zdravotních záznamů osoby."""

    presentations, presentation = _visible_person_page(request, person_id)
    health_records = list_health_records(
        person=presentation.person,
        actor=request.user,
    )
    return _render_health_list(
        request,
        presentations=presentations,
        presentation=presentation,
        health_records=health_records,
    )


def _render_health_list(
    request: HttpRequest,
    *,
    presentations: tuple[PersonPresentation, ...],
    presentation: PersonPresentation,
    health_records,
    archived: bool = False,
    deleted: bool = False,
) -> HttpResponse:
    return _render_person_content(
        request,
        presentations=presentations,
        presentation=presentation,
        template_name="people/partials/person_health.html",
        context={
            "active_person_tab": "health",
            "health_records": health_records,
            "can_add_health_record": _current_actor_can_write_health(
                request,
                permission="health.add_healthrecord",
            ),
            "can_manage_health_archive": _current_actor_can_write_health(
                request,
                permission="health.change_healthrecord",
            ),
            "can_manage_deleted_health_records": (
                _current_actor_can_write_health(
                    request,
                    permission="health.delete_healthrecord",
                )
            ),
            "health_record_archived": archived,
            "health_record_deleted": deleted,
        },
    )


@require_GET
def person_health_archive(
    request: HttpRequest,
    person_id: int,
) -> HttpResponse:
    """Zobraz bezpečný management seznam archivovaných health záznamů."""

    presentations, presentation = _visible_person_page(request, person_id)
    try:
        archived_records = list_archived_health_records(
            person=presentation.person,
            actor=request.user,
        )
    except Person.DoesNotExist as exc:
        raise Http404("Osoba nebyla nalezena.") from exc
    return _render_person_content(
        request,
        presentations=presentations,
        presentation=presentation,
        template_name="people/partials/person_health_archive.html",
        context={
            "active_person_tab": "health",
            "archived_health_records": archived_records,
        },
    )


@require_GET
def person_health_deleted(
    request: HttpRequest,
    person_id: int,
) -> HttpResponse:
    """Zobraz bezpečný management seznam odstraněných health záznamů."""

    presentations, presentation = _visible_person_page(request, person_id)
    try:
        deleted_records = list_soft_deleted_health_records(
            person=presentation.person,
            actor=request.user,
        )
    except Person.DoesNotExist as exc:
        raise Http404("Osoba nebyla nalezena.") from exc
    return _render_person_content(
        request,
        presentations=presentations,
        presentation=presentation,
        template_name="people/partials/person_health_deleted.html",
        context={
            "active_person_tab": "health",
            "deleted_health_records": deleted_records,
        },
    )


@require_GET
def person_health_record_detail(
    request: HttpRequest,
    person_id: int,
    health_record_id: int,
) -> HttpResponse:
    """Zobraz bezpečný read-only detail zdravotního záznamu."""

    presentations, presentation = _visible_person_page(request, person_id)
    health_record = _visible_health_record_or_404(
        request,
        person=presentation.person,
        health_record_id=health_record_id,
    )
    return _render_health_record_detail(
        request,
        presentations=presentations,
        presentation=presentation,
        health_record=health_record,
    )


def _visible_health_record_or_404(
    request: HttpRequest,
    *,
    person: Person,
    health_record_id: int,
) -> HealthRecord:
    try:
        health_record = get_health_record_detail(
            health_record_id=health_record_id,
            actor=request.user,
        )
    except ObjectDoesNotExist as exc:
        raise Http404("Zdravotní záznam nebyl nalezen.") from exc
    if health_record.person_id != person.pk:
        raise Http404("Zdravotní záznam nebyl nalezen.")
    return health_record


def _render_health_record_detail(
    request: HttpRequest,
    *,
    presentations: tuple[PersonPresentation, ...],
    presentation: PersonPresentation,
    health_record: HealthRecord,
    saved: bool = False,
) -> HttpResponse:
    return _render_person_content(
        request,
        presentations=presentations,
        presentation=presentation,
        template_name="people/partials/person_health_record.html",
        context={
            "active_person_tab": "health",
            "selected_health_record": health_record,
            "health_attachment_links": list_health_record_attachments(
                health_record=health_record,
                actor=request.user,
            ),
            "health_source_links": list_health_record_sources(
                health_record=health_record,
                actor=request.user,
            ),
            "can_change_health_record": _current_actor_can_write_health(
                request,
                permission="health.change_healthrecord",
                access_level=health_record.access_level,
            ),
            "can_soft_delete_health_record": (
                _current_actor_can_write_health(
                    request,
                    permission="health.delete_healthrecord",
                    access_level=health_record.access_level,
                )
            ),
            "health_record_saved": saved,
        },
    )


def _archived_health_record_or_404(
    request: HttpRequest,
    *,
    person: Person,
    health_record_id: int,
) -> HealthRecord:
    try:
        return get_archived_health_record_for_management(
            health_record_id=health_record_id,
            person=person,
            actor=request.user,
        )
    except (Person.DoesNotExist, HealthRecord.DoesNotExist) as exc:
        raise Http404("Zdravotní záznam nebyl nalezen.") from exc


def _soft_deleted_health_record_or_404(
    request: HttpRequest,
    *,
    person: Person,
    health_record_id: int,
) -> HealthRecord:
    try:
        return get_soft_deleted_health_record_for_management(
            health_record_id=health_record_id,
            person=person,
            actor=request.user,
        )
    except (Person.DoesNotExist, HealthRecord.DoesNotExist) as exc:
        raise Http404("Zdravotní záznam nebyl nalezen.") from exc


def _render_health_lifecycle_confirmation(
    request: HttpRequest,
    *,
    presentations: tuple[PersonPresentation, ...],
    presentation: PersonPresentation,
    health_record: HealthRecord,
    form: (
        HealthRecordArchiveForm
        | HealthRecordRestoreForm
        | HealthRecordSoftDeleteForm
        | HealthRecordRestoreSoftDeletedForm
    ),
    mode: str,
) -> HttpResponse:
    _prepare_accessible_form_errors(form)
    templates = {
        "archive": "people/partials/health_record_archive_confirm.html",
        "restore": "people/partials/health_record_restore_confirm.html",
        "soft_delete": (
            "people/partials/health_record_soft_delete_confirm.html"
        ),
        "restore_soft_deleted": (
            "people/partials/health_record_restore_soft_deleted_confirm.html"
        ),
    }
    return _render_person_content(
        request,
        presentations=presentations,
        presentation=presentation,
        template_name=templates[mode],
        context={
            "active_person_tab": "health",
            "selected_health_record": health_record,
            "health_lifecycle_form": form,
        },
    )


@require_http_methods(["GET", "POST"])
def person_health_record_archive(
    request: HttpRequest,
    person_id: int,
    health_record_id: int,
) -> HttpResponse:
    """Potvrď a proveď archivaci aktivního zdravotního záznamu."""

    presentations, presentation = _visible_person_page(request, person_id)
    health_record = _visible_health_record_or_404(
        request,
        person=presentation.person,
        health_record_id=health_record_id,
    )
    if not _current_actor_can_write_health(
        request,
        permission="health.change_healthrecord",
        access_level=health_record.access_level,
    ):
        raise PermissionDenied(
            "K archivaci zdravotního záznamu nemáte oprávnění."
        )
    form = HealthRecordArchiveForm(
        request.POST if request.method == "POST" else None
    )
    if request.method == "POST" and form.is_valid():
        try:
            archive_health_record(
                health_record=health_record,
                person=presentation.person,
                actor=request.user,
                reason=form.cleaned_data["reason"],
            )
        except (Person.DoesNotExist, HealthRecord.DoesNotExist) as exc:
            raise Http404("Zdravotní záznam nebyl nalezen.") from exc
        except ValidationError as error:
            _add_service_errors(form, error)
        else:
            if request.headers.get("HX-Request") == "true":
                response = _render_health_list(
                    request,
                    presentations=presentations,
                    presentation=presentation,
                    health_records=list_health_records(
                        person=presentation.person,
                        actor=request.user,
                    ),
                    archived=True,
                )
                response["HX-Push-Url"] = reverse(
                    "people:health",
                    args=(presentation.person.pk,),
                )
                return response
            messages.success(request, "Zdravotní záznam byl archivován.")
            return redirect("people:health", person_id=presentation.person.pk)
    return _render_health_lifecycle_confirmation(
        request,
        presentations=presentations,
        presentation=presentation,
        health_record=health_record,
        form=form,
        mode="archive",
    )


@require_http_methods(["GET", "POST"])
def person_health_record_restore(
    request: HttpRequest,
    person_id: int,
    health_record_id: int,
) -> HttpResponse:
    """Potvrď a proveď obnovení archivovaného zdravotního záznamu."""

    presentations, presentation = _visible_person_page(request, person_id)
    health_record = _archived_health_record_or_404(
        request,
        person=presentation.person,
        health_record_id=health_record_id,
    )
    form = HealthRecordRestoreForm(
        request.POST if request.method == "POST" else None
    )
    if request.method == "POST" and form.is_valid():
        try:
            restored_record = restore_archived_health_record(
                health_record=health_record,
                person=presentation.person,
                actor=request.user,
            )
        except (Person.DoesNotExist, HealthRecord.DoesNotExist) as exc:
            raise Http404("Zdravotní záznam nebyl nalezen.") from exc
        except ValidationError as error:
            _add_service_errors(form, error)
        else:
            if request.headers.get("HX-Request") == "true":
                response = _render_health_record_detail(
                    request,
                    presentations=presentations,
                    presentation=presentation,
                    health_record=restored_record,
                )
                response["HX-Push-Url"] = reverse(
                    "people:health-record-detail",
                    args=(presentation.person.pk, restored_record.pk),
                )
                return response
            messages.success(request, "Zdravotní záznam byl obnoven.")
            return redirect(
                "people:health-record-detail",
                person_id=presentation.person.pk,
                health_record_id=restored_record.pk,
            )
    return _render_health_lifecycle_confirmation(
        request,
        presentations=presentations,
        presentation=presentation,
        health_record=health_record,
        form=form,
        mode="restore",
    )


@require_http_methods(["GET", "POST"])
def person_health_record_soft_delete(
    request: HttpRequest,
    person_id: int,
    health_record_id: int,
) -> HttpResponse:
    """Potvrď a proveď měkké odstranění aktivního health záznamu."""

    presentations, presentation = _visible_person_page(request, person_id)
    health_record = _visible_health_record_or_404(
        request,
        person=presentation.person,
        health_record_id=health_record_id,
    )
    if not _current_actor_can_write_health(
        request,
        permission="health.delete_healthrecord",
        access_level=health_record.access_level,
    ):
        raise PermissionDenied(
            "K odstranění zdravotního záznamu nemáte oprávnění."
        )
    form = HealthRecordSoftDeleteForm(
        request.POST if request.method == "POST" else None
    )
    if request.method == "POST" and form.is_valid():
        try:
            soft_delete_health_record(
                health_record=health_record,
                person=presentation.person,
                actor=request.user,
                reason=form.cleaned_data["deletion_reason"],
            )
        except (Person.DoesNotExist, HealthRecord.DoesNotExist) as exc:
            raise Http404("Zdravotní záznam nebyl nalezen.") from exc
        except ValidationError as error:
            _add_service_errors(form, error)
        else:
            if request.headers.get("HX-Request") == "true":
                response = _render_health_list(
                    request,
                    presentations=presentations,
                    presentation=presentation,
                    health_records=list_health_records(
                        person=presentation.person,
                        actor=request.user,
                    ),
                    deleted=True,
                )
                response["HX-Push-Url"] = reverse(
                    "people:health",
                    args=(presentation.person.pk,),
                )
                return response
            messages.success(
                request,
                "Zdravotní záznam byl přesunut do koše.",
            )
            return redirect("people:health", person_id=presentation.person.pk)
    return _render_health_lifecycle_confirmation(
        request,
        presentations=presentations,
        presentation=presentation,
        health_record=health_record,
        form=form,
        mode="soft_delete",
    )


@require_http_methods(["GET", "POST"])
def person_health_record_restore_soft_deleted(
    request: HttpRequest,
    person_id: int,
    health_record_id: int,
) -> HttpResponse:
    """Potvrď a proveď obnovení odstraněného health záznamu."""

    presentations, presentation = _visible_person_page(request, person_id)
    health_record = _soft_deleted_health_record_or_404(
        request,
        person=presentation.person,
        health_record_id=health_record_id,
    )
    form = HealthRecordRestoreSoftDeletedForm(
        request.POST if request.method == "POST" else None
    )
    if request.method == "POST" and form.is_valid():
        try:
            restored_record = restore_soft_deleted_health_record(
                health_record=health_record,
                person=presentation.person,
                actor=request.user,
            )
        except (Person.DoesNotExist, HealthRecord.DoesNotExist) as exc:
            raise Http404("Zdravotní záznam nebyl nalezen.") from exc
        except ValidationError as error:
            _add_service_errors(form, error)
        else:
            if request.headers.get("HX-Request") == "true":
                response = _render_health_record_detail(
                    request,
                    presentations=presentations,
                    presentation=presentation,
                    health_record=restored_record,
                )
                response["HX-Push-Url"] = reverse(
                    "people:health-record-detail",
                    args=(presentation.person.pk, restored_record.pk),
                )
                return response
            messages.success(request, "Zdravotní záznam byl obnoven.")
            return redirect(
                "people:health-record-detail",
                person_id=presentation.person.pk,
                health_record_id=restored_record.pk,
            )
    return _render_health_lifecycle_confirmation(
        request,
        presentations=presentations,
        presentation=presentation,
        health_record=health_record,
        form=form,
        mode="restore_soft_deleted",
    )


def _current_actor_can_write_health(
    request: HttpRequest,
    *,
    permission: str,
    access_level: str | None = None,
) -> bool:
    actor = request.user
    if not actor.is_authenticated or actor.pk is None:
        return False
    user_model = get_user_model()
    try:
        current_actor = user_model._default_manager.get(pk=actor.pk)
    except user_model.DoesNotExist:
        return False
    if not current_actor.is_active or not current_actor.has_perm(permission):
        return False
    permitted_levels = (
        (access_level,)
        if access_level is not None
        else (AccessLevel.RESTRICTED, AccessLevel.ADMIN_ONLY)
    )
    return any(
        can_view_health_record_access(
            actor=current_actor,
            access_level=permitted_level,
        )
        for permitted_level in permitted_levels
    )


def _health_input_from_form(
    *,
    form: HealthRecordForm,
    person: Person,
    place: Place | None,
) -> HealthRecordInput:
    values = form.cleaned_data
    return HealthRecordInput(
        person=person,
        record_type=values["record_type"],
        place=place,
        title=values["title"],
        description=values["description"],
        provider_name=values["provider_name"],
        note=values["note"],
        access_level=values["access_level"],
        verification_status=values["verification_status"],
        date_precision=values["date_precision"],
        date_qualifier=values["date_qualifier"],
        start_year=values["start_year"],
        start_month=values["start_month"],
        start_day=values["start_day"],
        end_year=values["end_year"],
        end_month=values["end_month"],
        end_day=values["end_day"],
        original_date_text=values["original_date_text"],
        date_note=values["date_note"],
    )


def _render_health_form(
    request: HttpRequest,
    *,
    presentations: tuple[PersonPresentation, ...],
    presentation: PersonPresentation,
    form: HealthRecordForm,
    mode: str,
    health_record: HealthRecord | None = None,
) -> HttpResponse:
    _prepare_accessible_form_errors(form)
    return _render_person_content(
        request,
        presentations=presentations,
        presentation=presentation,
        template_name="people/partials/health_record_form.html",
        context={
            "active_person_tab": "health",
            "health_record_form": form,
            "health_form_mode": mode,
            "selected_health_record": health_record,
            "form_submitted": request.method == "POST",
        },
    )


@require_http_methods(["GET", "POST"])
def person_health_record_create(
    request: HttpRequest,
    person_id: int,
) -> HttpResponse:
    presentations, presentation = _visible_person_page(request, person_id)
    if not _current_actor_can_write_health(
        request,
        permission="health.add_healthrecord",
    ):
        raise PermissionDenied("K vytvoření zdravotního záznamu nemáte oprávnění.")
    candidate = HealthRecord(person=presentation.person)
    form = HealthRecordForm(
        request.POST or None,
        instance=candidate,
        actor=request.user,
    )
    if request.method == "POST" and form.is_valid():
        try:
            health_record = create_health_record(
                data=_health_input_from_form(
                    form=form,
                    person=presentation.person,
                    place=None,
                ),
                actor=request.user,
            )
        except Person.DoesNotExist as exc:
            raise Http404("Osoba nebyla nalezena.") from exc
        except ValidationError as error:
            _add_service_errors(form, error)
        else:
            if request.headers.get("HX-Request") == "true":
                response = _render_health_record_detail(
                    request,
                    presentations=presentations,
                    presentation=presentation,
                    health_record=health_record,
                    saved=True,
                )
                response["HX-Push-Url"] = reverse(
                    "people:health-record-detail",
                    args=(presentation.person.pk, health_record.pk),
                )
                return response
            messages.success(request, "Zdravotní záznam byl uložen.")
            return redirect(
                "people:health-record-detail",
                person_id=presentation.person.pk,
                health_record_id=health_record.pk,
            )
    return _render_health_form(
        request,
        presentations=presentations,
        presentation=presentation,
        form=form,
        mode="create",
    )


@require_http_methods(["GET", "POST"])
def person_health_record_edit(
    request: HttpRequest,
    person_id: int,
    health_record_id: int,
) -> HttpResponse:
    presentations, presentation = _visible_person_page(request, person_id)
    health_record = _visible_health_record_or_404(
        request,
        person=presentation.person,
        health_record_id=health_record_id,
    )
    if not _current_actor_can_write_health(
        request,
        permission="health.change_healthrecord",
    ):
        raise PermissionDenied("K úpravě zdravotního záznamu nemáte oprávnění.")
    preserved_place = health_record.place
    form = HealthRecordForm(
        request.POST or None,
        instance=health_record,
        actor=request.user,
    )
    if request.method == "POST" and form.is_valid():
        try:
            updated_record = update_health_record(
                health_record=health_record,
                data=_health_input_from_form(
                    form=form,
                    person=presentation.person,
                    place=preserved_place,
                ),
                actor=request.user,
            )
        except (Person.DoesNotExist, HealthRecord.DoesNotExist) as exc:
            raise Http404("Zdravotní záznam nebyl nalezen.") from exc
        except ValidationError as error:
            _add_service_errors(form, error)
        else:
            if request.headers.get("HX-Request") == "true":
                response = _render_health_record_detail(
                    request,
                    presentations=presentations,
                    presentation=presentation,
                    health_record=updated_record,
                    saved=True,
                )
                response["HX-Push-Url"] = reverse(
                    "people:health-record-detail",
                    args=(presentation.person.pk, updated_record.pk),
                )
                return response
            messages.success(request, "Zdravotní záznam byl uložen.")
            return redirect(
                "people:health-record-detail",
                person_id=presentation.person.pk,
                health_record_id=updated_record.pk,
            )
    return _render_health_form(
        request,
        presentations=presentations,
        presentation=presentation,
        form=form,
        mode="edit",
        health_record=health_record,
    )


def _current_actor_can_change_person(request: HttpRequest) -> bool:
    actor = request.user
    if not actor.is_authenticated or actor.pk is None:
        return False
    user_model = get_user_model()
    try:
        current_actor = user_model._default_manager.get(pk=actor.pk)
    except user_model.DoesNotExist:
        return False
    return current_actor.is_active and current_actor.has_perm(
        "people.change_person"
    )


def _visible_person_or_404(request: HttpRequest, person_id: int) -> Person:
    try:
        return get_visible_person(person_id=person_id, actor=request.user)
    except Person.DoesNotExist as exc:
        raise Http404("Osoba nebyla nalezena.") from exc


def _person_input_from_form(
    *,
    form: PersonForm,
) -> BasicPersonInput:
    return BasicPersonInput(
        category=form.cleaned_data["category"],
        gender=form.cleaned_data["gender"],
        first_name=form.cleaned_data["first_name"],
        last_name=form.cleaned_data["last_name"],
        notes=form.cleaned_data["notes"],
    )


def _add_service_errors(form: PersonForm, error: ValidationError) -> None:
    if hasattr(error, "error_dict"):
        for field_name, field_errors in error.error_dict.items():
            target = field_name if field_name in form.fields else None
            for field_error in field_errors:
                form.add_error(target, field_error)
        return
    form.add_error(None, error)


def _prepare_accessible_form_errors(form: PersonForm) -> None:
    for field_name in form.errors:
        if field_name not in form.fields:
            continue
        field = form.fields[field_name]
        field.widget.attrs["aria-invalid"] = "true"
        field.widget.attrs["aria-describedby"] = f"id_{field_name}-errors"


@require_http_methods(["GET", "POST"])
def person_edit(request: HttpRequest, person_id: int) -> HttpResponse:
    """Uprav základní údaje viditelné osoby přes doménovou službu."""

    person = _visible_person_or_404(request, person_id)
    if not _current_actor_can_change_person(request):
        raise PermissionDenied("K úpravě osoby nemáte oprávnění.")

    form = PersonForm(request.POST or None, instance=person)
    if request.method == "POST" and form.is_valid():
        try:
            updated_person = update_person_basic(
                person=person,
                data=_person_input_from_form(form=form),
                actor=request.user,
            )
        except Person.DoesNotExist as error:
            raise Http404("Osoba nebyla nalezena.") from error
        except ValidationError as error:
            _add_service_errors(form, error)
        else:
            if request.headers.get("HX-Request") == "true":
                context = _shell_context(
                    request,
                    selected_person=updated_person,
                )
                response = render(
                    request,
                    "people/partials/person_update_success.html",
                    context,
                )
                response["HX-Push-Url"] = reverse(
                    "people:detail",
                    args=(updated_person.pk,),
                )
                return response
            messages.success(request, "Změny byly uloženy.")
            return redirect("people:detail", person_id=updated_person.pk)

    _prepare_accessible_form_errors(form)
    context = {
        "selected_person": person,
        "person_form": form,
        "form_submitted": request.method == "POST",
    }
    if request.headers.get("HX-Request") == "true":
        return render(request, "people/partials/person_form.html", context)
    return render(
        request,
        "people/person_shell.html",
        _shell_context(request, selected_person=person) | context,
    )


def not_found(
    request: HttpRequest,
    exception: Exception,
) -> HttpResponse:
    """Vrať jednotný použitelný stav pro neexistující i skrytý cíl."""

    template_name = (
        "people/partials/not_found.html"
        if request.headers.get("HX-Request") == "true"
        else "404.html"
    )
    return render(
        request,
        template_name,
        {"login_return_path": "/"},
        status=404,
    )

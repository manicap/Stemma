from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from .forms import PersonForm
from .models import Person
from .selectors import get_visible_people, get_visible_person
from .services import PersonInput, update_person


def _shell_context(
    request: HttpRequest,
    *,
    selected_person: Person | None = None,
) -> dict[str, object]:
    return {
        "people": get_visible_people(actor=request.user),
        "selected_person": selected_person,
    }


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

    try:
        person = get_visible_person(
            person_id=person_id,
            actor=request.user,
        )
    except Person.DoesNotExist as exc:
        raise Http404("Osoba nebyla nalezena.") from exc

    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "people/partials/person_detail.html",
            {"selected_person": person},
        )
    return render(
        request,
        "people/person_shell.html",
        _shell_context(request, selected_person=person),
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
    person: Person,
) -> PersonInput:
    return PersonInput(
        category=form.cleaned_data["category"],
        gender=form.cleaned_data["gender"],
        first_name=form.cleaned_data["first_name"],
        last_name=form.cleaned_data["last_name"],
        notes=form.cleaned_data["notes"],
        access_level=person.access_level,
        verification_status=person.verification_status,
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
            updated_person = update_person(
                person=person,
                data=_person_input_from_form(form=form, person=person),
                actor=request.user,
            )
        except Person.DoesNotExist as error:
            raise Http404("Osoba nebyla nalezena.") from error
        except ValidationError as error:
            _add_service_errors(form, error)
        else:
            if request.headers.get("HX-Request") == "true":
                response = render(
                    request,
                    "people/partials/person_update_success.html",
                    {"selected_person": updated_person},
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

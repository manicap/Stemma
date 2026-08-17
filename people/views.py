from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .models import Person
from .selectors import get_visible_people, get_visible_person


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
    return render(request, template_name, status=404)

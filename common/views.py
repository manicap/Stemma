from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from people.derived_selectors import get_visible_person_presentations


@require_GET
def overview(request: HttpRequest) -> HttpResponse:
    """Render the application entry point from actor-visible data."""

    presentations = get_visible_person_presentations(actor=request.user)
    return render(
        request,
        "common/overview.html",
        {
            "visible_person_count": len(presentations),
            "visible_person_presentations": presentations[:4],
        },
    )

"""HTTP transport for protected attachment delivery."""

from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.utils.cache import patch_vary_headers
from django.views.decorators.http import require_GET

from .delivery import AttachmentDeliveryUnavailable, get_attachment_delivery


def _deliver(
    request: HttpRequest,
    *,
    context_type: str,
    context_id: int,
    link_id: int,
    as_attachment: bool,
) -> HttpResponse:
    try:
        delivery = get_attachment_delivery(
            context_type=context_type,
            context_id=context_id,
            link_id=link_id,
            actor=request.user,
        )
    except AttachmentDeliveryUnavailable:
        raise Http404("Příloha nebyla nalezena.") from None

    response = FileResponse(
        delivery.content,
        as_attachment=as_attachment,
        filename=delivery.filename,
        content_type=delivery.content_type,
    )
    response["Cache-Control"] = "private, no-store"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    response["Referrer-Policy"] = "no-referrer"
    patch_vary_headers(response, ("Cookie",))
    return response


@require_GET
def open_attachment(
    request: HttpRequest,
    context_type: str,
    context_id: int,
    link_id: int,
) -> HttpResponse:
    """Open an authorized attachment inline when the browser supports it."""

    return _deliver(
        request,
        context_type=context_type,
        context_id=context_id,
        link_id=link_id,
        as_attachment=False,
    )


@require_GET
def download_attachment(
    request: HttpRequest,
    context_type: str,
    context_id: int,
    link_id: int,
) -> HttpResponse:
    """Download an authorized attachment using its safe original filename."""

    return _deliver(
        request,
        context_type=context_type,
        context_id=context_id,
        link_id=link_id,
        as_attachment=True,
    )

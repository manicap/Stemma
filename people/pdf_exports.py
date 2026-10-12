"""Actor-aware person export presentation and A4 PDF rendering."""

from dataclasses import dataclass
from html import escape
from importlib.resources import files
from io import BytesIO

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from common.choices import DatePrecision, DateQualifier
from events.selectors import get_visible_person_events
from places.selectors import (
    get_visible_person_grave_site_links,
    get_visible_person_residences,
)

from .derived_selectors import get_visible_person_presentations
from .models import Person
from .selectors import get_visible_relationship_overview

__all__ = (
    "PersonPdfExport",
    "build_person_pdf",
    "get_person_pdf_export",
)

_FONT_NAME = "StemmaVera"
_FONT_BOLD_NAME = "StemmaVeraBold"


@dataclass(frozen=True, slots=True)
class PdfListItem:
    """One already-authorized textual item rendered in an export section."""

    title: str
    lines: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PersonPdfExport:
    """Immutable actor-specific presentation for one person's PDF export."""

    display_name: str
    category: str | None
    gender: str
    life_status: str
    age_text: str | None
    birth_text: str | None
    death_text: str | None
    biography: str
    notes: str
    relationships: tuple[PdfListItem, ...]
    residences: tuple[PdfListItem, ...]
    grave_sites: tuple[PdfListItem, ...]
    events: tuple[PdfListItem, ...]


def _display_name(person: Person, roman_suffix: str | None = None) -> str:
    name = " ".join(
        part.strip()
        for part in (
            person.title_before_name,
            person.first_name,
            person.last_name,
            roman_suffix or "",
            person.title_after_name,
        )
        if part and part.strip()
    )
    return name or "Osoba"


def _related_person_name(person: Person) -> str:
    name = " ".join(
        part.strip()
        for part in (person.first_name, person.last_name)
        if part and part.strip()
    )
    return name or "Osoba"


def _format_date_parts(
    year: int | None,
    month: int | None,
    day: int | None,
) -> str | None:
    if year is None:
        return None
    if month is None:
        return str(year)
    if day is None:
        return f"{month}/{year}"
    return f"{day}. {month}. {year}"


def _format_partial_date(value: object, *, unknown: str) -> str:
    original = str(getattr(value, "original_date_text", "") or "").strip()
    if original:
        return original

    start = _format_date_parts(
        getattr(value, "start_year", None),
        getattr(value, "start_month", None),
        getattr(value, "start_day", None),
    )
    if start is None:
        return unknown

    prefix = {
        DateQualifier.NONE: "",
        DateQualifier.APPROXIMATE: "přibližně ",
        DateQualifier.BEFORE: "před ",
        DateQualifier.AFTER: "po ",
    }.get(getattr(value, "date_qualifier", None), "")
    if getattr(value, "date_precision", None) != DatePrecision.RANGE:
        return f"{prefix}{start}"

    end = _format_date_parts(
        getattr(value, "end_year", None),
        getattr(value, "end_month", None),
        getattr(value, "end_day", None),
    )
    return f"{prefix}{start}–{end}" if end else f"{prefix}{start}"


def _residence_item(residence: object) -> PdfListItem:
    place = getattr(residence, "place", None)
    address = str(getattr(residence, "address_text", "") or "").strip()
    place_name = str(getattr(place, "name", "") or "").strip()
    title = place_name or address or "Bydliště"
    lines = [str(residence.residence_type.name)]
    if place_name and address:
        lines.append(address)
    lines.append(_format_partial_date(residence, unknown="Období neuvedeno"))
    note = str(getattr(residence, "note", "") or "").strip()
    if note:
        lines.append(note)
    return PdfListItem(title=title, lines=tuple(lines))


def _grave_site_item(link: object) -> PdfListItem:
    site = link.grave_site
    place_name = str(getattr(site.place, "name", "") or "").strip()
    cemetery = str(site.cemetery_name or "").strip()
    location = str(site.location_text or "").strip()
    title = cemetery or location or place_name or "Hrobové nebo pamětní místo"
    lines = [str(site.grave_site_type.name), f"Role: {link.role.name}"]
    for value in (location if cemetery else "", place_name):
        if value and value != title and value not in lines:
            lines.append(value)
    identifiers = []
    for label, value in (
        ("Oddíl", site.section),
        ("Řada", site.row),
        ("Hrob", site.grave_number),
    ):
        if value:
            identifiers.append(f"{label} {value}")
    if identifiers:
        lines.append(" · ".join(identifiers))
    lines.append(f"Stav: {site.get_status_display()}")
    note = str(link.note or "").strip()
    if note:
        lines.append(note)
    return PdfListItem(title=title, lines=tuple(lines))


def _event_item(event: object) -> PdfListItem:
    title = str(event.title or event.event_type.name)
    lines = [
        str(event.event_type.name),
        _format_partial_date(event, unknown="Datum neuvedeno"),
    ]
    for value in (
        getattr(event, "presentation_place_name", None),
        event.location_detail,
        event.description,
    ):
        clean_value = str(value or "").strip()
        if clean_value:
            lines.append(clean_value)
    return PdfListItem(title=title, lines=tuple(lines))


def get_person_pdf_export(
    *,
    person_id: int,
    actor: AbstractBaseUser | AnonymousUser,
) -> PersonPdfExport:
    """Compose one safe PDF presentation from existing actor-aware reads."""

    presentation = next(
        (
            item
            for item in get_visible_person_presentations(actor=actor)
            if item.person.pk == person_id
        ),
        None,
    )
    if presentation is None:
        raise Person.DoesNotExist

    person = presentation.person
    facts = presentation.facts
    relationship_items = tuple(
        PdfListItem(
            title=_related_person_name(item.person),
            lines=tuple(reason.label for reason in item.reasons),
        )
        for item in get_visible_relationship_overview(
            person=person,
            actor=actor,
        )
    )
    residences = tuple(
        _residence_item(residence)
        for residence in get_visible_person_residences(
            person=person,
            actor=actor,
        )
    )
    grave_sites = tuple(
        _grave_site_item(link)
        for link in get_visible_person_grave_site_links(
            person=person,
            actor=actor,
        )
    )
    events = tuple(
        _event_item(event)
        for event in get_visible_person_events(person=person, actor=actor)
    )
    return PersonPdfExport(
        display_name=_display_name(person, facts.roman_suffix),
        category=person.category.name if person.category else None,
        gender=person.get_gender_display(),
        life_status="Zemřelá osoba" if facts.is_deceased else "Žijící osoba",
        age_text=facts.age_text,
        birth_text=facts.birth_text,
        death_text=facts.death_text,
        biography=(person.biography or "").strip(),
        notes=(person.notes or "").strip(),
        relationships=relationship_items,
        residences=residences,
        grave_sites=grave_sites,
        events=events,
    )


def _register_fonts() -> None:
    if _FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return
    font_dir = files("font_roboto").joinpath("files")
    pdfmetrics.registerFont(
        TTFont(_FONT_NAME, str(font_dir.joinpath("Roboto-Regular.ttf")))
    )
    pdfmetrics.registerFont(
        TTFont(_FONT_BOLD_NAME, str(font_dir.joinpath("Roboto-Bold.ttf")))
    )


def _paragraph(value: str, style: ParagraphStyle) -> Paragraph:
    safe_value = escape(value).replace("\n", "<br/>")
    return Paragraph(safe_value, style)


def _page_footer(canvas: object, document: object) -> None:
    canvas.saveState()
    canvas.setFont(_FONT_NAME, 8)
    canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawCentredString(
        A4[0] / 2,
        10 * mm,
        f"Stemma · strana {document.page}",
    )
    canvas.restoreState()


def build_person_pdf(export: PersonPdfExport) -> bytes:
    """Render an actor-specific presentation as a printable A4 PDF."""

    _register_fonts()
    buffer = BytesIO()
    document = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=export.display_name,
        author="Stemma",
    )
    frame = Frame(
        document.leftMargin,
        document.bottomMargin,
        document.width,
        document.height,
        id="body",
    )
    document.addPageTemplates(
        PageTemplate(id="a4", frames=(frame,), onPage=_page_footer)
    )

    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "StemmaBody",
        parent=styles["BodyText"],
        fontName=_FONT_NAME,
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#263548"),
        spaceAfter=3 * mm,
    )
    title = ParagraphStyle(
        "StemmaTitle",
        parent=body,
        fontName=_FONT_BOLD_NAME,
        fontSize=20,
        leading=25,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#17324D"),
        spaceAfter=3 * mm,
    )
    subtitle = ParagraphStyle(
        "StemmaSubtitle",
        parent=body,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#526277"),
        spaceAfter=7 * mm,
    )
    section = ParagraphStyle(
        "StemmaSection",
        parent=body,
        fontName=_FONT_BOLD_NAME,
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#17324D"),
        spaceBefore=5 * mm,
        spaceAfter=2 * mm,
        keepWithNext=True,
    )
    item_title = ParagraphStyle(
        "StemmaItemTitle",
        parent=body,
        fontName=_FONT_BOLD_NAME,
        spaceAfter=1 * mm,
        keepWithNext=True,
    )
    item_body = ParagraphStyle(
        "StemmaItemBody",
        parent=body,
        textColor=colors.HexColor("#465569"),
        leftIndent=3 * mm,
        spaceAfter=2 * mm,
    )

    story = [_paragraph(export.display_name, title)]
    subtitle_parts = [export.category, export.gender, export.life_status]
    if export.age_text:
        subtitle_parts.append(export.age_text)
    story.append(_paragraph(" · ".join(filter(None, subtitle_parts)), subtitle))

    facts = []
    if export.birth_text:
        facts.append(("Narození", export.birth_text))
    if export.death_text:
        facts.append(("Úmrtí", export.death_text))
    if facts:
        data = [
            [
                _paragraph(label, item_title),
                _paragraph(value, body),
            ]
            for label, value in facts
        ]
        fact_table = Table(data, colWidths=(35 * mm, 120 * mm), hAlign="LEFT")
        fact_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 1 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1 * mm),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D9E0E8")),
                ]
            )
        )
        story.extend((fact_table, Spacer(1, 3 * mm)))

    for heading, text in (
        ("Životopis", export.biography),
        ("Poznámky", export.notes),
    ):
        if text:
            story.extend((_paragraph(heading, section), _paragraph(text, body)))

    for heading, items in (
        ("Vztahy", export.relationships),
        ("Bydliště", export.residences),
        ("Hrobová místa", export.grave_sites),
        ("Události", export.events),
    ):
        if not items:
            continue
        story.append(_paragraph(heading, section))
        for item in items:
            item_flowables = [_paragraph(item.title, item_title)]
            item_flowables.extend(
                _paragraph(line, item_body) for line in item.lines
            )
            story.append(KeepTogether(item_flowables))

    story.extend(
        (
            Spacer(1, 5 * mm),
            _paragraph(
                f"Vytvořeno {timezone.localdate().strftime('%d. %m. %Y')}",
                ParagraphStyle(
                    "StemmaGenerated",
                    parent=body,
                    fontSize=8,
                    textColor=colors.HexColor("#667085"),
                ),
            ),
        )
    )
    document.build(story)
    return buffer.getvalue()

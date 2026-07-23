from django.db import migrations


INITIAL_GRAVE_SITE_TYPES = (
    {
        "code": "grave",
        "name": "Hrob",
        "description": (
            "Hrobové místo určené k uložení tělesných ostatků; může být "
            "individuální i společné."
        ),
        "sort_order": 10,
    },
    {
        "code": "tomb",
        "name": "Hrobka",
        "description": (
            "Stavebně vymezené hrobové místo nebo podzemní či nadzemní "
            "hrobka."
        ),
        "sort_order": 20,
    },
    {
        "code": "urn_site",
        "name": "Urnové místo",
        "description": (
            "Místo určené k uložení urny, včetně urnového hrobu nebo "
            "jednotlivé kolumbární schránky."
        ),
        "sort_order": 30,
    },
    {
        "code": "ossuary",
        "name": "Kostnice",
        "description": "Místo společného uložení kosterních ostatků.",
        "sort_order": 40,
    },
    {
        "code": "scattering_place",
        "name": "Místo rozptylu",
        "description": (
            "Vymezené místo, na kterém byl proveden rozptyl popela."
        ),
        "sort_order": 50,
    },
    {
        "code": "memorial",
        "name": "Pamětní místo",
        "description": (
            "Památník, deska nebo jiné místo připomínky bez tvrzení o "
            "uložení ostatků."
        ),
        "sort_order": 60,
    },
    {
        "code": "cenotaph",
        "name": "Symbolický hrob",
        "description": (
            "Hrob nebo památník připomínající osobu, jejíž ostatky zde "
            "nejsou uloženy."
        ),
        "sort_order": 70,
    },
    {
        "code": "other",
        "name": "Jiné místo",
        "description": (
            "Jiný druh hrobového, pohřebního nebo pamětního místa."
        ),
        "sort_order": 90,
    },
)

INITIAL_PERSON_GRAVE_SITE_ROLES = (
    {
        "code": "buried",
        "name": "Pohřbena",
        "description": "Na místě byly uloženy tělesné ostatky osoby.",
        "sort_order": 10,
    },
    {
        "code": "urn_placed",
        "name": "Uložena urna",
        "description": "Na místě byla uložena urna s popelem osoby.",
        "sort_order": 20,
    },
    {
        "code": "ashes_scattered",
        "name": "Rozptýlena",
        "description": "Na místě byl rozptýlen popel osoby.",
        "sort_order": 30,
    },
    {
        "code": "commemorated",
        "name": "Připomenuta",
        "description": (
            "Osoba je na místě připomenuta nápisem, památníkem nebo "
            "symbolicky, bez tvrzení o uložení ostatků."
        ),
        "sort_order": 40,
    },
    {
        "code": "remains_relocated_from",
        "name": "Ostatky přemístěny z místa",
        "description": (
            "Místo je doloženým výchozím místem přemístění ostatků."
        ),
        "sort_order": 50,
    },
    {
        "code": "remains_relocated_to",
        "name": "Ostatky přemístěny na místo",
        "description": (
            "Místo je doloženým cílem přemístění ostatků."
        ),
        "sort_order": 60,
    },
    {
        "code": "other",
        "name": "Jiné propojení",
        "description": "Jiný význam propojení osoby s místem.",
        "sort_order": 90,
    },
)

INITIAL_GRAVE_SITE_TYPE_CODES = tuple(
    grave_site_type["code"]
    for grave_site_type in INITIAL_GRAVE_SITE_TYPES
)
INITIAL_PERSON_GRAVE_SITE_ROLE_CODES = tuple(
    role["code"] for role in INITIAL_PERSON_GRAVE_SITE_ROLES
)


def create_initial_grave_site_lookups(apps, schema_editor) -> None:
    grave_site_type_model = apps.get_model("places", "GraveSiteType")
    person_role_model = apps.get_model(
        "places",
        "PersonGraveSiteRole",
    )

    collisions = []
    for catalog_name, model, codes in (
        (
            "GraveSiteType",
            grave_site_type_model,
            INITIAL_GRAVE_SITE_TYPE_CODES,
        ),
        (
            "PersonGraveSiteRole",
            person_role_model,
            INITIAL_PERSON_GRAVE_SITE_ROLE_CODES,
        ),
    ):
        conflicting_codes = tuple(
            model.objects.filter(
                code__in=codes,
                is_system=False,
            )
            .order_by("code")
            .values_list("code", flat=True)
        )
        if conflicting_codes:
            collisions.append(
                f"{catalog_name}: {', '.join(conflicting_codes)}"
            )

    if collisions:
        raise RuntimeError(
            "Systémové kódy katalogů hrobových míst kolidují s "
            f"uživatelskými záznamy: {'; '.join(collisions)}."
        )

    for grave_site_type in INITIAL_GRAVE_SITE_TYPES:
        grave_site_type_model.objects.update_or_create(
            code=grave_site_type["code"],
            defaults={
                "name": grave_site_type["name"],
                "description": grave_site_type["description"],
                "sort_order": grave_site_type["sort_order"],
                "is_active": True,
                "is_system": True,
            },
        )

    for role in INITIAL_PERSON_GRAVE_SITE_ROLES:
        person_role_model.objects.update_or_create(
            code=role["code"],
            defaults={
                "name": role["name"],
                "description": role["description"],
                "sort_order": role["sort_order"],
                "is_active": True,
                "is_system": True,
            },
        )


def remove_initial_grave_site_lookups(apps, schema_editor) -> None:
    grave_site_type_model = apps.get_model("places", "GraveSiteType")
    person_role_model = apps.get_model(
        "places",
        "PersonGraveSiteRole",
    )
    grave_site_type_model.objects.filter(
        code__in=INITIAL_GRAVE_SITE_TYPE_CODES,
        is_system=True,
    ).delete()
    person_role_model.objects.filter(
        code__in=INITIAL_PERSON_GRAVE_SITE_ROLE_CODES,
        is_system=True,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("places", "0006_grave_site_lookups"),
    ]

    operations = [
        migrations.RunPython(
            create_initial_grave_site_lookups,
            remove_initial_grave_site_lookups,
        ),
    ]

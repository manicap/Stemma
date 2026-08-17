from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse

from events.models import AllowedEventRole, EventType, ParticipantRole
from people.models import NameType, PersonCategory, RelationshipType
from places.models import (
    GraveSiteType,
    PersonGraveSiteRole,
    PlaceType,
    ResidenceType,
)

from .admin import SystemValueAdminMixin


class SystemValueAdminTests(TestCase):
    guarded_models = (
        PersonCategory,
        NameType,
        RelationshipType,
        EventType,
        ParticipantRole,
        AllowedEventRole,
        PlaceType,
        ResidenceType,
        GraveSiteType,
        PersonGraveSiteRole,
    )

    def setUp(self) -> None:
        self.superuser = get_user_model().objects.create_superuser(
            username="lookup-admin",
            password="test-password",
        )
        self.client.force_login(self.superuser)

    def event_type_data(
        self,
        event_type: EventType,
        *,
        code: str,
        name: str,
    ) -> dict[str, object]:
        data: dict[str, object] = {
            "code": code,
            "name": name,
            "description": event_type.description,
            "sort_order": event_type.sort_order,
            "default_access_level": event_type.default_access_level,
            "_save": "Uložit",
        }
        if event_type.is_active:
            data["is_active"] = "on"
        if event_type.supports_date_range:
            data["supports_date_range"] = "on"
        if event_type.allows_place:
            data["allows_place"] = "on"
        if event_type.default_show_in_overview:
            data["default_show_in_overview"] = "on"
        return data

    def test_all_runtime_lookup_admins_use_system_value_guard(self) -> None:
        for model in self.guarded_models:
            with self.subTest(model=model._meta.label):
                self.assertIsInstance(
                    admin.site._registry[model],
                    SystemValueAdminMixin,
                )

    def test_system_relationship_semantics_are_readonly(self) -> None:
        model_admin = admin.site._registry[RelationshipType]
        request = RequestFactory().get("/")
        request.user = self.superuser
        system_type = RelationshipType.objects.get(
            code="biological_parent"
        )
        custom_type = RelationshipType.objects.create(
            code="custom_relation",
            name="Vlastní vazba",
            forward_label_male="cíl",
            forward_label_female="cíl",
            forward_label_unknown="cíl",
            reverse_label_male="zdroj",
            reverse_label_female="zdroj",
            reverse_label_unknown="zdroj",
        )
        semantic_fields = {
            "code",
            "category",
            "is_symmetric",
            "supports_date_range",
            "is_derivable",
        }

        self.assertTrue(
            semantic_fields
            <= set(model_admin.get_readonly_fields(request, system_type))
        )
        self.assertTrue(
            semantic_fields.isdisjoint(
                model_admin.get_readonly_fields(request, custom_type)
            )
        )

    def test_system_code_is_immutable_but_other_fields_remain_editable(
        self,
    ) -> None:
        event_type = EventType.objects.get(code="birth")
        response = self.client.post(
            reverse("admin:events_eventtype_change", args=(event_type.pk,)),
            self.event_type_data(
                event_type,
                code="renamed_birth",
                name="Upravené narození",
            ),
        )

        self.assertRedirects(
            response,
            reverse("admin:events_eventtype_changelist"),
        )
        event_type.refresh_from_db()
        self.assertEqual(event_type.code, "birth")
        self.assertEqual(event_type.name, "Upravené narození")
        self.assertTrue(event_type.is_system)

    def test_save_hook_restores_tampered_system_identity(self) -> None:
        model_admin = admin.site._registry[EventType]
        request = RequestFactory().post("/")
        request.user = self.superuser
        event_type = EventType.objects.get(code="birth")
        event_type.code = "tampered_birth"
        event_type.is_system = False

        model_admin.save_model(request, event_type, form=None, change=True)

        event_type.refresh_from_db()
        self.assertEqual(event_type.code, "birth")
        self.assertTrue(event_type.is_system)

    def test_custom_code_remains_editable_and_custom_row_deletable(self) -> None:
        event_type = EventType.objects.create(
            code="custom_event",
            name="Vlastní událost",
        )
        custom_data = self.event_type_data(
            event_type,
            code="renamed_custom_event",
            name="Přejmenovaná vlastní událost",
        )
        custom_data["is_system"] = "on"
        change_response = self.client.post(
            reverse("admin:events_eventtype_change", args=(event_type.pk,)),
            custom_data,
        )

        self.assertRedirects(
            change_response,
            reverse("admin:events_eventtype_changelist"),
        )
        event_type.refresh_from_db()
        self.assertEqual(event_type.code, "renamed_custom_event")
        self.assertFalse(event_type.is_system)

        delete_response = self.client.post(
            reverse("admin:events_eventtype_delete", args=(event_type.pk,)),
            {"post": "yes"},
        )
        self.assertRedirects(
            delete_response,
            reverse("admin:events_eventtype_changelist"),
        )
        self.assertFalse(EventType.objects.filter(pk=event_type.pk).exists())

    def test_system_row_cannot_be_deleted_directly_or_in_bulk(self) -> None:
        event_type = EventType.objects.get(code="other")
        custom_type = EventType.objects.create(
            code="bulk_custom_event",
            name="Hromadně vybraná vlastní událost",
        )

        direct_response = self.client.post(
            reverse("admin:events_eventtype_delete", args=(event_type.pk,)),
            {"post": "yes"},
        )
        bulk_response = self.client.post(
            reverse("admin:events_eventtype_changelist"),
            {
                "action": "delete_selected",
                "_selected_action": (event_type.pk, custom_type.pk),
                "post": "yes",
            },
        )

        self.assertEqual(direct_response.status_code, 403)
        self.assertEqual(bulk_response.status_code, 200)
        self.assertTrue(bulk_response.context["perms_lacking"])
        self.assertTrue(EventType.objects.filter(pk=event_type.pk).exists())
        self.assertTrue(EventType.objects.filter(pk=custom_type.pk).exists())

    def test_delete_queryset_hook_rejects_mixed_system_selection(self) -> None:
        model_admin = admin.site._registry[EventType]
        request = RequestFactory().post("/")
        request.user = self.superuser
        system_type = EventType.objects.get(code="other")
        custom_type = EventType.objects.create(
            code="hook_custom_event",
            name="Vlastní událost pro hook",
        )
        queryset = EventType.objects.filter(
            pk__in=(system_type.pk, custom_type.pk)
        )

        with self.assertRaises(PermissionDenied):
            model_admin.delete_queryset(request, queryset)

        self.assertTrue(EventType.objects.filter(pk=system_type.pk).exists())
        self.assertTrue(EventType.objects.filter(pk=custom_type.pk).exists())

    def test_system_allowed_role_identity_is_immutable(self) -> None:
        rule = AllowedEventRole.objects.select_related(
            "event_type", "participant_role"
        ).get(
            event_type__code="birth",
            participant_role__code="born_person",
        )
        replacement_type = EventType.objects.get(code="death")
        replacement_role = ParticipantRole.objects.get(code="witness")

        response = self.client.post(
            reverse(
                "admin:events_allowedeventrole_change",
                args=(rule.pk,),
            ),
            {
                "event_type": replacement_type.pk,
                "participant_role": replacement_role.pk,
                "min_count": 1,
                "max_count": 1,
                "sort_order": 11,
                "is_active": "on",
                "_save": "Uložit",
            },
        )

        self.assertRedirects(
            response,
            reverse("admin:events_allowedeventrole_changelist"),
        )
        rule.refresh_from_db()
        self.assertEqual(rule.event_type.code, "birth")
        self.assertEqual(rule.participant_role.code, "born_person")
        self.assertEqual(rule.sort_order, 11)

    def test_custom_allowed_role_identity_and_deletion_remain_available(
        self,
    ) -> None:
        first_type = EventType.objects.create(
            code="custom_first",
            name="První vlastní typ",
        )
        second_type = EventType.objects.create(
            code="custom_second",
            name="Druhý vlastní typ",
        )
        first_role = ParticipantRole.objects.create(
            code="custom_first_role",
            name="První vlastní role",
        )
        second_role = ParticipantRole.objects.create(
            code="custom_second_role",
            name="Druhá vlastní role",
        )
        rule = AllowedEventRole.objects.create(
            event_type=first_type,
            participant_role=first_role,
        )

        change_response = self.client.post(
            reverse(
                "admin:events_allowedeventrole_change",
                args=(rule.pk,),
            ),
            {
                "event_type": second_type.pk,
                "participant_role": second_role.pk,
                "min_count": 0,
                "max_count": "",
                "sort_order": 5,
                "is_active": "on",
                "is_system": "on",
                "_save": "Uložit",
            },
        )

        self.assertRedirects(
            change_response,
            reverse("admin:events_allowedeventrole_changelist"),
        )
        rule.refresh_from_db()
        self.assertEqual(rule.event_type, second_type)
        self.assertEqual(rule.participant_role, second_role)
        self.assertFalse(rule.is_system)

        delete_response = self.client.post(
            reverse(
                "admin:events_allowedeventrole_delete",
                args=(rule.pk,),
            ),
            {"post": "yes"},
        )
        self.assertRedirects(
            delete_response,
            reverse("admin:events_allowedeventrole_changelist"),
        )
        self.assertFalse(
            AllowedEventRole.objects.filter(pk=rule.pk).exists()
        )

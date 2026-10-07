from django.urls import path

from . import views

app_name = "people"

urlpatterns = [
    path("", views.person_index, name="index"),
    path("<int:person_id>/", views.person_detail, name="detail"),
    path(
        "<int:person_id>/vztahy/",
        views.person_relationships,
        name="relationships",
    ),
    path(
        "<int:person_id>/zdravi/",
        views.person_health,
        name="health",
    ),
    path(
        "<int:person_id>/zdravi/archiv/",
        views.person_health_archive,
        name="health-archive",
    ),
    path(
        "<int:person_id>/zdravi/kos/",
        views.person_health_deleted,
        name="health-deleted",
    ),
    path(
        "<int:person_id>/zdravi/<int:health_record_id>/",
        views.person_health_record_detail,
        name="health-record-detail",
    ),
    path(
        "<int:person_id>/zdravi/novy/",
        views.person_health_record_create,
        name="health-record-create",
    ),
    path(
        "<int:person_id>/zdravi/<int:health_record_id>/upravit/",
        views.person_health_record_edit,
        name="health-record-edit",
    ),
    path(
        "<int:person_id>/zdravi/<int:health_record_id>/archivovat/",
        views.person_health_record_archive,
        name="health-record-archive",
    ),
    path(
        "<int:person_id>/zdravi/<int:health_record_id>/obnovit/",
        views.person_health_record_restore,
        name="health-record-restore",
    ),
    path(
        "<int:person_id>/zdravi/<int:health_record_id>/odstranit/",
        views.person_health_record_soft_delete,
        name="health-record-soft-delete",
    ),
    path(
        "<int:person_id>/zdravi/<int:health_record_id>/obnovit-odstraneny/",
        views.person_health_record_restore_soft_deleted,
        name="health-record-restore-soft-deleted",
    ),
    path(
        "<int:person_id>/upravit/",
        views.person_edit,
        name="edit",
    ),
]

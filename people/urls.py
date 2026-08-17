from django.urls import path

from . import views

app_name = "people"

urlpatterns = [
    path("", views.person_index, name="index"),
    path("<int:person_id>/", views.person_detail, name="detail"),
    path(
        "<int:person_id>/upravit/",
        views.person_edit,
        name="edit",
    ),
]

from django.urls import path

from . import views

app_name = "people"

urlpatterns = [
    path("", views.person_index, name="index"),
    path("osoby/<int:person_id>/", views.person_detail, name="detail"),
]

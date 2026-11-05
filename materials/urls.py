from django.urls import path

from . import views

app_name = "materials"

urlpatterns = [
    path(
        "<slug:context_type>/<int:context_id>/vazby/<int:link_id>/otevrit/",
        views.open_attachment,
        name="open-attachment",
    ),
    path(
        "<slug:context_type>/<int:context_id>/vazby/<int:link_id>/stahnout/",
        views.download_attachment,
        name="download-attachment",
    ),
]

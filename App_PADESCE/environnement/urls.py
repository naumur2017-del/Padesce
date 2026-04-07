from django.urls import path

from App_PADESCE.core.lazy_urls import lazy_view

urlpatterns = [
    path(
        "", lazy_view("App_PADESCE.environnement.views.environnement"), name="environnement_index"
    ),
    path(
        "export/csv/",
        lazy_view("App_PADESCE.environnement.views.environnement_export_csv"),
        name="environnement_export_csv",
    ),
]

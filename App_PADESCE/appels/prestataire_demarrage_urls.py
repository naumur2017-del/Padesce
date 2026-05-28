from django.urls import path

from App_PADESCE.core.lazy_urls import lazy_view

urlpatterns = [
    path(
        "",
        lazy_view("App_PADESCE.appels.prestataire_demarrage_views.prestataire_demarrage_index"),
        name="prestataire_demarrage_index",
    ),
    path(
        "export/filtered-csv/",
        lazy_view(
            "App_PADESCE.appels.prestataire_demarrage_views."
            "prestataire_demarrage_export_filtered_csv"
        ),
        name="prestataire_demarrage_export_filtered_csv",
    ),
    path(
        "<int:pk>/action/",
        lazy_view("App_PADESCE.appels.prestataire_demarrage_views.prestataire_demarrage_action"),
        name="prestataire_demarrage_action",
    ),
    path(
        "<int:pk>/finalize/",
        lazy_view("App_PADESCE.appels.prestataire_demarrage_views.prestataire_demarrage_finalize"),
        name="prestataire_demarrage_finalize",
    ),
]

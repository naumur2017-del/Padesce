from django.urls import path

from App_PADESCE.core.lazy_urls import lazy_view

urlpatterns = [
    path(
        "",
        lazy_view("App_PADESCE.appels.pas_forme_views.pas_forme_index"),
        name="pas_forme_index",
    ),
    path(
        "export/filtered-csv/",
        lazy_view("App_PADESCE.appels.pas_forme_views.pas_forme_export_filtered_csv"),
        name="pas_forme_export_filtered_csv",
    ),
    path(
        "manual/add/",
        lazy_view("App_PADESCE.appels.pas_forme_views.pas_forme_manual_add"),
        name="pas_forme_manual_add",
    ),
    path(
        "<int:pk>/action/",
        lazy_view("App_PADESCE.appels.pas_forme_views.pas_forme_action"),
        name="pas_forme_action",
    ),
    path(
        "<int:pk>/finalize/",
        lazy_view("App_PADESCE.appels.pas_forme_views.pas_forme_finalize"),
        name="pas_forme_finalize",
    ),
]

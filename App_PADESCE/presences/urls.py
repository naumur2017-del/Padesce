from django.urls import path

from App_PADESCE.core.lazy_urls import lazy_view

urlpatterns = [
    path("", lazy_view("App_PADESCE.presences.views.presence_list"), name="presences_index"),
    path(
        "classes/<int:classe_id>/controle/",
        lazy_view("App_PADESCE.presences.views.presence_control_create"),
        name="presence_control_create",
    ),
    path(
        "classes/<int:classe_id>/controle/<str:control_type>/jumeler/",
        lazy_view("App_PADESCE.presences.views.presence_control_pair_existing"),
        name="presence_control_pair_existing",
    ),
    path(
        "controle/<int:pk>/",
        lazy_view("App_PADESCE.presences.views.presence_control_detail"),
        name="presence_control_detail",
    ),
    path(
        "controle/<int:pk>/export/csv/",
        lazy_view("App_PADESCE.presences.views.presence_control_export_csv"),
        name="presence_control_export_csv",
    ),
    path(
        "controle/<int:pk>/export/xlsx/",
        lazy_view("App_PADESCE.presences.views.presence_control_export_xlsx"),
        name="presence_control_export_xlsx",
    ),
    path(
        "controle/<int:pk>/send-teams/",
        lazy_view("App_PADESCE.presences.views.presence_control_send_teams"),
        name="presence_control_send_teams",
    ),
    path(
        "export/csv/",
        lazy_view("App_PADESCE.presences.views.presence_export_csv"),
        name="presences_export_csv",
    ),
    path("appels/", lazy_view("App_PADESCE.presences.views.appels"), name="appels_index"),
]

from django.urls import path

from App_PADESCE.core.lazy_urls import lazy_view

urlpatterns = [
    path("", lazy_view("App_PADESCE.formations.views.formation_list"), name="formations_index"),
    path("classes/", lazy_view("App_PADESCE.formations.views.class_list"), name="class_list"),
    path(
        "classes/nouveau/",
        lazy_view("App_PADESCE.formations.views.class_create"),
        name="class_create",
    ),
    path(
        "classes/api/cohorte/",
        lazy_view("App_PADESCE.formations.views.api_prestation_cohorte"),
        name="class_cohorte_api",
    ),
    path(
        "classes/<int:pk>/supprimer/",
        lazy_view("App_PADESCE.formations.views.class_delete"),
        name="class_delete",
    ),
    path(
        "classes/<int:pk>/",
        lazy_view("App_PADESCE.formations.views.class_detail"),
        name="class_detail",
    ),
    path(
        "classes/<int:pk>/rapports/",
        lazy_view("App_PADESCE.formations.views.class_reports"),
        name="class_reports",
    ),
    path(
        "classes/<int:pk>/rapports/presences/<str:date_str>/",
        lazy_view("App_PADESCE.formations.views.presence_report_detail"),
        name="presence_report_detail",
    ),
    path(
        "end/toggle-classe/<int:pk>/",
        lazy_view("App_PADESCE.formations.views.class_toggle_status"),
        name="class_toggle_status",
    ),
]

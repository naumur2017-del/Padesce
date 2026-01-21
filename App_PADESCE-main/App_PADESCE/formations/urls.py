from django.urls import path

from App_PADESCE.formations.views import (
    api_prestation_cohorte,
    class_create,
    class_delete,
    class_detail,
    class_list,
    class_toggle_status,
    class_reports,
    presence_report_detail,
    formation_list,
)

urlpatterns = [
    path("", formation_list, name="formations_index"),
    path("classes/", class_list, name="class_list"),
    path("classes/nouveau/", class_create, name="class_create"),
    path("classes/api/cohorte/", api_prestation_cohorte, name="class_cohorte_api"),
    path("classes/<int:pk>/supprimer/", class_delete, name="class_delete"),
    path("classes/<int:pk>/", class_detail, name="class_detail"),
    path("classes/<int:pk>/rapports/", class_reports, name="class_reports"),
    path("classes/<int:pk>/rapports/presences/<str:date_str>/", presence_report_detail, name="presence_report_detail"),
    path("end/toggle-classe/<int:pk>/", class_toggle_status, name="class_toggle_status"),
]

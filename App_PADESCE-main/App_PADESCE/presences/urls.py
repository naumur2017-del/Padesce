from django.urls import path

from App_PADESCE.presences.views import appels, presence_export_csv, presence_list

urlpatterns = [
    path("", presence_list, name="presences_index"),
    path("export/csv/", presence_export_csv, name="presences_export_csv"),
    path("appels/", appels, name="appels_index"),
]

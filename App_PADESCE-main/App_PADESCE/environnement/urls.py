from django.urls import path

from App_PADESCE.environnement.views import environnement, environnement_export_csv

urlpatterns = [
    path("", environnement, name="environnement_index"),
    path("export/csv/", environnement_export_csv, name="environnement_export_csv"),
]

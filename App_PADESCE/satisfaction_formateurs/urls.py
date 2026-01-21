from django.urls import path

from App_PADESCE.satisfaction_formateurs.views import (
    satisfaction_formateurs,
    satisfaction_formateurs_export_csv,
)

urlpatterns = [
    path("", satisfaction_formateurs, name="satisfaction_formateurs_index"),
    path("export/csv/", satisfaction_formateurs_export_csv, name="satisfaction_formateurs_export_csv"),
]

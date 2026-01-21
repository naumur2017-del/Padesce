from django.urls import path

from App_PADESCE.satisfaction_apprenants.views import (
    satisfaction_apprenants,
    satisfaction_apprenants_export_csv,
)

urlpatterns = [
    path("", satisfaction_apprenants, name="satisfaction_apprenants_index"),
    path("export/csv/", satisfaction_apprenants_export_csv, name="satisfaction_apprenants_export_csv"),
]

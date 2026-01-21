from django.urls import path
from django.views.generic import TemplateView

from App_PADESCE.apprenants.views import (
    api_codes,
    delete_apprenants,
    import_csv,
    send_sms,
    update_appartenance,
    update_appartenance_bulk,
)

urlpatterns = [
    path("", TemplateView.as_view(template_name="apprenants/index.html"), name="apprenants_index"),
    path("import/<int:classe_id>/", import_csv, name="apprenants_import"),
    path("api/codes/", api_codes, name="apprenants_api_codes"),
    path("api/appartenance/<int:apprenant_id>/", update_appartenance, name="apprenant_appartenance"),
    path("api/appartenance/bulk/", update_appartenance_bulk, name="apprenant_appartenance_bulk"),
    path("api/delete/", delete_apprenants, name="apprenants_delete"),
    path("api/sms/", send_sms, name="apprenants_sms"),
]

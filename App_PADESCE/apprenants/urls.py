from django.urls import path
from django.views.generic import TemplateView

from App_PADESCE.core.lazy_urls import lazy_view

urlpatterns = [
    path(
        "import/<int:classe_id>/",
        lazy_view("App_PADESCE.apprenants.views.import_csv"),
        name="apprenants_import",
    ),
    path(
        "api/codes/",
        lazy_view("App_PADESCE.apprenants.views.api_codes"),
        name="apprenants_api_codes",
    ),
    path(
        "api/appartenance/<int:apprenant_id>/",
        lazy_view("App_PADESCE.apprenants.views.update_appartenance"),
        name="apprenant_appartenance",
    ),
    path(
        "api/appartenance/bulk/",
        lazy_view("App_PADESCE.apprenants.views.update_appartenance_bulk"),
        name="apprenant_appartenance_bulk",
    ),
    path(
        "api/delete/",
        lazy_view("App_PADESCE.apprenants.views.delete_apprenants"),
        name="apprenants_delete",
    ),
    path("api/sms/", lazy_view("App_PADESCE.apprenants.views.send_sms"), name="apprenants_sms"),
    path(
        "<str:apprenant_code>/",
        lazy_view("App_PADESCE.apprenants.views.redirect_to_analysis_detail"),
        name="apprenant_analysis_shortcut",
    ),
    path(
        "<str:apprenant_code>",
        lazy_view("App_PADESCE.apprenants.views.redirect_to_analysis_detail"),
    ),
    path("", TemplateView.as_view(template_name="apprenants/index.html"), name="apprenants_index"),
]

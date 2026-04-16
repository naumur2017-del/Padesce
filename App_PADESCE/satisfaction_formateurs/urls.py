from django.urls import path

from App_PADESCE.core.lazy_urls import lazy_view

urlpatterns = [
    path(
        "",
        lazy_view("App_PADESCE.satisfaction_formateurs.views.satisfaction_formateurs"),
        name="satisfaction_formateurs_index",
    ),
    path(
        "export/csv/",
        lazy_view("App_PADESCE.satisfaction_formateurs.views.satisfaction_formateurs_export_csv"),
        name="satisfaction_formateurs_export_csv",
    ),
    path(
        "analyse/",
        lazy_view("App_PADESCE.satisfaction_formateurs.views.satisfaction_formateurs_dashboard"),
        name="satisfaction_formateurs_dashboard",
    ),
    path(
        "analyse/export/csv/",
        lazy_view(
            "App_PADESCE.satisfaction_formateurs.views.satisfaction_formateurs_dashboard_export_csv"
        ),
        name="satisfaction_formateurs_dashboard_export_csv",
    ),
    path(
        "analyse/export/chapeau/",
        lazy_view(
            "App_PADESCE.satisfaction_formateurs.views.satisfaction_formateurs_dashboard_export_chapeau"
        ),
        name="satisfaction_formateurs_dashboard_export_chapeau",
    ),
    path(
        "analyse/update-form/",
        lazy_view(
            "App_PADESCE.satisfaction_formateurs.views.satisfaction_formateurs_update_form_page"
        ),
        name="satisfaction_formateurs_update_form_page",
    ),
    path(
        "analyse/gestion/",
        lazy_view("App_PADESCE.satisfaction_formateurs.views.formateurs_prestataires_management"),
        name="formateurs_prestataires_management",
    ),
    path(
        "export/moyennes-generales/xlsx/",
        lazy_view("App_PADESCE.satisfaction_formateurs.views.export_formateur_global_averages_xlsx"),
        name="export_formateur_global_averages",
    ),
]

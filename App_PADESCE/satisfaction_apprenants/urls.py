from django.urls import path

from App_PADESCE.core.lazy_urls import lazy_view

urlpatterns = [
    path(
        "",
        lazy_view("App_PADESCE.satisfaction_apprenants.views.satisfaction_apprenants"),
        name="satisfaction_apprenants_index",
    ),
    path(
        "export/csv/",
        lazy_view("App_PADESCE.satisfaction_apprenants.views.satisfaction_apprenants_export_csv"),
        name="satisfaction_apprenants_export_csv",
    ),
    path(
        "analyse/",
        lazy_view("App_PADESCE.satisfaction_apprenants.views.satisfaction_dashboard"),
        name="satisfaction_dashboard",
    ),
    path(
        "analyse/rag/",
        lazy_view("App_PADESCE.satisfaction_apprenants.views.satisfaction_dashboard_rag"),
        name="satisfaction_dashboard_rag",
    ),
    path(
        "analyse/export/rapport-quotidien/xlsx/",
        lazy_view(
            "App_PADESCE.satisfaction_apprenants.views.satisfaction_dashboard_daily_report_xlsx"
        ),
        name="satisfaction_dashboard_daily_report_xlsx",
    ),
    path(
        "analyse/export/xlsx/",
        lazy_view("App_PADESCE.satisfaction_apprenants.views.satisfaction_dashboard_export_xlsx"),
        name="satisfaction_dashboard_export_xlsx",
    ),
    path(
        "analyse/export/csv/",
        lazy_view("App_PADESCE.satisfaction_apprenants.views.satisfaction_dashboard_export_csv"),
        name="satisfaction_dashboard_export_csv",
    ),
    path(
        "analyse/export/chapeau/",
        lazy_view(
            "App_PADESCE.satisfaction_apprenants.views.satisfaction_dashboard_export_chapeau"
        ),
        name="satisfaction_dashboard_export_chapeau",
    ),
    path(
        "analyse/map-data/",
        lazy_view("App_PADESCE.satisfaction_apprenants.views.satisfaction_map_data"),
        name="satisfaction_map_data",
    ),
]

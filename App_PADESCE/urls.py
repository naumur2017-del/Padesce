from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path

from App_PADESCE.core.lazy_urls import lazy_view

app_urlpatterns = [
    path(
        "",
        lazy_view("App_PADESCE.core.public_views.public_space"),
        name="public_space",
    ),
    path(
        "service-worker.js",
        lazy_view("App_PADESCE.core.pwa_views.service_worker"),
        name="service_worker",
    ),
    path(
        "manifest.webmanifest",
        lazy_view("App_PADESCE.core.pwa_views.web_manifest"),
        name="web_manifest",
    ),
    path("api/chat/", lazy_view("App_PADESCE.core.chat_views.chat_query"), name="chat_query"),
    path(
        "api/chat/download/<str:filename>/",
        lazy_view("App_PADESCE.core.chat_views.download_export"),
        name="download_export",
    ),
    path("dashboard/", lazy_view("App_PADESCE.core.views.home"), name="home"),
    path(
        "suivi-utilisateurs/",
        lazy_view("App_PADESCE.core.views.user_tracking_view"),
        name="user_tracking",
    ),
    path(
        "suivi-utilisateurs/live/",
        lazy_view("App_PADESCE.core.views.user_tracking_live_api"),
        name="user_tracking_live_api",
    ),
    path(
        "api/activity/track/",
        lazy_view("App_PADESCE.core.views.activity_track_api"),
        name="activity_track_api",
    ),
    path(
        "consultant/",
        lazy_view("App_PADESCE.core.views.consultant_dashboard"),
        name="consultant_dashboard",
    ),
    path(
        "consultant/appels/<int:pk>/",
        lazy_view("App_PADESCE.core.views.consultant_call_detail"),
        name="consultant_call_detail",
    ),
    path(
        "classe/<str:code>/",
        lazy_view("App_PADESCE.formations.views.class_analysis_detail"),
        name="class_analysis_detail",
    ),
    path(
        "prestation/<str:code>/",
        lazy_view("App_PADESCE.formations.views.prestation_analysis_detail"),
        name="prestation_analysis_detail",
    ),
    path(
        "analyse/appels/apprenant/<int:pk>/",
        lazy_view("App_PADESCE.formations.views.analysis_apprenant_call_detail"),
        name="analysis_apprenant_call_detail",
    ),
    path(
        "analyse/appels/formateur/<int:pk>/",
        lazy_view("App_PADESCE.formations.views.analysis_formateur_call_detail"),
        name="analysis_formateur_call_detail",
    ),
    path(
        "guide-operateur/",
        lazy_view("App_PADESCE.core.views.operator_guide"),
        name="operator_guide",
    ),
    path(
        "documentation-reporting/",
        lazy_view("App_PADESCE.reporting.views.public_reporting_manual_view"),
        name="public_reporting_manual",
    ),
    path(
        "analyses/fast-stats/export/",
        lazy_view("App_PADESCE.core.views.fast_stats_export_xlsx"),
        name="fast_stats_export_xlsx",
    ),
    path(
        "analyses/fast-stats/api/",
        lazy_view("App_PADESCE.core.views.fast_stats_api"),
        name="fast_stats_api",
    ),
    path("accounts/", include("django.contrib.auth.urls")),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html", redirect_authenticated_user=True
        ),
        name="login",
    ),
    path("formations/", include("App_PADESCE.formations.urls")),
    path("apprenants/", include("App_PADESCE.apprenants.urls")),
    path("presences/", include("App_PADESCE.presences.urls")),
    path("satisfaction-apprenants/", include("App_PADESCE.satisfaction_apprenants.urls")),
    path("satisfaction-formateurs/", include("App_PADESCE.satisfaction_formateurs.urls")),
    path("environnement/", include("App_PADESCE.environnement.urls")),
    path("messages/", include("App_PADESCE.messaging.urls")),
    path("appels/", include("App_PADESCE.appels.urls")),
    path("appels-formateurs/", include("App_PADESCE.appels.formateurs_urls")),
    path("cga/", include("App_PADESCE.appels.cga_urls")),
    path("reporting/", include("App_PADESCE.reporting.urls")),
    path("beneficiaire/", include("App_PADESCE.beneficiaires.urls")),
    path(
        "backup/",
        lazy_view("App_PADESCE.core.backup_views.backup_dashboard"),
        name="backup_dashboard",
    ),
    path(
        "backup/api/start/",
        lazy_view("App_PADESCE.core.backup_views.backup_start"),
        name="backup_start",
    ),
    path(
        "backup/api/status/<str:job_id>/",
        lazy_view("App_PADESCE.core.backup_views.backup_status"),
        name="backup_status",
    ),
    path(
        "backup/api/trigger/",
        lazy_view("App_PADESCE.core.backup_views.backup_trigger"),
        name="backup_trigger",
    ),
    path(
        "backup/download/<str:filename>/",
        lazy_view("App_PADESCE.core.backup_views.backup_download"),
        name="backup_download",
    ),
    path(
        "backup/delete/<str:filename>/",
        lazy_view("App_PADESCE.core.backup_views.backup_delete"),
        name="backup_delete",
    ),
    path(
        "deploiement/",
        lazy_view("App_PADESCE.core.deployment_views.deployment_dashboard"),
        name="deployment_dashboard",
    ),
    path(
        "deploiement/start/",
        lazy_view("App_PADESCE.core.deployment_views.deployment_start"),
        name="deployment_start",
    ),
    path(
        "deploiement/status/<str:run_id>/",
        lazy_view("App_PADESCE.core.deployment_views.deployment_status"),
        name="deployment_status",
    ),
    path(
        "deploiement/live-status/",
        lazy_view("App_PADESCE.core.deployment_views.deployment_live_status"),
        name="deployment_live_status",
    ),
    path(
        "deploiement/live/",
        lazy_view("App_PADESCE.core.deployment_views.deployment_live_status"),
        name="deployment_live",
    ),
    path(
        "deploiement/config/save/",
        lazy_view("App_PADESCE.core.deployment_views.deployment_config_save"),
        name="deployment_config_save",
    ),
]

root_only_urlpatterns = [
    path("admin/", admin.site.urls),
]

urlpatterns = [
    path("", include(app_urlpatterns)),
    path("", include(root_only_urlpatterns)),
    path("padesce/", include((app_urlpatterns, "padesce"), namespace="padesce")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()

handler400 = "App_PADESCE.core.error_views.bad_request"
handler403 = "App_PADESCE.core.error_views.permission_denied"
handler404 = "App_PADESCE.core.error_views.page_not_found"
handler500 = "App_PADESCE.core.error_views.server_error"

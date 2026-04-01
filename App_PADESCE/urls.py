from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path

from App_PADESCE.core.lazy_urls import lazy_view
from App_PADESCE.core import chat_views

urlpatterns = [
    path('', auth_views.LoginView.as_view(template_name="registration/login.html", redirect_authenticated_user=True), name='login'),
    # --- API Chat Agent ---
    path('api/chat/', chat_views.chat_query, name='chat_query'),
    path('api/chat/download/<str:filename>/', chat_views.download_export, name='download_export'),
    # ----------------------
    path('dashboard/', lazy_view('App_PADESCE.core.views.home'), name='home'),
    path('deploiement/', lazy_view('App_PADESCE.core.deployment_views.deployment_dashboard'), name='deployment_dashboard'),
    path('deploiement/live/', lazy_view('App_PADESCE.core.deployment_views.deployment_live_status'), name='deployment_live_status'),
    path('deploiement/api/config/', lazy_view('App_PADESCE.core.deployment_views.deployment_config_save'), name='deployment_config_save'),
    path('deploiement/api/start/', lazy_view('App_PADESCE.core.deployment_views.deployment_start'), name='deployment_start'),
    path('deploiement/api/status/<str:run_id>/', lazy_view('App_PADESCE.core.deployment_views.deployment_status'), name='deployment_status'),
    path('consultant/', lazy_view('App_PADESCE.core.views.consultant_dashboard'), name='consultant_dashboard'),
    path('consultant/appels/<int:pk>/', lazy_view('App_PADESCE.core.views.consultant_call_detail'), name='consultant_call_detail'),
    path('guide-operateur/', lazy_view('App_PADESCE.core.views.operator_guide'), name='operator_guide'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('admin/', admin.site.urls),
    path('formations/', include('App_PADESCE.formations.urls')),
    path('apprenants/', include('App_PADESCE.apprenants.urls')),
    path('presences/', include('App_PADESCE.presences.urls')),
    path('satisfaction-apprenants/', include('App_PADESCE.satisfaction_apprenants.urls')),
    path('satisfaction-formateurs/', include('App_PADESCE.satisfaction_formateurs.urls')),
    path('environnement/', include('App_PADESCE.environnement.urls')),
    path('messages/', include('App_PADESCE.messaging.urls')),
    path('appels/', include('App_PADESCE.appels.urls')),
    path('appels-formateurs/', include('App_PADESCE.appels.formateurs_urls')),
    path('cga/', include('App_PADESCE.appels.cga_urls')),
    path('reporting/', include('App_PADESCE.reporting.urls')),
    path('beneficiaire/', include('App_PADESCE.beneficiaires.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()

handler400 = "App_PADESCE.core.error_views.bad_request"
handler403 = "App_PADESCE.core.error_views.permission_denied"
handler404 = "App_PADESCE.core.error_views.page_not_found"
handler500 = "App_PADESCE.core.error_views.server_error"

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path
from App_PADESCE.core.views import home

urlpatterns = [
    path('', auth_views.LoginView.as_view(template_name="registration/login.html", redirect_authenticated_user=True), name='login'),
    path('dashboard/', home, name='home'),
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
    path('reporting/', include('App_PADESCE.reporting.urls')),
    path('beneficiaire/', include('App_PADESCE.beneficiaires.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()

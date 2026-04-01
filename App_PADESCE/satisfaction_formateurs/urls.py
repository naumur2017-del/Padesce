from django.urls import path

from App_PADESCE.core.lazy_urls import lazy_view

urlpatterns = [
    path('', lazy_view('App_PADESCE.satisfaction_formateurs.views.satisfaction_formateurs'), name='satisfaction_formateurs_index'),
    path('export/csv/', lazy_view('App_PADESCE.satisfaction_formateurs.views.satisfaction_formateurs_export_csv'), name='satisfaction_formateurs_export_csv'),
    path('analyse/', lazy_view('App_PADESCE.satisfaction_formateurs.views.satisfaction_formateurs_dashboard'), name='satisfaction_formateurs_dashboard'),
]

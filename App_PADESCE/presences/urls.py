from django.urls import path

from App_PADESCE.core.lazy_urls import lazy_view

urlpatterns = [
    path('', lazy_view('App_PADESCE.presences.views.presence_list'), name='presences_index'),
    path('export/csv/', lazy_view('App_PADESCE.presences.views.presence_export_csv'), name='presences_export_csv'),
    path('appels/', lazy_view('App_PADESCE.presences.views.appels'), name='appels_index'),
]

from django.urls import path

from App_PADESCE.core.lazy_urls import lazy_view

urlpatterns = [
    path('', lazy_view('App_PADESCE.messaging.views.contacts_view'), name='messaging_index'),
    path('export/csv/', lazy_view('App_PADESCE.messaging.views.contacts_export_csv'), name='messaging_contacts_export'),
    path('campagnes/', lazy_view('App_PADESCE.messaging.views.campagnes_view'), name='messaging_campagnes'),
    path('support/', lazy_view('App_PADESCE.messaging.views.support_center'), name='messaging_support'),
    path('support/alarms/poll/', lazy_view('App_PADESCE.messaging.views.support_alarm_poll'), name='messaging_support_alarm_poll'),
    path('support/alarms/<int:pk>/seen/', lazy_view('App_PADESCE.messaging.views.support_alarm_mark_seen'), name='messaging_support_alarm_seen'),
]

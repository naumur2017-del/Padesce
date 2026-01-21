from django.urls import path

from App_PADESCE.messaging.views import campagnes_view, contacts_export_csv, contacts_view

urlpatterns = [
    path("", contacts_view, name="messaging_index"),
    path("export/csv/", contacts_export_csv, name="messaging_contacts_export"),
    path("campagnes/", campagnes_view, name="messaging_campagnes"),
]

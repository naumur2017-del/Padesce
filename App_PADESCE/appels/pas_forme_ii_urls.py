from django.urls import path
from App_PADESCE.core.lazy_urls import lazy_view

urlpatterns = [
    path("", lazy_view("App_PADESCE.appels.pas_forme_ii_views.index"), name="pas_forme_ii_index"),
    path(
        "export/xlsx/",
        lazy_view("App_PADESCE.appels.pas_forme_ii_views.export_xlsx"),
        name="pas_forme_ii_export_xlsx",
    ),
    path("<int:pk>/form/", lazy_view("App_PADESCE.appels.pas_forme_ii_views.save_form"), name="pas_forme_ii_save_form"),
    path("<int:pk>/update/", lazy_view("App_PADESCE.appels.pas_forme_ii_views.update_form"), name="pas_forme_ii_update"),
    path("<int:pk>/action/", lazy_view("App_PADESCE.appels.pas_forme_ii_views.action"), name="pas_forme_ii_action"),
]

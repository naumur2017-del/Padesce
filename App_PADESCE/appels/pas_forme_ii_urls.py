from django.urls import path
from App_PADESCE.core.lazy_urls import lazy_view

urlpatterns = [
    path("", lazy_view("App_PADESCE.appels.pas_forme_ii_views.index"), name="pas_forme_ii_index"),
    path("<int:pk>/form/", lazy_view("App_PADESCE.appels.pas_forme_ii_views.save_form"), name="pas_forme_ii_save_form"),
    path("<int:pk>/action/", lazy_view("App_PADESCE.appels.pas_forme_ii_views.action"), name="pas_forme_ii_action"),
]

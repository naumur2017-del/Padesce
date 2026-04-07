from django.urls import path

from App_PADESCE.core.lazy_urls import lazy_view

urlpatterns = [
    path(
        "",
        lazy_view("App_PADESCE.beneficiaires.views.beneficiaire_portal"),
        name="beneficiaire_portal",
    ),
    path(
        "history/",
        lazy_view("App_PADESCE.beneficiaires.views.beneficiaire_history"),
        name="beneficiaire_history",
    ),
    path(
        "recap/",
        lazy_view("App_PADESCE.beneficiaires.views.beneficiaire_recap"),
        name="beneficiaire_recap",
    ),
]

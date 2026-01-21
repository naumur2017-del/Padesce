from django.urls import path

from App_PADESCE.beneficiaires.views import (
    beneficiaire_history,
    beneficiaire_portal,
    beneficiaire_recap,
)

urlpatterns = [
    path("", beneficiaire_portal, name="beneficiaire_portal"),
    path("history/", beneficiaire_history, name="beneficiaire_history"),
    path("recap/", beneficiaire_recap, name="beneficiaire_recap"),
]

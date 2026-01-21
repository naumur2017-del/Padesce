from django.urls import path

from App_PADESCE.appels.views import appels_index, appel_action, appel_upload_audio

urlpatterns = [
    path("", appels_index, name="appels_index"),
    path("<int:pk>/action/", appel_action, name="appel_action"),
    path("<int:pk>/upload/", appel_upload_audio, name="appel_upload_audio"),
]

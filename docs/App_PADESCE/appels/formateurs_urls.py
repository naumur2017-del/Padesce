from django.urls import path

from App_PADESCE.appels.formateurs_views import (
    download_formateur_audios,
    formateur_action,
    filtered_formateurs_transcription_status,
    formateur_transcription_detail,
    formateur_transcription_download,
    formateur_upload_audio,
    formateurs_delete_missing_phones,
    formateurs_export_filtered_csv,
    formateurs_export_xlsx,
    formateurs_index,
    start_filtered_formateurs_transcription,
    stop_filtered_formateurs_transcription,
)


urlpatterns = [
    path("", formateurs_index, name="formateurs_index"),
    path("export/xlsx/", formateurs_export_xlsx, name="formateurs_export_xlsx"),
    path("export/filtered-csv/", formateurs_export_filtered_csv, name="formateurs_export_filtered_csv"),
    path("tools/delete-missing-phones/", formateurs_delete_missing_phones, name="formateurs_delete_missing_phones"),
    path("<int:pk>/action/", formateur_action, name="formateur_action"),
    path("<int:pk>/transcription/", formateur_transcription_detail, name="formateur_transcription_detail"),
    path("<int:pk>/transcription/download/", formateur_transcription_download, name="formateur_transcription_download"),
    path("<int:pk>/upload/", formateur_upload_audio, name="formateur_upload_audio"),
    path("audio-download/", download_formateur_audios, name="formateur_download_audios"),
    path("tools/transcribe-filtered/", start_filtered_formateurs_transcription, name="start_filtered_formateurs_transcription"),
    path("tools/transcribe-filtered-status/", filtered_formateurs_transcription_status, name="filtered_formateurs_transcription_status"),
    path("tools/transcribe-filtered-stop/", stop_filtered_formateurs_transcription, name="stop_filtered_formateurs_transcription"),
]

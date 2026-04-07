from django.urls import path

from App_PADESCE.appels.cga_views import (
    cga_action,
    cga_export_filtered_csv,
    cga_export_xlsx,
    cga_index,
    cga_transcription_detail,
    cga_transcription_download,
    cga_upload_audio,
    download_cga_audios,
    filtered_cga_transcription_status,
    start_filtered_cga_transcription,
    stop_filtered_cga_transcription,
)

urlpatterns = [
    path("", cga_index, name="cga_index"),
    path("export/xlsx/", cga_export_xlsx, name="cga_export_xlsx"),
    path("export/filtered-csv/", cga_export_filtered_csv, name="cga_export_filtered_csv"),
    path("<int:pk>/action/", cga_action, name="cga_action"),
    path("<int:pk>/transcription/", cga_transcription_detail, name="cga_transcription_detail"),
    path(
        "<int:pk>/transcription/download/",
        cga_transcription_download,
        name="cga_transcription_download",
    ),
    path("<int:pk>/upload/", cga_upload_audio, name="cga_upload_audio"),
    path("audio-download/", download_cga_audios, name="cga_download_audios"),
    path(
        "tools/transcribe-filtered/",
        start_filtered_cga_transcription,
        name="start_filtered_cga_transcription",
    ),
    path(
        "tools/transcribe-filtered-status/",
        filtered_cga_transcription_status,
        name="filtered_cga_transcription_status",
    ),
    path(
        "tools/transcribe-filtered-stop/",
        stop_filtered_cga_transcription,
        name="stop_filtered_cga_transcription",
    ),
]

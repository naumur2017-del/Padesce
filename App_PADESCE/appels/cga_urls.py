from django.urls import path

from App_PADESCE.core.lazy_urls import lazy_view

urlpatterns = [
    path("", lazy_view("App_PADESCE.appels.cga_views.cga_index"), name="cga_index"),
    path(
        "export/xlsx/",
        lazy_view("App_PADESCE.appels.cga_views.cga_export_xlsx"),
        name="cga_export_xlsx",
    ),
    path(
        "export/filtered-csv/",
        lazy_view("App_PADESCE.appels.cga_views.cga_export_filtered_csv"),
        name="cga_export_filtered_csv",
    ),
    path(
        "<int:pk>/action/", lazy_view("App_PADESCE.appels.cga_views.cga_action"), name="cga_action"
    ),
    path(
        "<int:pk>/transcription/",
        lazy_view("App_PADESCE.appels.cga_views.cga_transcription_detail"),
        name="cga_transcription_detail",
    ),
    path(
        "<int:pk>/transcription/download/",
        lazy_view("App_PADESCE.appels.cga_views.cga_transcription_download"),
        name="cga_transcription_download",
    ),
    path(
        "<int:pk>/upload/",
        lazy_view("App_PADESCE.appels.cga_views.cga_upload_audio"),
        name="cga_upload_audio",
    ),
    path(
        "audio-download/",
        lazy_view("App_PADESCE.appels.cga_views.download_cga_audios"),
        name="cga_download_audios",
    ),
    path(
        "tools/transcribe-filtered/",
        lazy_view("App_PADESCE.appels.cga_views.start_filtered_cga_transcription"),
        name="start_filtered_cga_transcription",
    ),
    path(
        "tools/transcribe-filtered-status/",
        lazy_view("App_PADESCE.appels.cga_views.filtered_cga_transcription_status"),
        name="filtered_cga_transcription_status",
    ),
    path(
        "tools/transcribe-filtered-stop/",
        lazy_view("App_PADESCE.appels.cga_views.stop_filtered_cga_transcription"),
        name="stop_filtered_cga_transcription",
    ),
]

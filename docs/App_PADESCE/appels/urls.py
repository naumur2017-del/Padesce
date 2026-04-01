from django.urls import path
from django.http import JsonResponse

from .views import (
    appels_index,
    appel_action,
    finalize_appel,
    appel_answers_detail,
    appels_export_filtered_csv,
    appels_export_xlsx,
    deduplicate_all_call_tables,
    download_appel_audios,
)
from .consolidation_views import consolidation_pending_appels

urlpatterns = [
    path("", appels_index, name="appels_index"),
    path("consolidation/a-charger/", consolidation_pending_appels, name="appels_consolidation_pending"),
    path("export/xlsx/", appels_export_xlsx, name="appels_export_xlsx"),
    path("export/filtered-csv/", appels_export_filtered_csv, name="appels_export_filtered_csv"),
    path("<int:pk>/action/", appel_action, name="appel_action"),
    path("<int:pk>/finalize/", finalize_appel, name="appel_finalize"),
    path("<int:pk>/answers/", appel_answers_detail, name="appel_answers_detail"),
    path("audio-download/", download_appel_audios, name="appel_download_audios"),
    path("tools/deduplicate/", deduplicate_all_call_tables, name="deduplicate_all_call_tables"),
    
    # Disabled transcription URLs to prevent NoReverseMatch
    path("tools/transcribe-status/", lambda r: JsonResponse({"state": "stopped", "message": "Désactivé"}), name="bulk_transcription_status"),
    path("tools/transcribe-all/", lambda r: JsonResponse({"ok": False, "error": "Désactivé"}), name="start_bulk_transcription"),
    path("tools/transcribe-stop/", lambda r: JsonResponse({"ok": False, "error": "Désactivé"}), name="stop_bulk_transcription"),
    path("tools/transcribe-filtered/", lambda r: JsonResponse({"ok": False, "error": "Désactivé"}), name="start_filtered_appels_transcription"),
    path("tools/transcribe-filtered-status/", lambda r: JsonResponse({"state": "stopped", "message": "Désactivé"}), name="filtered_appels_transcription_status"),
    path("tools/transcribe-filtered-stop/", lambda r: JsonResponse({"ok": False, "error": "Désactivé"}), name="stop_filtered_appels_transcription"),
]

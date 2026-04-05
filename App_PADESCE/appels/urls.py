from django.http import JsonResponse
from django.urls import path

from App_PADESCE.core.lazy_urls import lazy_view

urlpatterns = [
    path('', lazy_view('App_PADESCE.appels.views.appels_index'), name='appels_index'),
    path('consolidation/a-charger/', lazy_view('App_PADESCE.appels.consolidation_views.consolidation_pending_appels'), name='appels_consolidation_pending'),
    path('export/xlsx/', lazy_view('App_PADESCE.appels.views.appels_export_xlsx'), name='appels_export_xlsx'),
    path('export/filtered-csv/', lazy_view('App_PADESCE.appels.views.appels_export_filtered_csv'), name='appels_export_filtered_csv'),
    path('<int:pk>/action/', lazy_view('App_PADESCE.appels.views.appel_action'), name='appel_action'),
    path('<int:pk>/finalize/', lazy_view('App_PADESCE.appels.views.finalize_appel'), name='appel_finalize'),
    path('<int:pk>/upload/', lazy_view('App_PADESCE.appels.views.appel_upload_audio'), name='appel_upload_audio'),
    path('<int:pk>/answers/', lazy_view('App_PADESCE.appels.views.appel_answers_detail'), name='appel_answers_detail'),
    path('audio-download/', lazy_view('App_PADESCE.appels.views.download_appel_audios'), name='appel_download_audios'),
    path('tools/deduplicate/', lazy_view('App_PADESCE.appels.views.deduplicate_all_call_tables'), name='deduplicate_all_call_tables'),
    path('tools/transcribe-status/', lambda r: JsonResponse({'state': 'stopped', 'message': 'Desactive'}), name='bulk_transcription_status'),
    path('tools/transcribe-all/', lambda r: JsonResponse({'ok': False, 'error': 'Desactive'}), name='start_bulk_transcription'),
    path('tools/transcribe-stop/', lambda r: JsonResponse({'ok': False, 'error': 'Desactive'}), name='stop_bulk_transcription'),
    path('tools/transcribe-filtered/', lambda r: JsonResponse({'ok': False, 'error': 'Desactive'}), name='start_filtered_appels_transcription'),
    path('tools/transcribe-filtered-status/', lambda r: JsonResponse({'state': 'stopped', 'message': 'Desactive'}), name='filtered_appels_transcription_status'),
    path('tools/transcribe-filtered-stop/', lambda r: JsonResponse({'ok': False, 'error': 'Desactive'}), name='stop_filtered_appels_transcription'),
]

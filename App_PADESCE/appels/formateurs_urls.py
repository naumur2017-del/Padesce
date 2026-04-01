from django.urls import path

from App_PADESCE.core.lazy_urls import lazy_view

urlpatterns = [
    path('', lazy_view('App_PADESCE.appels.formateurs_views.formateurs_index'), name='formateurs_index'),
    path('export/xlsx/', lazy_view('App_PADESCE.appels.formateurs_views.formateurs_export_xlsx'), name='formateurs_export_xlsx'),
    path('export/filtered-csv/', lazy_view('App_PADESCE.appels.formateurs_views.formateurs_export_filtered_csv'), name='formateurs_export_filtered_csv'),
    path('tools/delete-missing-phones/', lazy_view('App_PADESCE.appels.formateurs_views.formateurs_delete_missing_phones'), name='formateurs_delete_missing_phones'),
    path('<int:pk>/action/', lazy_view('App_PADESCE.appels.formateurs_views.formateur_action'), name='formateur_action'),
    path('<int:pk>/transcription/', lazy_view('App_PADESCE.appels.formateurs_views.formateur_transcription_detail'), name='formateur_transcription_detail'),
    path('<int:pk>/transcription/download/', lazy_view('App_PADESCE.appels.formateurs_views.formateur_transcription_download'), name='formateur_transcription_download'),
    path('<int:pk>/upload/', lazy_view('App_PADESCE.appels.formateurs_views.formateur_upload_audio'), name='formateur_upload_audio'),
    path('audio-download/', lazy_view('App_PADESCE.appels.formateurs_views.download_formateur_audios'), name='formateur_download_audios'),
    path('tools/transcribe-filtered/', lazy_view('App_PADESCE.appels.formateurs_views.start_filtered_formateurs_transcription'), name='start_filtered_formateurs_transcription'),
    path('tools/transcribe-filtered-status/', lazy_view('App_PADESCE.appels.formateurs_views.filtered_formateurs_transcription_status'), name='filtered_formateurs_transcription_status'),
    path('tools/transcribe-filtered-stop/', lazy_view('App_PADESCE.appels.formateurs_views.stop_filtered_formateurs_transcription'), name='stop_filtered_formateurs_transcription'),
]


from django.urls import path

from App_PADESCE.core.lazy_urls import lazy_view

urlpatterns = [
    path('', lazy_view('App_PADESCE.reporting.views.application_report_view'), name='reporting_index'),
    path('rapport/', lazy_view('App_PADESCE.reporting.views.application_report_view'), name='application_report'),
    path('rapport/view/', lazy_view('App_PADESCE.reporting.views.application_report_view'), name='application_report_view'),
    path('rapport/export/excel/', lazy_view('App_PADESCE.reporting.views.application_report_export_excel'), name='application_report_export_excel'),
    path('rapport/export/csv/', lazy_view('App_PADESCE.reporting.views.application_report_export_csv_view'), name='application_report_export_csv'),
    path('rapport/export/word/', lazy_view('App_PADESCE.reporting.views.application_report_export_word_view'), name='application_report_export_word'),
    path('rapport/send-mail/', lazy_view('App_PADESCE.reporting.views.application_report_send_mail_view'), name='application_report_send_mail'),
    path('excel-reseau/', lazy_view('App_PADESCE.reporting.network_excel.network_excel_view'), name='reporting_network_excel'),
    path('api/excel-reseau/', lazy_view('App_PADESCE.reporting.network_excel.network_excel_api'), name='reporting_network_excel_api'),
    path('consolidation/', lazy_view('App_PADESCE.reporting.views.consolidation_view'), name='consolidation_index'),
    path('consolidation/apprenants.xlsx', lazy_view('App_PADESCE.reporting.views.export_consolidation_apprenants_excel'), name='consolidation_apprenants_excel'),
    path('consolidation/appels-termines.xlsx', lazy_view('App_PADESCE.reporting.views.export_appels_termines_excel'), name='consolidation_appels_termines_excel'),
    path('consolidation/appels-termines.csv', lazy_view('App_PADESCE.reporting.views.export_appels_termines_csv'), name='consolidation_appels_termines_csv'),
    path('export/csv/', lazy_view('App_PADESCE.reporting.views.export_csv'), name='reporting_export_csv'),
    path('export/excel/', lazy_view('App_PADESCE.reporting.views.export_excel'), name='reporting_export_excel'),
    path('api/<str:code>/', lazy_view('App_PADESCE.reporting.api.api_chart'), name='reporting_api_chart'),
    path('embed/<str:code>/', lazy_view('App_PADESCE.reporting.views.reporting_embed'), name='reporting_embed'),
    path('embed/table/<str:code>/', lazy_view('App_PADESCE.reporting.views.reporting_embed_table'), name='reporting_embed_table'),
]

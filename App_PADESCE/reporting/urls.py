from django.urls import path

from App_PADESCE.reporting.api import api_chart
from App_PADESCE.reporting.views import (
    consolidation_view,
    export_csv,
    export_excel,
    reporting_home,
    reporting_embed,
    reporting_embed_table,
)

urlpatterns = [
    path("", reporting_home, name="reporting_index"),
    path("consolidation/", consolidation_view, name="consolidation_index"),
    path("export/csv/", export_csv, name="reporting_export_csv"),
    path("export/excel/", export_excel, name="reporting_export_excel"),
    path("api/<str:code>/", api_chart, name="reporting_api_chart"),
    path("embed/<str:code>/", reporting_embed, name="reporting_embed"),
    path("embed/table/<str:code>/", reporting_embed_table, name="reporting_embed_table"),
]

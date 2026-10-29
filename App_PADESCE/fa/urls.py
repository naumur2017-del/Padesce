from django.urls import path

from App_PADESCE.core.lazy_urls import lazy_view

urlpatterns = [
    path("", lazy_view("App_PADESCE.fa.views.index"), name="fa_index"),
    path("analyses/", lazy_view("App_PADESCE.fa.views.analytics"), name="fa_analytics"),
    path("export/", lazy_view("App_PADESCE.fa.views.export"), name="fa_export"),
    path("import/", lazy_view("App_PADESCE.fa.views.import_enterprises"), name="fa_import"),
    path("<int:pk>/", lazy_view("App_PADESCE.fa.views.detail"), name="fa_detail"),
    path("<int:pk>/start/", lazy_view("App_PADESCE.fa.views.start"), name="fa_start"),
    path(
        "attempts/<int:pk>/audio/",
        lazy_view("App_PADESCE.fa.views.upload_audio"),
        name="fa_upload_audio",
    ),
    path("attempts/<int:pk>/save/", lazy_view("App_PADESCE.fa.views.save"), name="fa_save"),
    path("attempts/<int:pk>/finish/", lazy_view("App_PADESCE.fa.views.finish"), name="fa_finish"),
    path("attempts/<int:pk>/state/", lazy_view("App_PADESCE.fa.views.state"), name="fa_state"),
    path("recordings/<int:pk>/", lazy_view("App_PADESCE.fa.views.audio"), name="fa_audio"),
]

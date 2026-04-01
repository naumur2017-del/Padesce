from django.contrib import admin

from .models import SatisfactionApprenant, Transcription


@admin.register(SatisfactionApprenant)
class SatisfactionApprenantAdmin(admin.ModelAdmin):
    list_display = ("date", "classe", "apprenant", "appel", "q9_satisfaction_globale")
    list_filter = ("classe", "date")
    search_fields = ("apprenant__nom_complet", "classe__code", "appel__code", "appel__nom")


@admin.register(Transcription)
class TranscriptionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "apprenant", "appel", "engine")
    list_filter = ("engine", "created_at")
    search_fields = ("apprenant__nom_complet", "appel__code", "transcript")

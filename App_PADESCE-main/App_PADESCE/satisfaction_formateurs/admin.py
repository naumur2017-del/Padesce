from django.contrib import admin

from .models import SatisfactionFormateur


@admin.register(SatisfactionFormateur)
class SatisfactionFormateurAdmin(admin.ModelAdmin):
    list_display = ("classe", "formateur", "date", "q9_satisfaction_globale_prestataire")
    list_filter = ("classe", "date")
    search_fields = ("formateur__nom_complet", "classe__code")

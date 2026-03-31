from django.contrib import admin

from .models import SatisfactionFormateur


@admin.register(SatisfactionFormateur)
class SatisfactionFormateurAdmin(admin.ModelAdmin):
    list_display = ("classe", "formateur", "date", "q1_prerequis_apprenants", "q2_interaction_apprenants", "q3_competences_acquises")
    list_filter = ("classe", "date")
    search_fields = ("formateur__nom_complet", "classe__code")

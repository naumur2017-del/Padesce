from django.contrib import admin

from .models import SatisfactionApprenant


@admin.register(SatisfactionApprenant)
class SatisfactionApprenantAdmin(admin.ModelAdmin):
    list_display = ("classe", "apprenant", "date", "q9_satisfaction_globale")
    list_filter = ("classe", "date")
    search_fields = ("apprenant__nom_complet", "classe__code")

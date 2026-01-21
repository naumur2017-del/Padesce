from django.contrib import admin

from .models import Apprenant


@admin.register(Apprenant)
class ApprenantAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "nom_complet",
        "classe",
        "formation",
        "telephone1",
        "ville_residence",
        "fenetre",
        "actif",
    )
    search_fields = ("code", "nom_complet", "telephone1", "telephone2")
    list_filter = ("classe", "formation", "fenetre", "actif")

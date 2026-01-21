from django.contrib import admin

from .models import Presence


@admin.register(Presence)
class PresenceAdmin(admin.ModelAdmin):
    list_display = (
        "classe",
        "apprenant",
        "date",
        "presence",
        "statut",
        "moyen_enregistrement",
        "inspecteur",
    )
    list_filter = ("classe", "presence", "statut", "moyen_enregistrement", "date")
    search_fields = ("apprenant__nom_complet", "classe__code")

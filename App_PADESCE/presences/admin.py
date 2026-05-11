from django.contrib import admin

from .models import Presence, PresenceControl


class PresenceInline(admin.TabularInline):
    model = Presence
    extra = 0
    fields = ("apprenant", "presence", "statut", "moyen_enregistrement", "heure_presence")
    readonly_fields = ("apprenant",)


@admin.register(PresenceControl)
class PresenceControlAdmin(admin.ModelAdmin):
    list_display = (
        "classe",
        "type_controle",
        "date",
        "inspecteur",
        "conformite",
        "teams_sent_at",
    )
    list_filter = ("type_controle", "conformite", "date", "classe")
    search_fields = ("classe__code", "theme", "inspecteur__nom_complet")
    inlines = [PresenceInline]


@admin.register(Presence)
class PresenceAdmin(admin.ModelAdmin):
    list_display = (
        "controle",
        "classe",
        "apprenant",
        "date",
        "presence",
        "statut",
        "moyen_enregistrement",
        "inspecteur",
    )
    list_filter = ("controle", "classe", "presence", "statut", "moyen_enregistrement", "date")
    search_fields = ("apprenant__nom_complet", "classe__code")

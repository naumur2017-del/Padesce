from django.contrib import admin

from App_PADESCE.appels.models import AppelPasForme, CallAlert


@admin.register(AppelPasForme)
class AppelPasFormeAdmin(admin.ModelAdmin):
    list_display = ("id", "nom", "telephone", "prestation_id", "status", "is_active")
    list_filter = ("status", "is_active", "prestation_id")
    search_fields = ("nom", "telephone", "prestation_id", "prestataire", "beneficiaire")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CallAlert)
class CallAlertAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source",
        "reporter",
        "status",
        "assigned_to",
        "created_at",
        "first_response_at",
        "resolved_at",
    )
    list_filter = ("source", "status", "created_at")
    search_fields = ("reporter__username", "details", "call_label", "call_id")
    readonly_fields = ("created_at", "updated_at", "user_agent", "last_actions")
    autocomplete_fields = ("reporter", "assigned_to", "admin_seen_by")

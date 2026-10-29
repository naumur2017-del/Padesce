from django.contrib import admin

from .models import CallAttempt, Enterprise, Recording


@admin.register(Enterprise)
class EnterpriseAdmin(admin.ModelAdmin):
    list_display = ("reference", "campaign", "name", "phone", "city", "sector", "status")
    list_filter = ("campaign", "status", "sector", "city")
    search_fields = ("reference", "name", "phone")
    readonly_fields = ("campaign", "answers", "status", "callback_at")


@admin.register(CallAttempt)
class CallAttemptAdmin(admin.ModelAdmin):
    list_display = ("enterprise", "agent", "status", "started_at", "ended_at")
    readonly_fields = tuple(field.name for field in CallAttempt._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = ("attempt", "sequence", "is_final", "byte_size", "created_at")
    readonly_fields = tuple(field.name for field in Recording._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

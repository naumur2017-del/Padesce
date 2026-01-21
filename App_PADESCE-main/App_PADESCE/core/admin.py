from django.contrib import admin

from App_PADESCE.core.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("model_name", "object_pk", "action", "actor", "timestamp")
    list_filter = ("model_name", "action", "actor")
    search_fields = ("model_name", "object_pk", "object_repr", "actor__username")
    readonly_fields = ("model_name", "object_pk", "object_repr", "action", "actor", "timestamp", "extra")

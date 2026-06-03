from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User

from App_PADESCE.core.models import AuditLog, UserActivity, UserActivityEvent, UserLoginLog


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class SafeUserAdmin(UserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "is_active")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("username", "first_name", "last_name", "email")


@admin.register(Group)
class SafeGroupAdmin(GroupAdmin):
    filter_horizontal = ("permissions",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("model_name", "object_pk", "action", "actor", "timestamp")
    list_filter = ("model_name", "action", "actor")
    search_fields = ("model_name", "object_pk", "object_repr", "actor__username")
    readonly_fields = (
        "model_name",
        "object_pk",
        "object_repr",
        "action",
        "actor",
        "timestamp",
        "extra",
    )


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "last_seen",
        "last_ip",
        "last_city",
        "last_country",
        "current_page",
        "last_action_type",
    )
    search_fields = ("user__username", "last_ip", "last_city", "last_country", "current_page")
    readonly_fields = (
        "user",
        "last_seen",
        "last_ip",
        "last_latitude",
        "last_longitude",
        "last_city",
        "last_country",
        "current_page",
        "current_page_title",
        "last_action_type",
        "last_action_label",
        "last_action_target",
        "last_action_at",
    )


@admin.register(UserLoginLog)
class UserLoginLogAdmin(admin.ModelAdmin):
    list_display = ("user", "logged_at", "ip_address", "city", "country")
    search_fields = ("user__username", "ip_address", "city", "country")
    list_filter = ("country", "city")
    readonly_fields = (
        "user",
        "logged_at",
        "ip_address",
        "latitude",
        "longitude",
        "city",
        "country",
    )


@admin.register(UserActivityEvent)
class UserActivityEventAdmin(admin.ModelAdmin):
    list_display = ("user", "event_type", "page_path", "target_label", "occurred_at")
    search_fields = ("user__username", "page_path", "page_title", "target_label", "target_path")
    list_filter = ("event_type",)
    readonly_fields = (
        "user",
        "event_type",
        "page_path",
        "page_title",
        "target_label",
        "target_path",
        "occurred_at",
    )

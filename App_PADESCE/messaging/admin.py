from django.contrib import admin

from .models import CampagneMessage, Contact, SupportAlarm, SupportMessage


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("nom_complet", "telephone", "prestataire", "fenetre", "ville_residence", "actif")
    search_fields = ("nom_complet", "telephone", "ville_residence")
    list_filter = ("prestataire", "fenetre", "actif")


@admin.register(CampagneMessage)
class CampagneMessageAdmin(admin.ModelAdmin):
    list_display = ("date_heure", "cible_description", "enqueteur")
    list_filter = ("date_heure",)


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "sender", "recipient", "kind", "is_read")
    list_filter = ("kind", "is_read", "created_at")
    search_fields = ("sender__username", "recipient__username", "body")


@admin.register(SupportAlarm)
class SupportAlarmAdmin(admin.ModelAdmin):
    list_display = ("created_at", "title", "reporter", "module", "is_seen", "is_resolved")
    list_filter = ("is_seen", "is_resolved", "module", "created_at")
    search_fields = ("title", "details", "reporter__username")

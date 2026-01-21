from django.contrib import admin

from .models import CampagneMessage, Contact


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("nom_complet", "telephone", "prestataire", "fenetre", "ville_residence", "actif")
    search_fields = ("nom_complet", "telephone", "ville_residence")
    list_filter = ("prestataire", "fenetre", "actif")


@admin.register(CampagneMessage)
class CampagneMessageAdmin(admin.ModelAdmin):
    list_display = ("date_heure", "cible_description", "enqueteur")
    list_filter = ("date_heure",)

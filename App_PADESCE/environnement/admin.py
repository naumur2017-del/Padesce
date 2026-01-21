from django.contrib import admin

from .models import EnqueteEnvironnement


@admin.register(EnqueteEnvironnement)
class EnqueteEnvironnementAdmin(admin.ModelAdmin):
    list_display = ("classe", "date", "tables", "chaises", "ventilation", "securite")
    list_filter = ("classe", "date")

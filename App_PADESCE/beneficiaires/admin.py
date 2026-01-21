from django.contrib import admin

from App_PADESCE.beneficiaires.models import BeneficiaireUpload


@admin.register(BeneficiaireUpload)
class BeneficiaireUploadAdmin(admin.ModelAdmin):
    list_display = ("beneficiaire_nom", "prestataire_nom", "est_rejete", "created_at")
    list_filter = ("est_rejete", "created_at")
    search_fields = ("beneficiaire_nom", "prestataire_nom")

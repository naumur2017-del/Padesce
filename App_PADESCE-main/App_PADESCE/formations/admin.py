from django.contrib import admin

from .models import Beneficiaire, Classe, Formateur, Formation, Inspecteur, Lieu, Prestation, Prestataire


@admin.register(Formateur)
class FormateurAdmin(admin.ModelAdmin):
    list_display = ("code", "nom_complet", "specialite", "fenetre", "telephone", "actif")
    search_fields = ("code", "nom_complet", "specialite", "telephone")
    list_filter = ("fenetre", "actif")


@admin.register(Prestataire)
class PrestataireAdmin(admin.ModelAdmin):
    list_display = ("code", "raison_sociale", "type_structure", "telephone", "email", "actif")
    search_fields = ("code", "raison_sociale")
    list_filter = ("type_structure", "actif")


@admin.register(Formation)
class FormationAdmin(admin.ModelAdmin):
    list_display = ("code", "nom", "statut", "fenetre", "actif")
    list_filter = ("statut", "fenetre", "actif")
    search_fields = ("code", "nom", "nom_harmonise")


@admin.register(Beneficiaire)
class BeneficiaireAdmin(admin.ModelAdmin):
    list_display = ("nom_structure", "type_structure", "region", "ville", "actif")
    search_fields = ("nom_structure", "ville", "region")
    list_filter = ("region", "type_structure", "actif")


@admin.register(Prestation)
class PrestationAdmin(admin.ModelAdmin):
    list_display = ("code", "prestataire", "formation", "beneficiaire", "effectif_a_former", "actif")
    search_fields = ("code",)
    list_filter = ("prestataire", "formation", "beneficiaire", "actif")


@admin.register(Lieu)
class LieuAdmin(admin.ModelAdmin):
    list_display = ("code", "nom_lieu", "region", "departement", "ville", "actif")
    search_fields = ("code", "nom_lieu", "ville", "region")
    list_filter = ("region", "actif")


@admin.register(Inspecteur)
class InspecteurAdmin(admin.ModelAdmin):
    list_display = ("code", "nom_complet", "telephone", "email", "actif")
    search_fields = ("code", "nom_complet", "telephone", "email")
    list_filter = ("actif",)


@admin.register(Classe)
class ClasseAdmin(admin.ModelAdmin):
    list_display = ("code", "formation", "prestation", "lieu", "formateur", "fenetre", "cohorte", "statut", "actif")
    search_fields = ("code", "intitule_formation")
    list_filter = ("formation", "prestation", "fenetre", "statut", "actif")

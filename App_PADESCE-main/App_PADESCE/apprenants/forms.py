from django import forms


class ImportApprenantsForm(forms.Form):
    fichier = forms.FileField(
        widget=forms.ClearableFileInput(attrs={"accept": ".csv,.xlsx,.xlsm"}),
        help_text=(
            "CSV/XLSX/XLSM (ligne d'en-tete obligatoire). "
            "Colonnes typiques : No, Nom complet, Beneficiaire, Genre, Age, Fonction, Diplome, "
            "Nb d'annees d'experience, Ville de residence, Prestataire, Intitule sollicite, "
            "Intitule dispense, Fenetre, Ville formation, Arrondissement, Departement, Region, "
            "Lieu, Precision lieu, Longitude, Latitude, 1er numero, 2e numero, Cohorte, Tel formateur, Code (optionnel)"
        )
    )
    generate_codes = forms.BooleanField(required=False, initial=False)
    edited_rows = forms.CharField(required=False, widget=forms.HiddenInput())

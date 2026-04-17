from django import forms


class ConsolidationUploadForm(forms.Form):
    fichier = forms.FileField(
        label="Fichier consolidé",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsm,.xlsx"}),
        help_text="Fichier Excel consolidé (feuille 'Consolidation').",
        required=False,
    )

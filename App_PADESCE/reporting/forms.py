from django import forms


class ConsolidationUploadForm(forms.Form):
    fichier = forms.FileField(
        label="Fichier consolide",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsm,.xlsx"}),
        help_text="Fichier Excel consolide (feuille 'Consolidation').",
        required=False,
    )

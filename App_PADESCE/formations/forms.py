from django import forms

from App_PADESCE.formations.models import Classe


class ClasseCreateForm(forms.ModelForm):
    lieu_nom = forms.CharField(
        required=False,
        label="Nom du lieu / Quartier",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: Hotel de ville"}),
    )
    lieu_precision = forms.CharField(
        required=False,
        label="Precision du lieu",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Adresse, point de repere..."}),
    )
    lieu_arrondissement = forms.CharField(
        required=False, label="Arrondissement", widget=forms.TextInput(attrs={"class": "form-control"})
    )
    lieu_departement = forms.CharField(
        required=False, label="Departement", widget=forms.TextInput(attrs={"class": "form-control"})
    )
    lieu_ville = forms.CharField(
        required=False, label="Ville", widget=forms.TextInput(attrs={"class": "form-control"})
    )
    lieu_region = forms.CharField(
        required=False, label="Region (Cameroun)", widget=forms.TextInput(attrs={"class": "form-control"})
    )
    lieu_longitude = forms.CharField(
        required=False, label="Longitude", widget=forms.TextInput(attrs={"class": "form-control"})
    )
    lieu_latitude = forms.CharField(
        required=False, label="Latitude", widget=forms.TextInput(attrs={"class": "form-control"})
    )
    class Meta:
        model = Classe
        fields = [
            "code",
            "prestation",
            "intitule_formation",
            "formateur",
            "fenetre",
            "cohorte",
            "statut",
        ]
        widgets = {
            "code": forms.TextInput(attrs={"readonly": "readonly", "class": "form-control"}),
            "intitule_formation": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: Transformation agroalimentaire"}),
            "prestation": forms.Select(attrs={"class": "form-select"}),
            "formateur": forms.Select(attrs={"class": "form-select"}),
            "fenetre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Fenêtre 2 ou 3"}),
            "cohorte": forms.NumberInput(attrs={"readonly": "readonly", "class": "form-control"}),
            "statut": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_code(self):
        # Ensure code is not modified by the user.
        return self.initial.get("code") or self.cleaned_data.get("code")

    def clean_cohorte(self):
        return self.initial.get("cohorte") or self.cleaned_data.get("cohorte")

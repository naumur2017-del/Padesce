from django import forms

from App_PADESCE.environnement.models import EnqueteEnvironnement


class EnqueteEnvironnementForm(forms.ModelForm):
    class Meta:
        model = EnqueteEnvironnement
        exclude = ["enqueteur"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "heure_enregistrement": forms.TimeInput(attrs={"type": "time"}),
            "commentaire_salle": forms.Textarea(attrs={"rows": 2}),
            "commentaire_global": forms.Textarea(attrs={"rows": 2}),
        }

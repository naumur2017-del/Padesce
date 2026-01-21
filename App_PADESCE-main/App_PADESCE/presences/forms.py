from django import forms

from App_PADESCE.presences.models import Presence


class PresenceForm(forms.ModelForm):
    class Meta:
        model = Presence
        fields = [
            "classe",
            "apprenant",
            "inspecteur",
            "date",
            "heure_debut",
            "heure_fin",
            "presence",
            "statut",
            "moyen_enregistrement",
            "remarques",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "heure_debut": forms.TimeInput(attrs={"type": "time"}),
            "heure_fin": forms.TimeInput(attrs={"type": "time"}),
            "remarques": forms.Textarea(attrs={"rows": 2}),
        }

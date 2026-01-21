from django import forms

from App_PADESCE.satisfaction_formateurs.models import SatisfactionFormateur


class SatisfactionFormateurForm(forms.ModelForm):
    class Meta:
        model = SatisfactionFormateur
        fields = [
            "classe",
            "formateur",
            "inspecteur",
            "date",
            "heure",
            "q1_motivation_apprenants",
            "q2_niveau_prerequis",
            "q3",
            "q4",
            "q5",
            "q6",
            "q7",
            "q8",
            "q9_satisfaction_globale_prestataire",
            "commentaires",
            "recommandations",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "heure": forms.TimeInput(attrs={"type": "time"}),
            "commentaires": forms.Textarea(attrs={"rows": 2}),
            "recommandations": forms.Textarea(attrs={"rows": 2}),
        }

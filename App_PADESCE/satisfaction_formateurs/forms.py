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
            "q1_prerequis_apprenants",
            "q2_interaction_apprenants",
            "q3_competences_acquises",
            "q4_gestion_administrative",
            "q5_gestion_financiere",
            "q6_communication",
            "commentaires",
            "recommandations",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "heure": forms.TimeInput(attrs={"type": "time"}),
            "q4_gestion_administrative": forms.Textarea(attrs={"rows": 3}),
            "q5_gestion_financiere": forms.Textarea(attrs={"rows": 3}),
            "q6_communication": forms.Textarea(attrs={"rows": 3}),
            "commentaires": forms.Textarea(attrs={"rows": 2}),
            "recommandations": forms.Textarea(attrs={"rows": 2}),
        }

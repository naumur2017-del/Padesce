from django import forms

from App_PADESCE.satisfaction_apprenants.models import SatisfactionApprenant


class SatisfactionApprenantForm(forms.ModelForm):
    class Meta:
        model = SatisfactionApprenant
        fields = [
            "classe",
            "apprenant",
            "inspecteur",
            "date",
            "heure",
            "q1_clarte_exposes",
            "q2_interaction_formateur",
            "q3_rythme_formation",
            "q4_qualite_supports",
            "q5_applicabilite_contenu",
            "q6_organisation_logistique",
            "q7_respect_programme",
            "q8_adequation_besoins",
            "q9_satisfaction_globale",
            "commentaire",
            "recommandations",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "heure": forms.TimeInput(attrs={"type": "time"}),
            "commentaire": forms.Textarea(attrs={"rows": 2}),
            "recommandations": forms.Textarea(attrs={"rows": 2}),
        }

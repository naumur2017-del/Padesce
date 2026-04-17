import re

from django import forms

from App_PADESCE.appels.models import Appel
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
            "q3_maitrise_contenu",
            "q4_salle_adequate",
            "q5_materiel_disponible",
            "q6_organisation_temps",
            "q7_utilite_formation",
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


class SatisfactionBatchUpdateForm(forms.Form):
    classe_code = forms.CharField(
        required=False,
        label="Code classe",
        help_text="Optionnel. Applique a tous les codes sans classe explicite.",
        widget=forms.TextInput(
            attrs={
                "placeholder": "CLA001",
                "autocomplete": "off",
            }
        ),
    )
    codes_text = forms.CharField(
        required=False,
        label="Codes apprenants",
        help_text=(
            "Accepte un code par ligne, une liste entre crochets comme "
            "[APP100, APP101] ou le format CODE|CLASSE pour forcer la classe. "
            "Laissez vide si vous selectionnez les lignes plus bas."
        ),
        widget=forms.Textarea(
            attrs={
                "rows": 10,
                "placeholder": "[APP100, APP101]\nAPP102|CLA002",
            }
        ),
    )
    target_status = forms.ChoiceField(
        required=False,
        label="Statut a appliquer",
        help_text="Utilise uniquement par le bouton de changement de statut.",
        choices=(),
    )
    q1_clarte_exposes = forms.CharField(
        required=False,
        label="Q1 Clarte des exposes",
        help_text="Une valeur unique (ex. : 4) ou une liste ordonnee [4,5].",
        widget=forms.TextInput(
            attrs={
                "placeholder": "4 ou [4,5]",
                "autocomplete": "off",
            }
        ),
    )
    q2_interaction_formateur = forms.CharField(
        required=False,
        label="Q2 Interaction formateur",
        help_text="Une valeur unique (ex. : 4) ou une liste ordonnee [4,5].",
        widget=forms.TextInput(
            attrs={
                "placeholder": "4 ou [4,5]",
                "autocomplete": "off",
            }
        ),
    )
    q3_maitrise_contenu = forms.CharField(
        required=False,
        label="Q3 Maitrise du contenu",
        help_text="Une valeur unique (ex. : 4) ou une liste ordonnee [4,5].",
        widget=forms.TextInput(
            attrs={
                "placeholder": "4 ou [4,5]",
                "autocomplete": "off",
            }
        ),
    )
    q4_salle_adequate = forms.CharField(
        required=False,
        label="Q4 Salle adequate",
        help_text="Une valeur unique (ex. : 4) ou une liste ordonnee [4,5].",
        widget=forms.TextInput(
            attrs={
                "placeholder": "4 ou [4,5]",
                "autocomplete": "off",
            }
        ),
    )
    q5_materiel_disponible = forms.CharField(
        required=False,
        label="Q5 Materiel disponible",
        help_text="Une valeur unique (ex. : 4) ou une liste ordonnee [4,5].",
        widget=forms.TextInput(
            attrs={
                "placeholder": "4 ou [4,5]",
                "autocomplete": "off",
            }
        ),
    )
    q6_organisation_temps = forms.CharField(
        required=False,
        label="Q6 Organisation du temps",
        help_text="Une valeur unique (ex. : 4) ou une liste ordonnee [4,5].",
        widget=forms.TextInput(
            attrs={
                "placeholder": "4 ou [4,5]",
                "autocomplete": "off",
            }
        ),
    )
    q7_utilite_formation = forms.CharField(
        required=False,
        label="Q7 Utilite de la formation",
        help_text="Une valeur unique (ex. : 4) ou une liste ordonnee [4,5].",
        widget=forms.TextInput(
            attrs={
                "placeholder": "4 ou [4,5]",
                "autocomplete": "off",
            }
        ),
    )
    q8_adequation_besoins = forms.CharField(
        required=False,
        label="Q8 Adequation aux besoins",
        help_text="Une valeur unique (ex. : 4) ou une liste ordonnee [4,5].",
        widget=forms.TextInput(
            attrs={
                "placeholder": "4 ou [4,5]",
                "autocomplete": "off",
            }
        ),
    )
    q9_satisfaction_globale = forms.CharField(
        required=False,
        label="Q9 Satisfaction globale",
        help_text="Une valeur unique (ex. : 4) ou une liste ordonnee [4,5].",
        widget=forms.TextInput(
            attrs={
                "placeholder": "4 ou [4,5]",
                "autocomplete": "off",
            }
        ),
    )
    commentaire_values = forms.CharField(
        required=False,
        label="Commentaires",
        help_text=(
            "Texte unique ou liste ordonnee entre crochets. "
            "Exemple : [RAS, Besoin de suivi]."
        ),
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "RAS ou [RAS, Besoin de suivi]",
            }
        ),
    )
    recommandations_values = forms.CharField(
        required=False,
        label="Recommandations",
        help_text=(
            "Texte unique ou liste ordonnee entre crochets. "
            "Exemple : [Continuer, Renforcer l'accompagnement]."
        ),
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "RAS ou [Continuer, Renforcer l'accompagnement]",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target_status"].choices = [
            ("", "Selectionner un statut"),
            *Appel.STATUS_CHOICES,
        ]
        self.initial.setdefault("target_status", "termine")

    @staticmethod
    def _normalize_container(raw_value: str) -> str:
        text = str(raw_value or "").strip()
        if text.startswith("[") and text.endswith("]"):
            return text[1:-1].strip()
        return text

    @classmethod
    def _split_segments(cls, raw_value: str) -> list[str]:
        return [
            item.strip()
            for item in re.split(r"[,;\r\n]+", cls._normalize_container(raw_value))
            if item.strip()
        ]

    def _clean_score_values(self, field_name: str) -> list[int]:
        raw_value = self.cleaned_data.get(field_name, "")
        raw_items = self._split_segments(raw_value)
        if not raw_items:
            return []
        scores: list[int] = []
        invalid_items: list[str] = []
        for item in raw_items:
            if not item.isdigit():
                invalid_items.append(item)
                continue
            score = int(item)
            if score < 1 or score > 5:
                invalid_items.append(item)
                continue
            scores.append(score)
        if invalid_items:
            raise forms.ValidationError("Les notes doivent etre comprises entre 1 et 5.")
        return scores

    def clean_q1_clarte_exposes(self) -> list[int]:
        return self._clean_score_values("q1_clarte_exposes")

    def clean_q2_interaction_formateur(self) -> list[int]:
        return self._clean_score_values("q2_interaction_formateur")

    def clean_q3_maitrise_contenu(self) -> list[int]:
        return self._clean_score_values("q3_maitrise_contenu")

    def clean_q4_salle_adequate(self) -> list[int]:
        return self._clean_score_values("q4_salle_adequate")

    def clean_q5_materiel_disponible(self) -> list[int]:
        return self._clean_score_values("q5_materiel_disponible")

    def clean_q6_organisation_temps(self) -> list[int]:
        return self._clean_score_values("q6_organisation_temps")

    def clean_q7_utilite_formation(self) -> list[int]:
        return self._clean_score_values("q7_utilite_formation")

    def clean_q8_adequation_besoins(self) -> list[int]:
        return self._clean_score_values("q8_adequation_besoins")

    def clean_q9_satisfaction_globale(self) -> list[int]:
        return self._clean_score_values("q9_satisfaction_globale")

    def clean_commentaire_values(self) -> list[str]:
        return self._split_segments(self.cleaned_data.get("commentaire_values", ""))

    def clean_recommandations_values(self) -> list[str]:
        return self._split_segments(self.cleaned_data.get("recommandations_values", ""))

    def clean(self):
        return super().clean()

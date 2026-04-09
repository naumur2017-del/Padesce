import re

from django import forms

from App_PADESCE.appels.models import AppelFormateur
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


class SatisfactionFormateurBatchUpdateForm(forms.Form):
    reference_codes_text = forms.CharField(
        required=False,
        label="References d'appel formateur",
        help_text=(
            "Accepte une reference par ligne ou une liste entre crochets comme "
            "[FORM-001, FORM-002]. Laissez vide si vous selectionnez les lignes plus bas."
        ),
        widget=forms.Textarea(
            attrs={
                "rows": 10,
                "placeholder": "[FORM-001, FORM-002]\nFORM-003",
            }
        ),
    )
    target_status = forms.ChoiceField(
        required=False,
        label="Statut a appliquer",
        help_text="Utilise uniquement le bouton de changement de statut.",
        choices=(),
    )
    q1_prerequis_apprenants = forms.CharField(
        required=False,
        label="Q1 Prerequis apprenants",
        help_text="Une valeur unique (ex: 4) ou une liste ordonnee [4,5].",
        widget=forms.TextInput(
            attrs={
                "placeholder": "4 ou [4,5]",
                "autocomplete": "off",
            }
        ),
    )
    q2_interaction_apprenants = forms.CharField(
        required=False,
        label="Q2 Interaction apprenants",
        help_text="Une valeur unique (ex: 4) ou une liste ordonnee [4,5].",
        widget=forms.TextInput(
            attrs={
                "placeholder": "4 ou [4,5]",
                "autocomplete": "off",
            }
        ),
    )
    q3_competences_acquises = forms.CharField(
        required=False,
        label="Q3 Competences acquises",
        help_text="Une valeur unique (ex: 4) ou une liste ordonnee [4,5].",
        widget=forms.TextInput(
            attrs={
                "placeholder": "4 ou [4,5]",
                "autocomplete": "off",
            }
        ),
    )
    q4_gestion_administrative = forms.CharField(
        required=False,
        label="Q4 Gestion administrative",
        help_text="Texte unique ou liste ordonnee entre crochets.",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "RAS ou [RAS, Besoin d'alignement administratif]",
            }
        ),
    )
    q5_gestion_financiere = forms.CharField(
        required=False,
        label="Q5 Gestion financiere",
        help_text="Texte unique ou liste ordonnee entre crochets.",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "RAS ou [RAS, Delais de paiement a revoir]",
            }
        ),
    )
    q6_communication = forms.CharField(
        required=False,
        label="Q6 Communication",
        help_text="Texte unique ou liste ordonnee entre crochets.",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "RAS ou [RAS, Communication a renforcer]",
            }
        ),
    )
    commentaires_values = forms.CharField(
        required=False,
        label="Commentaires",
        help_text="Texte unique ou liste ordonnee entre crochets.",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "RAS ou [RAS, Commentaire detaille]",
            }
        ),
    )
    recommandations_values = forms.CharField(
        required=False,
        label="Recommandations",
        help_text="Texte unique ou liste ordonnee entre crochets.",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "RAS ou [RAS, Recommandation detaillee]",
            }
        ),
    )
    class_codes_values = forms.CharField(
        required=False,
        label="Code classe",
        help_text="Valeur unique ou liste ordonnee entre crochets. Exemple: CLA001 ou [CLA001, CLA002].",
        widget=forms.TextInput(
            attrs={
                "placeholder": "CLA001 ou [CLA001, CLA002]",
                "autocomplete": "off",
            }
        ),
    )
    prestation_codes_values = forms.CharField(
        required=False,
        label="Prestation ID",
        help_text="Valeur unique ou liste ordonnee entre crochets. Exemple: PRE001 ou [PRE001, PRE002].",
        widget=forms.TextInput(
            attrs={
                "placeholder": "PRE001 ou [PRE001, PRE002]",
                "autocomplete": "off",
            }
        ),
    )
    prestataire_values = forms.CharField(
        required=False,
        label="Prestataire",
        help_text="Valeur unique ou liste ordonnee entre crochets.",
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Nom prestataire"}),
    )
    beneficiaire_values = forms.CharField(
        required=False,
        label="Beneficiaire",
        help_text="Valeur unique ou liste ordonnee entre crochets.",
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Nom beneficiaire"}),
    )
    formation_values = forms.CharField(
        required=False,
        label="Titre de formation",
        help_text="Valeur unique ou liste ordonnee entre crochets.",
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Titre de formation"}),
    )
    cohorte_values = forms.CharField(
        required=False,
        label="Cohorte",
        help_text="Valeur unique ou liste ordonnee entre crochets.",
        widget=forms.TextInput(
            attrs={
                "placeholder": "1 ou [1, 2]",
                "autocomplete": "off",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target_status"].choices = [
            ("", "Selectionner un statut"),
            *AppelFormateur.STATUS_CHOICES,
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
        raw_items = self._split_segments(self.cleaned_data.get(field_name, ""))
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

    def clean_q1_prerequis_apprenants(self) -> list[int]:
        return self._clean_score_values("q1_prerequis_apprenants")

    def clean_q2_interaction_apprenants(self) -> list[int]:
        return self._clean_score_values("q2_interaction_apprenants")

    def clean_q3_competences_acquises(self) -> list[int]:
        return self._clean_score_values("q3_competences_acquises")

    def clean_q4_gestion_administrative(self) -> list[str]:
        return self._split_segments(self.cleaned_data.get("q4_gestion_administrative", ""))

    def clean_q5_gestion_financiere(self) -> list[str]:
        return self._split_segments(self.cleaned_data.get("q5_gestion_financiere", ""))

    def clean_q6_communication(self) -> list[str]:
        return self._split_segments(self.cleaned_data.get("q6_communication", ""))

    def clean_commentaires_values(self) -> list[str]:
        return self._split_segments(self.cleaned_data.get("commentaires_values", ""))

    def clean_recommandations_values(self) -> list[str]:
        return self._split_segments(self.cleaned_data.get("recommandations_values", ""))

    def clean_class_codes_values(self) -> list[str]:
        return self._split_segments(self.cleaned_data.get("class_codes_values", ""))

    def clean_prestation_codes_values(self) -> list[str]:
        return self._split_segments(self.cleaned_data.get("prestation_codes_values", ""))

    def clean_prestataire_values(self) -> list[str]:
        return self._split_segments(self.cleaned_data.get("prestataire_values", ""))

    def clean_beneficiaire_values(self) -> list[str]:
        return self._split_segments(self.cleaned_data.get("beneficiaire_values", ""))

    def clean_formation_values(self) -> list[str]:
        return self._split_segments(self.cleaned_data.get("formation_values", ""))

    def clean_cohorte_values(self) -> list[str]:
        return self._split_segments(self.cleaned_data.get("cohorte_values", ""))

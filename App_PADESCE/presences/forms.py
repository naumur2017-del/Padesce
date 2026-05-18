from django import forms

from App_PADESCE.presences.control_utils import get_class_marker_control_types
from App_PADESCE.presences.models import Presence, PresenceControl


class PresenceControlForm(forms.ModelForm):
    class Meta:
        model = PresenceControl
        fields = [
            "inspecteur",
            "theme",
            "date",
            "heure_debut",
            "heure_fin",
            "conformite",
            "type_controle",
            "duree_prevue_formation",
            "formateur1_nom",
            "formateur1_telephone",
            "formateur2_nom",
            "formateur2_telephone",
            "formateur3_nom",
            "formateur3_telephone",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "heure_debut": forms.TimeInput(attrs={"type": "time"}),
            "heure_fin": forms.TimeInput(attrs={"type": "time"}),
            "theme": forms.TextInput(attrs={"placeholder": "Thème de la séance"}),
            "duree_prevue_formation": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, classe=None, **kwargs):
        self.classe = classe
        super().__init__(*args, **kwargs)
        self.fields["conformite"].required = True
        if classe is not None:
            used_qs = PresenceControl.objects.filter(classe=classe)
            if self.instance.pk:
                used_qs = used_qs.exclude(pk=self.instance.pk)
            used = set(used_qs.values_list("type_controle", flat=True))
            used.update(get_class_marker_control_types(classe))
            choices = [
                choice
                for choice in self.fields["type_controle"].choices
                if choice[0] and choice[0] not in used
            ]
            self.fields["type_controle"].choices = choices

    def clean_type_controle(self):
        type_controle = self.cleaned_data["type_controle"]
        if not self.classe:
            return type_controle
        exists = PresenceControl.objects.filter(classe=self.classe, type_controle=type_controle)
        if self.instance.pk:
            exists = exists.exclude(pk=self.instance.pk)
        if exists.exists() or type_controle in get_class_marker_control_types(self.classe):
            raise forms.ValidationError(
                f"{type_controle} existe déjà pour cette classe. Utilisez le contrôle suivant."
            )
        return type_controle


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

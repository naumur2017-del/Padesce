from django import forms

from App_PADESCE.messaging.models import CampagneMessage, Contact, SupportAlarm, SupportMessage


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = [
            "nom_complet",
            "telephone",
            "genre",
            "age",
            "fonction",
            "qualification",
            "nb_annees_experience",
            "ville_residence",
            "prestataire",
            "type_formation",
            "intitule_formation",
            "fenetre",
            "formation",
            "actif",
        ]


class CampagneMessageForm(forms.ModelForm):
    class Meta:
        model = CampagneMessage
        fields = [
            "date_heure",
            "texte",
            "cible_description",
            "message_envoye_json",
            "message_rejete_json",
            "motif_rejet",
        ]
        widgets = {
            "date_heure": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "texte": forms.Textarea(attrs={"rows": 3}),
            "motif_rejet": forms.Textarea(attrs={"rows": 2}),
        }


class SupportMessageForm(forms.ModelForm):
    class Meta:
        model = SupportMessage
        fields = ["recipient", "body"]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 3, "placeholder": "Ecrire votre message..."}),
        }


class SupportAlarmForm(forms.ModelForm):
    class Meta:
        model = SupportAlarm
        fields = ["module", "title", "details"]
        widgets = {
            "module": forms.TextInput(attrs={"placeholder": "Ex: PADESCE, CGA, Dashboard"}),
            "title": forms.TextInput(attrs={"placeholder": "Titre de l'alerte"}),
            "details": forms.Textarea(attrs={"rows": 3, "placeholder": "Detaillez le souci rencontre"}),
        }

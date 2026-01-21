from django import forms

from App_PADESCE.messaging.models import CampagneMessage, Contact


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

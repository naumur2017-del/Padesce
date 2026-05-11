from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.formations.models import (
    Beneficiaire,
    Classe,
    Formation,
    Inspecteur,
    Lieu,
    Prestataire,
    Prestation,
)
from App_PADESCE.presences.models import Presence, PresenceControl


class PresenceControlTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="agent", password="pass")
        self.client.force_login(self.user)
        self.formation = Formation.objects.create(code="FOR001", nom="Transformation")
        self.prestataire = Prestataire.objects.create(code="PREST01", raison_sociale="Prestataire")
        self.beneficiaire = Beneficiaire.objects.create(nom_structure="Beneficiaire")
        self.prestation = Prestation.objects.create(
            code="PRESTA001",
            prestataire=self.prestataire,
            formation=self.formation,
            beneficiaire=self.beneficiaire,
            duree_prevue_heures=24,
        )
        self.lieu = Lieu.objects.create(code="LIE001", nom_lieu="Salle A", ville="Yaounde")
        self.inspecteur = Inspecteur.objects.create(code="INS001", nom_complet="Inspecteur Un")
        self.classe = Classe.objects.create(
            code="CLA001",
            prestation=self.prestation,
            lieu=self.lieu,
            formation=self.formation,
            intitule_formation="Transformation",
            cohorte=1,
        )
        self.apprenant = Apprenant.objects.create(
            code="APP001",
            classe=self.classe,
            formation=self.formation,
            nom_complet="Alice Exemple",
            telephone1="699000001",
        )
        self.second = Apprenant.objects.create(
            code="APP002",
            classe=self.classe,
            formation=self.formation,
            nom_complet="Alice Deux",
            telephone1="699000002",
        )

    def _create_control(self, control_type="C1"):
        return PresenceControl.objects.create(
            classe=self.classe,
            inspecteur=self.inspecteur,
            enqueteur=self.user,
            theme="Theme test",
            date=date(2026, 5, 11),
            heure_debut=time(8, 0),
            heure_fin=time(10, 0),
            conformite="conforme",
            type_controle=control_type,
            duree_prevue_formation=24,
        )

    def test_create_control_seeds_absent_rows_and_control_marker(self):
        response = self.client.post(
            reverse("presence_control_create", args=[self.classe.id]),
            {
                "inspecteur": self.inspecteur.id,
                "theme": "Controle initial",
                "date": "2026-05-11",
                "heure_debut": "08:00",
                "heure_fin": "10:00",
                "conformite": "conforme",
                "type_controle": "C1",
                "duree_prevue_formation": "24",
            },
        )

        self.assertEqual(response.status_code, 302)
        control = PresenceControl.objects.get(type_controle="C1")
        self.assertEqual(control.presences.count(), 2)
        self.assertEqual(set(control.presences.values_list("presence", flat=True)), {"AB"})
        self.apprenant.refresh_from_db()
        self.assertEqual(self.apprenant.c1, "AB")

    def test_exact_code_search_marks_present_with_code_moyen(self):
        control = self._create_control()
        Presence.objects.create(
            controle=control,
            classe=self.classe,
            apprenant=self.apprenant,
            inspecteur=self.inspecteur,
            enqueteur=self.user,
            date=control.date,
            heure_debut=control.heure_debut,
            heure_fin=control.heure_fin,
            presence="AB",
            statut="absent",
        )

        response = self.client.post(
            reverse("presence_control_detail", args=[control.id]),
            {"action": "search", "q": "APP001"},
        )

        self.assertEqual(response.status_code, 302)
        presence = Presence.objects.get(controle=control, apprenant=self.apprenant)
        self.assertEqual(presence.presence, "PR")
        self.assertEqual(presence.statut, "present")
        self.assertEqual(presence.moyen_enregistrement, "C")
        self.assertIsNotNone(presence.heure_presence)
        self.apprenant.refresh_from_db()
        self.assertEqual(self.apprenant.c1, "PR")

    def test_csv_export_uses_expected_presence_filename_and_columns(self):
        control = self._create_control()
        Presence.objects.create(
            controle=control,
            classe=self.classe,
            apprenant=self.apprenant,
            inspecteur=self.inspecteur,
            enqueteur=self.user,
            date=control.date,
            heure_debut=control.heure_debut,
            heure_fin=control.heure_fin,
            presence="AB",
            statut="absent",
        )

        response = self.client.get(reverse("presence_control_export_csv", args=[control.id]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("Presence_CLA001_ENQ1_20260511.csv", response["Content-Disposition"])
        content = response.content.decode("utf-8-sig")
        self.assertIn("Apprenant ID", content)
        self.assertIn("Thème de la séance", content)
        self.assertIn("Alice Exemple", content)

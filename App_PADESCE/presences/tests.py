import json
from datetime import date, time

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
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
from App_PADESCE.presences.forms import PresenceControlForm
from App_PADESCE.presences.views import _exact_code_match, presence_control_create
from App_PADESCE.formations.views import _presence_control_modal_context


class PresenceControlTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="agent", password="pass")
        self.client.force_login(self.user)
        self.request_factory = RequestFactory()
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
        self.inspecteur, _ = Inspecteur.objects.update_or_create(
            code="INS001", defaults={"nom_complet": "Inspecteur Un"}
        )
        self.classe = Classe.objects.create(
            code="CLA001",
            prestation=self.prestation,
            lieu=self.lieu,
            formation=self.formation,
            intitule_formation="Transformation",
            cohorte=1,
        )
        self.apprenant = Apprenant.objects.create(
            code="9GHB",
            numero="APP001",
            classe=self.classe,
            formation=self.formation,
            nom_complet="Alice Exemple",
            telephone1="699000001",
        )
        self.second = Apprenant.objects.create(
            code="8XYZ",
            numero="APP002",
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

    def test_public_user_cannot_create_presence_control(self):
        public_user, _created = get_user_model().objects.update_or_create(
            username="yanava",
            defaults={"is_active": True, "is_staff": False, "is_superuser": False},
        )
        public_user.set_password("pass")
        public_user.save(update_fields=["password", "is_active", "is_staff", "is_superuser"])
        request = self.request_factory.post(
            reverse("presence_control_create", args=[self.classe.id]),
            {
                "inspecteur": self.inspecteur.id,
                "theme": "Controle public",
                "date": "2026-05-11",
                "heure_debut": "08:00",
                "heure_fin": "10:00",
                "conformite": "conforme",
                "type_controle": "C1",
                "duree_prevue_formation": "24",
            },
        )
        request.user = public_user

        with self.assertRaises(PermissionDenied):
            presence_control_create(request, self.classe.id)
        self.assertFalse(PresenceControl.objects.filter(type_controle="C1").exists())

    def test_class_detail_shows_existing_marker_controls_and_skips_next_type(self):
        self.apprenant.c1 = "PR"
        self.second.c1 = "AB"
        self.apprenant.save(update_fields=["c1", "updated_at"])
        self.second.save(update_fields=["c1", "updated_at"])

        request = self.request_factory.get(reverse("class_detail", args=[self.classe.id]))
        request.user = self.user
        context = _presence_control_modal_context(self.classe, request)

        self.assertEqual(context["presence_next_type"], "C2")
        self.assertEqual(len(context["presence_existing_controls"]), 1)
        control = context["presence_existing_controls"][0]
        self.assertEqual(control.type_controle, "C1")
        self.assertEqual(control.theme, "Données de présence existantes")
        self.assertEqual(control.presents, 1)
        self.assertEqual(control.total, 2)

    def test_existing_marker_control_type_cannot_be_created_again(self):
        self.apprenant.c1 = "PR"
        self.apprenant.save(update_fields=["c1", "updated_at"])

        form = PresenceControlForm(
            {
                "inspecteur": self.inspecteur.id,
                "theme": "Controle duplicate",
                "date": "2026-05-11",
                "heure_debut": "08:00",
                "heure_fin": "10:00",
                "conformite": "conforme",
                "type_controle": "C1",
                "duree_prevue_formation": "24",
            },
            classe=self.classe,
        )

        self.assertFalse(form.is_valid())
        self.assertFalse(PresenceControl.objects.filter(type_controle="C1").exists())

    def test_pair_existing_marker_control_creates_clickable_control(self):
        self.apprenant.c1 = "PR"
        self.second.c1 = "AB"
        self.apprenant.save(update_fields=["c1", "updated_at"])
        self.second.save(update_fields=["c1", "updated_at"])

        response = self.client.post(
            reverse("presence_control_pair_existing", args=[self.classe.id, "C1"])
        )

        control = PresenceControl.objects.get(classe=self.classe, type_controle="C1")
        self.assertRedirects(
            response,
            reverse("presence_control_detail", args=[control.id]),
            fetch_redirect_response=False,
        )
        self.assertEqual(control.theme, "Données de présence existantes")
        first_presence = Presence.objects.get(controle=control, apprenant=self.apprenant)
        second_presence = Presence.objects.get(controle=control, apprenant=self.second)
        self.assertEqual(first_presence.presence, "PR")
        self.assertEqual(first_presence.statut, "present")
        self.assertEqual(second_presence.presence, "AB")
        self.assertEqual(second_presence.statut, "absent")

    def test_create_control_includes_inactive_registered_learners(self):
        self.second.actif = False
        self.second.save(update_fields=["actif", "updated_at"])

        response = self.client.post(
            reverse("presence_control_create", args=[self.classe.id]),
            {
                "inspecteur": self.inspecteur.id,
                "theme": "Controle tous inscrits",
                "date": "2026-05-11",
                "heure_debut": "08:00",
                "heure_fin": "10:00",
                "conformite": "conforme",
                "type_controle": "C1",
                "duree_prevue_formation": "24",
                "presence_marks_json": json.dumps(
                    {str(self.second.id): {"moyen": "P", "heure": "08:30"}}
                ),
            },
        )

        self.assertEqual(response.status_code, 302)
        control = PresenceControl.objects.get(type_controle="C1")
        self.assertEqual(control.presences.count(), 2)
        second_presence = Presence.objects.get(controle=control, apprenant=self.second)
        self.assertEqual(second_presence.presence, "PR")
        self.assertEqual(second_presence.heure_presence, time(8, 30))

    def test_create_control_applies_modal_presence_marks(self):
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
                "presence_marks_json": json.dumps(
                    {
                        str(self.apprenant.id): {"moyen": "C", "heure": "08:12"},
                        str(self.second.id): {"moyen": "P", "heure": "08:20"},
                    }
                ),
            },
        )

        self.assertEqual(response.status_code, 302)
        control = PresenceControl.objects.get(type_controle="C1")
        first_presence = Presence.objects.get(controle=control, apprenant=self.apprenant)
        second_presence = Presence.objects.get(controle=control, apprenant=self.second)
        self.assertEqual(first_presence.presence, "PR")
        self.assertEqual(first_presence.moyen_enregistrement, "C")
        self.assertEqual(first_presence.heure_presence, time(8, 12))
        self.assertEqual(second_presence.presence, "PR")
        self.assertEqual(second_presence.moyen_enregistrement, "P")
        self.assertEqual(second_presence.heure_presence, time(8, 20))

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
            {"action": "search", "q": "9GHB"},
        )

        self.assertEqual(response.status_code, 302)
        presence = Presence.objects.get(controle=control, apprenant=self.apprenant)
        self.assertEqual(presence.presence, "PR")
        self.assertEqual(presence.statut, "present")
        self.assertEqual(presence.moyen_enregistrement, "C")
        self.assertIsNotNone(presence.heure_presence)
        self.apprenant.refresh_from_db()
        self.assertEqual(self.apprenant.c1, "PR")

    def test_internal_number_search_does_not_auto_mark_as_code(self):
        control = self._create_control()

        self.assertIsNone(_exact_code_match(control, "APP001"))
        self.assertEqual(_exact_code_match(control, "9GHB"), self.apprenant)

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

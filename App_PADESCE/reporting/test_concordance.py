import csv
import io

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook

from App_PADESCE.appels.models import AppelPasFormeII
from App_PADESCE.reporting import views
from App_PADESCE.reporting.models import (
    ConcordanceRecord,
    PendingLearnerContactImport,
    PendingLearnerContactRecord,
)


def _postgres_jsonb_order(payload):
    """Approximate PostgreSQL JSONB's deterministic object-key ordering."""
    return dict(sorted(payload.items(), key=lambda item: (len(item[0]), item[0])))


def _feuil2_payload():
    return {
        "NBRE": "1",
        "PRESTA ID": "PRESTA001",
        "PRESTATAIRE": "CFP FAMEAC",
        "BENEFICIAIRE": "COOP CA WALDE BEKA MARDOCK",
        "FENETRE": "3",
        "NBRE PERSONNES FORMEES SELON FICHE DE PRESENCE RAPPORT PRESTATAIRE - T": "30",
        "NBRE PERSONNES FORMEES SELON FICHE DE PRESENCE RAPPORT PRESTATAIRE - H": "20",
        "NBRE PERSONNES FORMEES SELON FICHE DE PRESENCE RAPPORT PRESTATAIRE - F": "10",
        "TAUX_CONCORDANCE": "0.7667",
        "NOMBRE FORME TOTAL AVEC TAUX DE CONCORDANCE - H": "17",
        "NOMBRE FORME TOTAL AVEC TAUX DE CONCORDANCE - F": "6",
        "NOMBRE FORME TOTAL AVEC TAUX DE CONCORDANCE - T": "23",
    }


class ConcordancePostgresParityTests(SimpleTestCase):
    def test_feuil2_display_order_does_not_depend_on_json_key_order(self):
        payload = _postgres_jsonb_order(_feuil2_payload())
        record = ConcordanceRecord(payload=payload)

        headers, is_feuil2_layout = views._concordance_display_headers([record])
        displayed_values = [payload.get(header, "") for header in headers]

        self.assertTrue(is_feuil2_layout)
        self.assertEqual(headers, list(views.CONCORDANCE_FEUIL2_DISPLAY_HEADERS))
        self.assertEqual(
            displayed_values[:5],
            ["1", "PRESTA001", "CFP FAMEAC", "COOP CA WALDE BEKA MARDOCK", "3"],
        )
        self.assertEqual(displayed_values[-3:], ["17", "6", "23"])

    def test_concordance_summary_reads_named_columns_from_reordered_json(self):
        record = ConcordanceRecord(fenetre="3", payload=_postgres_jsonb_order(_feuil2_payload()))

        summary = views._concordance_window_summary(
            [record], list(views.CONCORDANCE_FEUIL2_DISPLAY_HEADERS)
        )

        self.assertEqual(
            summary,
            [
                {"window": "Fenêtre 2", "men": 0, "women": 0, "total": 0},
                {"window": "Fenêtre 3", "men": 17, "women": 6, "total": 23},
                {"window": "Total", "men": 17, "women": 6, "total": 23},
            ],
        )

    def test_pending_contact_csv_preserves_source_column_order(self):
        uploaded_file = SimpleUploadedFile(
            "contacts.csv",
            "PRESTA ID;Apprenant;Téléphone\nPRESTA001;Alice;690000001\n".encode(),
            content_type="text/csv",
        )

        headers, payloads = views._pending_contact_rows_from_file(uploaded_file)

        self.assertEqual(headers, ["PRESTA ID", "Apprenant", "Téléphone"])
        self.assertEqual(
            payloads,
            [
                {
                    "PRESTA ID": "PRESTA001",
                    "Apprenant": "Alice",
                    "Téléphone": "690000001",
                }
            ],
        )

    def test_pending_contact_xlsx_uses_first_sheet(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["PRESTA ID", "Apprenant", "Téléphone"])
        worksheet.append(["PRESTA002", "Bob", "690000002"])
        content = io.BytesIO()
        workbook.save(content)
        uploaded_file = SimpleUploadedFile("contacts.xlsx", content.getvalue())

        headers, payloads = views._pending_contact_rows_from_file(uploaded_file)

        self.assertEqual(headers, ["PRESTA ID", "Apprenant", "Téléphone"])
        self.assertEqual(payloads[0]["Téléphone"], "690000002")


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class ConcordanceCampaignPageTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="concordance-tester", password="test-pass-123"
        )
        manager_group, _ = Group.objects.get_or_create(name="manager_padesce")
        user.groups.add(manager_group)
        self.client.force_login(user)

    def test_pas_forme_ii_cards_keep_expected_production_totals(self):
        distributions = [(5, 2), (4, 1), (4, 2), (4, 1)]
        calls = []
        sequence = 0
        for prestation_index, (men, women) in enumerate(distributions, start=1):
            for genre in ("H",) * men + ("F",) * women:
                sequence += 1
                calls.append(
                    AppelPasFormeII(
                        reference_code=f"PFII-{sequence:03d}",
                        prestation_id=f"PRESTA{prestation_index:03d}",
                        nom=f"Personne {sequence}",
                        prestataire=f"Prestataire {prestation_index}",
                        beneficiaire=f"Bénéficiaire {prestation_index}",
                        genre=genre,
                        fenetre="3",
                        total_seances=1,
                        nombre_seances_declare=1,
                        formulaire_rempli_at=timezone.now(),
                    )
                )
        AppelPasFormeII.objects.bulk_create(calls)

        rows, summary = views._build_pas_forme_ii_campaign()

        self.assertEqual(len(rows), 4)
        self.assertEqual(
            summary,
            {
                "prestations": 4,
                "appels_effectues": 23,
                "fenetre_2": 0,
                "fenetre_3": 23,
                "hommes": 17,
                "femmes": 6,
            },
        )

    def test_campaign_detail_reports_declared_and_planned_sessions_with_status(self):
        calls = [
            AppelPasFormeII(
                reference_code="PFII-FORME",
                prestation_id="PRESTA-SEANCES",
                nom="Formé",
                total_seances=4,
                nombre_seances_declare=3,
                formulaire_rempli_at=timezone.now(),
            ),
            AppelPasFormeII(
                reference_code="PFII-EXCESS",
                prestation_id="PRESTA-SEANCES",
                nom="Excès",
                total_seances=4,
                nombre_seances_declare=5,
                formulaire_rempli_at=timezone.now(),
            ),
            AppelPasFormeII(
                reference_code="PFII-LOW",
                prestation_id="PRESTA-SEANCES",
                nom="Insuffisant",
                total_seances=4,
                nombre_seances_declare=2,
                formulaire_rempli_at=timezone.now(),
            ),
            AppelPasFormeII(
                reference_code="PFII-INDETERMINE",
                prestation_id="PRESTA-SEANCES",
                nom="Pas formé du tout",
                total_seances=4,
                nombre_seances_declare=0,
                pas_forme_du_tout=True,
                formulaire_rempli_at=timezone.now(),
            ),
        ]
        AppelPasFormeII.objects.bulk_create(calls)

        rows, _ = views._build_pas_forme_ii_campaign()
        apprenants = {item["code"]: item for item in rows[0]["apprenants"]}

        self.assertEqual(apprenants["PFII-FORME"]["seances_declarees"], 3)
        self.assertEqual(apprenants["PFII-FORME"]["seances_prevues"], 4)
        self.assertEqual(apprenants["PFII-FORME"]["taux_presence"], 75)
        self.assertEqual(apprenants["PFII-FORME"]["statut_formation"], "Formé")
        self.assertEqual(apprenants["PFII-EXCESS"]["statut_formation"], "Pas formé")
        self.assertEqual(apprenants["PFII-LOW"]["statut_formation"], "Pas formé")
        self.assertEqual(
            apprenants["PFII-INDETERMINE"]["statut_formation"],
            "Indéterminé",
        )
        self.assertTrue(apprenants["PFII-INDETERMINE"]["pas_forme_du_tout"])

    def test_custom_formation_rate_interval_recalculates_all_dependent_values(self):
        calls = []
        for index, genre in enumerate(("H", "H", "F", "F"), start=1):
            calls.append(AppelPasFormeII(
                reference_code=f"PFII-CUSTOM-50-{index}",
                prestation_id="PRESTA-CUSTOM-RATE",
                nom=f"Taux 50 #{index}",
                genre=genre,
                fenetre="2",
                total_seances=4,
                nombre_seances_declare=2,
                formulaire_rempli_at=timezone.now(),
            ))
        calls.append(AppelPasFormeII(
            reference_code="PFII-CUSTOM-75",
            prestation_id="PRESTA-CUSTOM-RATE",
            nom="Taux 75",
            genre="F",
            fenetre="2",
            total_seances=4,
            nombre_seances_declare=3,
            formulaire_rempli_at=timezone.now(),
        ))
        AppelPasFormeII.objects.bulk_create(calls)

        default_response = self.client.get(reverse("concordance_campaigns"))
        default_row = default_response.context["not_formed_campaign_rows"][0]
        self.assertEqual(default_row["formes_total"], 1)
        self.assertEqual(default_row["pas_formes_total"], 4)
        self.assertEqual(default_row["decision"], "_")

        params = {
            "tab": "campaigns",
            "formation_rate_min": "50",
            "formation_rate_max": "50",
        }
        response = self.client.get(reverse("concordance_campaigns"), params)

        self.assertEqual(response.status_code, 200)
        interval = response.context["formation_rate_interval"]
        self.assertEqual((interval["minimum"], interval["maximum"]), (50, 50))
        row = response.context["not_formed_campaign_rows"][0]
        statuses = {item["code"]: item["statut_formation"] for item in row["apprenants"]}
        self.assertEqual(row["formes_total"], 4)
        self.assertEqual(row["formes_hommes"], 2)
        self.assertEqual(row["formes_femmes"], 2)
        self.assertEqual(row["formes_fenetre_2"], 4)
        self.assertEqual(row["pas_formes_total"], 1)
        self.assertEqual(row["taux_formation"], 80)
        self.assertEqual(row["decision"], 5)
        self.assertEqual(row["decision_hommes"], 2)
        self.assertEqual(row["decision_femmes"], 3)
        self.assertEqual(statuses["PFII-CUSTOM-50-1"], "Formé")
        self.assertEqual(statuses["PFII-CUSTOM-75"], "Pas formé")
        self.assertEqual(response.context["campaign_formed_people_summary"]["total"], 5)
        self.assertContains(response, 'value="50"')
        self.assertContains(
            response, 'id="formation-rate-min-slider" type="range"'
        )
        self.assertContains(
            response, 'id="formation-rate-max-slider" type="range"'
        )
        self.assertContains(response, 'step="5"', count=2)

        export_response = self.client.get(reverse("concordance_export_ra_csv"), params)
        exported = list(csv.reader(io.StringIO(export_response.content.decode("utf-8-sig"))))
        exported_row = dict(zip(exported[0], exported[1]))
        self.assertEqual(exported_row["Formés total"], "4")
        self.assertEqual(exported_row["Pas formés total"], "1")
        self.assertEqual(exported_row["Décision"], "5")

    def test_invalid_formation_rate_interval_falls_back_to_safe_defaults(self):
        response = self.client.get(reverse("concordance_campaigns"), {
            "tab": "campaigns",
            "formation_rate_min": "130",
            "formation_rate_max": "20",
        })

        interval = response.context["formation_rate_interval"]
        self.assertEqual(
            (interval["minimum"], interval["maximum"]),
            (views.DEFAULT_FORMATION_RATE_MIN, views.DEFAULT_FORMATION_RATE_MAX),
        )
        self.assertTrue(interval["error"])
        self.assertContains(response, "Les valeurs par défaut 75 % – 120 % ont été appliquées.")

    def test_campaign_gender_summary_is_built_from_decision_hf_columns(self):
        # PRESTA-DEC2 (fenêtre 2): 4/4 formés (taux 100% > 75) -> decision = total = 4,
        # reparti a parts egales (2 hommes appeles, 2 femmes appelees).
        AppelPasFormeII.objects.bulk_create([
            AppelPasFormeII(reference_code="PFII-DEC2-H1", prestation_id="PRESTA-DEC2", nom="H1", genre="H", fenetre="2", total_seances=10, nombre_seances_declare=9, formulaire_rempli_at=timezone.now()),
            AppelPasFormeII(reference_code="PFII-DEC2-H2", prestation_id="PRESTA-DEC2", nom="H2", genre="H", fenetre="2", total_seances=10, nombre_seances_declare=8, formulaire_rempli_at=timezone.now()),
            AppelPasFormeII(reference_code="PFII-DEC2-F1", prestation_id="PRESTA-DEC2", nom="F1", genre="F", fenetre="2", total_seances=10, nombre_seances_declare=9, formulaire_rempli_at=timezone.now()),
            AppelPasFormeII(reference_code="PFII-DEC2-F2", prestation_id="PRESTA-DEC2", nom="F2", genre="F", fenetre="2", total_seances=10, nombre_seances_declare=8, formulaire_rempli_at=timezone.now()),
        ])
        # PRESTA-DEC3 (fenêtre 3): 4/5 formés (taux 80% > 75) -> decision = total = 5,
        # reparti au prorata des 4 hommes / 1 femme appeles (4 et 1).
        AppelPasFormeII.objects.bulk_create([
            AppelPasFormeII(reference_code="PFII-DEC3-H1", prestation_id="PRESTA-DEC3", nom="H1", genre="H", fenetre="3", total_seances=10, nombre_seances_declare=9, formulaire_rempli_at=timezone.now()),
            AppelPasFormeII(reference_code="PFII-DEC3-H2", prestation_id="PRESTA-DEC3", nom="H2", genre="H", fenetre="3", total_seances=10, nombre_seances_declare=8, formulaire_rempli_at=timezone.now()),
            AppelPasFormeII(reference_code="PFII-DEC3-H3", prestation_id="PRESTA-DEC3", nom="H3", genre="H", fenetre="3", total_seances=10, nombre_seances_declare=9, formulaire_rempli_at=timezone.now()),
            AppelPasFormeII(reference_code="PFII-DEC3-H4-NON", prestation_id="PRESTA-DEC3", nom="H4 pas forme", genre="H", fenetre="3", total_seances=10, nombre_seances_declare=2, formulaire_rempli_at=timezone.now()),
            AppelPasFormeII(reference_code="PFII-DEC3-F1", prestation_id="PRESTA-DEC3", nom="F1", genre="F", fenetre="3", total_seances=10, nombre_seances_declare=9, formulaire_rempli_at=timezone.now()),
        ])

        response = self.client.get(reverse("concordance_campaigns"))

        self.assertEqual(
            response.context["campaign_gender_summary"],
            [
                {"window": "Fenêtre 2", "men": 2, "women": 2, "total": 4},
                {"window": "Fenêtre 3", "men": 4, "women": 1, "total": 5},
                {"window": "Total", "men": 6, "women": 3, "total": 9},
            ],
        )
        self.assertEqual(
            response.context["campaign_formed_people_summary"],
            {"total": 9, "fenetre_2": 4, "fenetre_3": 5, "hommes": 6, "femmes": 3},
        )
        self.assertEqual(
            response.context["synthesis_gender_summary"],
            response.context["campaign_gender_summary"],
        )

    def test_synthesis_gender_summary_combines_concordance_and_calls(self):
        ConcordanceRecord.objects.create(fenetre="3", payload=_feuil2_payload())
        AppelPasFormeII.objects.create(
            reference_code="PFII-SYNTHESIS-GENDER",
            prestation_id="PRESTA-SUMMARY",
            nom="Apprenant formé",
            genre="F",
            fenetre="2",
            total_seances=4,
            nombre_seances_declare=3,
            formulaire_rempli_at=timezone.now(),
        )

        response = self.client.get(reverse("concordance_campaigns"))

        self.assertEqual(
            response.context["synthesis_gender_summary"],
            [
                {"window": "Fenêtre 2", "men": 0, "women": 1, "total": 1},
                {"window": "Fenêtre 3", "men": 17, "women": 6, "total": 23},
                {"window": "Total", "men": 17, "women": 7, "total": 24},
            ],
        )

    def test_campaign_detail_exposes_phone_and_structure_membership(self):
        AppelPasFormeII.objects.create(
            reference_code="PFII-CONTACT-001",
            prestation_id="PRESTA-CONTACT",
            nom="Apprenant contact",
            telephone="690000001",
            membre_structure="OUI",
            total_seances=12,
            nombre_seances_declare=10,
            formulaire_rempli_at=timezone.now(),
        )

        rows, _ = views._build_pas_forme_ii_campaign()
        apprenant = rows[0]["apprenants"][0]

        self.assertEqual(apprenant["telephone"], "690000001")
        self.assertEqual(apprenant["membre_structure"], "OUI")

    def test_campaign_rows_include_formed_people_breakdown_columns(self):
        AppelPasFormeII.objects.bulk_create([
            AppelPasFormeII(reference_code="PFII-COLUMNS-H", prestation_id="PRESTA-COLUMNS", nom="Homme", genre="H", fenetre="2", total_seances=4, nombre_seances_declare=3, formulaire_rempli_at=timezone.now()),
            AppelPasFormeII(reference_code="PFII-COLUMNS-F", prestation_id="PRESTA-COLUMNS", nom="Femme", genre="F", fenetre="2", total_seances=4, nombre_seances_declare=4, formulaire_rempli_at=timezone.now()),
            AppelPasFormeII(reference_code="PFII-COLUMNS-NON", prestation_id="PRESTA-COLUMNS", nom="Non formé", genre="F", fenetre="2", total_seances=4, nombre_seances_declare=2, formulaire_rempli_at=timezone.now()),
            AppelPasFormeII(reference_code="PFII-COLUMNS-INDETERMINE", prestation_id="PRESTA-COLUMNS", nom="Indéterminé", genre="H", fenetre="2", total_seances=4, nombre_seances_declare=4, pas_forme_du_tout=True, formulaire_rempli_at=timezone.now()),
        ])

        rows, _ = views._build_pas_forme_ii_campaign()

        self.assertEqual(rows[0]["formes_total"], 2)
        self.assertEqual(rows[0]["formes_hommes"], 1)
        self.assertEqual(rows[0]["formes_femmes"], 1)
        self.assertEqual(rows[0]["formes_fenetre_2"], 2)
        self.assertEqual(rows[0]["formes_fenetre_3"], 0)

    def test_campaign_called_counts_require_completed_form_and_sessions(self):
        AppelPasFormeII.objects.bulk_create([
            AppelPasFormeII(reference_code="PFII-CALLED-VALID", prestation_id="PRESTA-CALLED", nom="Valide", genre="H", fenetre="2", total_seances=4, nombre_seances_declare=3, formulaire_rempli_at=timezone.now()),
            AppelPasFormeII(reference_code="PFII-CALLED-NO-SESSIONS", prestation_id="PRESTA-CALLED", nom="Sans séances", genre="F", fenetre="2", total_seances=4, formulaire_rempli_at=timezone.now()),
            AppelPasFormeII(reference_code="PFII-CALLED-NO-FORM", prestation_id="PRESTA-CALLED", nom="Sans formulaire", genre="F", fenetre="2", total_seances=4, nombre_seances_declare=2, status="appel_tente"),
        ])

        rows, _ = views._build_pas_forme_ii_campaign()

        self.assertEqual(rows[0]["appeles"], 1)
        self.assertEqual(rows[0]["hommes"], 1)
        self.assertEqual(rows[0]["femmes"], 0)

    @override_settings(
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
    )
    def test_page_renders_ordered_concordance_and_campaign_cards(self):
        ConcordanceRecord.objects.create(
            fenetre="3", payload=_postgres_jsonb_order(_feuil2_payload())
        )

        response = self.client.get(reverse("concordance_campaigns"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Prestations analysées")
        self.assertContains(response, "Total des appels effectués")
        self.assertContains(response, "Personnes appelées — fenêtre 3")
        self.assertContains(response, "Réconciliation par prestation")
        self.assertContains(response, "Méthode")
        self.assertEqual(response.context["synthesis_reconciliation_rows"][0]["methode"], "RC")
        self.assertEqual(
            response.context["headers"],
            list(views.CONCORDANCE_FEUIL2_DISPLAY_HEADERS),
        )
        self.assertEqual(
            response.context["concordance_rows"][0]["values"][:5],
            ["1", "PRESTA001", "CFP FAMEAC", "COOP CA WALDE BEKA MARDOCK", "3"],
        )

    @override_settings(
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
    )
    def test_synthesis_collects_rc_ra_and_r_rows_from_their_tabs(self):
        ConcordanceRecord.objects.create(
            fenetre="3",
            payload=_postgres_jsonb_order(_feuil2_payload()),
        )
        AppelPasFormeII.objects.create(
            reference_code="PFII-SYNTHESIS-001",
            prestation_id="PRESTA002",
            nom="Apprenant RA",
            prestataire="Prestataire RA",
            beneficiaire="Bénéficiaire RA",
            genre="F",
            fenetre="3",
            is_active=True,
            formulaire_rempli_at=timezone.now(),
        )
        pending_import = PendingLearnerContactImport.objects.create(
            source_filename="contacts.csv",
            headers=["PRESTA ID", "Prestataire", "Bénéficiaire", "Fenêtre", "Apprenant"],
        )
        PendingLearnerContactRecord.objects.create(
            import_batch=pending_import,
            row_number=1,
            payload={
                "PRESTA ID": "PRESTA003",
                "Prestataire": "Prestataire R",
                "Bénéficiaire": "Bénéficiaire R",
                "Fenêtre": "3",
                "Apprenant": "Apprenant R",
            },
        )

        response = self.client.get(reverse("concordance_campaigns"))

        rows = response.context["synthesis_reconciliation_rows"]
        rows_by_method = {row["methode"]: row for row in rows}
        self.assertEqual(set(rows_by_method), {"RC", "RA", "R"})
        self.assertEqual(rows_by_method["RC"]["presta_id"], "PRESTA001")
        self.assertEqual(rows_by_method["RA"]["presta_id"], "PRESTA002")
        self.assertEqual(rows_by_method["R"]["presta_id"], "PRESTA003")
        self.assertEqual(rows_by_method["R"]["appeles"], 0)
        self.assertEqual(rows_by_method["R"]["total"], 1)

    @override_settings(
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
    )
    def test_synthesis_keeps_unattempted_ra_and_flexible_r_source_headers(self):
        ConcordanceRecord.objects.create(
            fenetre="3",
            payload=_postgres_jsonb_order(_feuil2_payload()),
        )
        AppelPasFormeII.objects.create(
            reference_code="PFII-WAITING-001",
            prestation_id="PRESTA004",
            nom="Apprenant en attente",
            prestataire="Prestataire RA en attente",
            beneficiaire="Bénéficiaire RA en attente",
            genre="H",
            fenetre="2",
            is_active=True,
            status="en_attente",
        )
        pending_import = PendingLearnerContactImport.objects.create(
            source_filename="contacts.xlsx",
            headers=["Prestation ID", "Prestataires", "Bénéficiaires", "Fenetre appel"],
        )
        PendingLearnerContactRecord.objects.create(
            import_batch=pending_import,
            row_number=1,
            payload={
                "Prestation ID": "PRESTA005",
                "Prestataires": "Prestataire R",
                "Bénéficiaires": "Bénéficiaire R",
                "Fenetre appel": "2",
            },
        )

        response = self.client.get(reverse("concordance_campaigns"))
        rows = response.context["synthesis_reconciliation_rows"]
        rows_by_key = {(row["methode"], row["presta_id"]): row for row in rows}

        self.assertEqual(rows_by_key[("RA", "PRESTA004")]["appeles"], 0)
        self.assertEqual(rows_by_key[("RA", "PRESTA004")]["total"], 1)
        self.assertEqual(rows_by_key[("R", "PRESTA005")]["prestataire"], "Prestataire R")
        self.assertEqual(rows_by_key[("R", "PRESTA005")]["beneficiaire"], "Bénéficiaire R")
        self.assertEqual(rows_by_key[("R", "PRESTA005")]["fenetre"], "2")


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class PendingLearnerContactImportTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="pending-contact-tester",
            password="test-pass-123",
            is_staff=True,
            is_superuser=True,
        )
        manager_group, _ = Group.objects.get_or_create(name="manager_padesce")
        user.groups.add(manager_group)
        self.client.force_login(user)

    @staticmethod
    def _csv_file(name, rows):
        return SimpleUploadedFile(name, rows.encode(), content_type="text/csv")

    def test_import_replaces_previous_contact_file_atomically(self):
        self.client.post(
            reverse("concordance_campaigns"),
            {
                "action": "pending_contacts_upload",
                "fichier": self._csv_file(
                    "premier.csv",
                    "PRESTA ID;Apprenant;Téléphone\nPRESTA001;Alice;690000001\n",
                ),
            },
        )

        response = self.client.post(
            reverse("concordance_campaigns"),
            {
                "action": "pending_contacts_upload",
                "fichier": self._csv_file(
                    "second.csv",
                    "Code;Nom;Contact\nPRESTA002;Bob;690000002\nPRESTA003;Carole;690000003\n",
                ),
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('concordance_campaigns')}?tab=pending-contacts",
        )
        self.assertEqual(PendingLearnerContactImport.objects.count(), 1)
        current_import = PendingLearnerContactImport.objects.get()
        self.assertEqual(current_import.source_filename, "second.csv")
        self.assertEqual(current_import.headers, ["Code", "Nom", "Contact"])
        self.assertEqual(current_import.records.count(), 2)

    def test_invalid_import_keeps_current_contacts(self):
        self.client.post(
            reverse("concordance_campaigns"),
            {
                "action": "pending_contacts_upload",
                "fichier": self._csv_file(
                    "contacts.csv",
                    "Code;Nom\nPRESTA001;Alice\n",
                ),
            },
        )
        current_import = PendingLearnerContactImport.objects.get()

        self.client.post(
            reverse("concordance_campaigns"),
            {
                "action": "pending_contacts_upload",
                "fichier": SimpleUploadedFile("invalide.txt", b"contenu invalide"),
            },
        )

        self.assertEqual(PendingLearnerContactImport.objects.count(), 1)
        self.assertTrue(PendingLearnerContactImport.objects.filter(id=current_import.id).exists())
        self.assertEqual(current_import.records.count(), 1)

    def test_page_renders_fourth_tab_and_imported_table(self):
        self.client.post(
            reverse("concordance_campaigns"),
            {
                "action": "pending_contacts_upload",
                "fichier": self._csv_file(
                    "contacts.csv",
                    "PRESTA ID;Apprenant;Téléphone\nPRESTA001;Alice;690000001\n",
                ),
            },
        )

        response = self.client.get(reverse("concordance_campaigns"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Récupération des contacts des apprenants des prestations en attente",
        )
        self.assertContains(response, "contacts.csv")
        self.assertContains(response, "690000001")
        self.assertEqual(response.context["pending_contact_count"], 1)

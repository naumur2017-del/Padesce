from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from App_PADESCE.appels.models import AppelPasFormeII
from App_PADESCE.reporting import views
from App_PADESCE.reporting.models import ConcordanceRecord


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

        summary = views._concordance_window_summary([record])

        self.assertEqual(
            summary,
            [
                {"window": "Fenêtre 2", "men": 0, "women": 0, "total": 0},
                {"window": "Fenêtre 3", "men": 17, "women": 6, "total": 23},
                {"window": "Total", "men": 17, "women": 6, "total": 23},
            ],
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
                "fenetre_2": 0,
                "fenetre_3": 23,
                "hommes": 17,
                "femmes": 6,
            },
        )

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
        self.assertContains(response, "Personnes appelées — fenêtre 3")
        self.assertEqual(
            response.context["headers"],
            list(views.CONCORDANCE_FEUIL2_DISPLAY_HEADERS),
        )
        self.assertEqual(
            response.context["concordance_rows"][0]["values"][:5],
            ["1", "PRESTA001", "CFP FAMEAC", "COOP CA WALDE BEKA MARDOCK", "3"],
        )

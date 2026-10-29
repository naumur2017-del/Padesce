import io
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import QuestionnaireForm
from .imports import import_records, records_from_file
from .models import CallAttempt, Enterprise, Recording
from .schema import QUESTIONS


def audio(content=b"\x1aE\xdf\xa3" + b"test recording bytes" * 5):
    return SimpleUploadedFile("call.webm", content, content_type="audio/webm")


def complete_answers():
    # Support and maturity remain applicable to a first-time applicant without funding needs.
    return {
        "q1_name": "Entreprise Exemple",
        "q2_respondent": "Marie Exemple",
        "q3_role": "Promotrice",
        "q4_phone": "699000001",
        "q5_city": "Douala",
        "q6_year": 2024,
        "q7_legal": "SARL",
        "q8_sector": "Agriculture",
        "q9_activity": "Production",
        "q10_products": "Légumes",
        "q11_none": True,
        "q12_need": "Non",
        "q17_aware": "Non",
        "q20_applied": "Non",
        "q27_supported": "Non",
        "q27_support_desired": ["Mentorat"],
        "q28_stage": "Premières ventes",
        "q29_sales": "Non",
        "q30_contracts": "Non",
        "q31_goals": "Développer la production",
        "q32_impact": "Emplois",
        "q33_barriers": "Garanties",
        "q34_type": "Subvention",
        "q35_support": ["Gestion"],
        "declaration_name": "Marie Exemple",
        "declaration_confirmed": True,
    }


@override_settings(
    PADESCE_ACTIVITY_TRACKING_ENABLED=False,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class FAWorkflowTests(TestCase):
    def setUp(self):
        self.agent = get_user_model().objects.create_user(username="fa-agent", password="test-pass")
        self.other = get_user_model().objects.create_user(username="fa-other", password="test-pass")
        self.enterprise = Enterprise.objects.create(
            reference="FA-001",
            name="Entreprise Exemple",
            phone="699000001",
            city="Douala",
            sector="Agriculture",
        )
        self.client.force_login(self.agent)

    def start_call(self):
        result = self.client.post(
            reverse("fa_start", args=[self.enterprise.pk]),
            {"client_token": str(uuid.uuid4()), "audio": audio()},
        )
        self.assertEqual(result.status_code, 200, result.content)
        return result.json()

    def upload_final(self, attempt, sequence=1):
        result = self.client.post(
            attempt["upload_url"],
            {"audio": audio(), "sequence": sequence, "full": "1", "final": "1"},
        )
        self.assertEqual(result.status_code, 200, result.content)
        return result.json()

    def test_start_needs_real_recording_and_authentication(self):
        result = self.client.post(
            reverse("fa_start", args=[self.enterprise.pk]),
            {"client_token": str(uuid.uuid4()), "recording_ready": "true"},
        )
        self.assertEqual(result.status_code, 400)
        self.assertFalse(CallAttempt.objects.exists())
        self.assertEqual(
            self.client.post(
                reverse("fa_start", args=[self.enterprise.pk]),
                {
                    "client_token": str(uuid.uuid4()),
                    "audio": audio(b"<script>fake recording</script>" * 3),
                },
            ).status_code,
            400,
        )
        self.client.logout()
        self.assertEqual(self.client.get(reverse("fa_index")).status_code, 302)

    def test_start_is_idempotent_and_preserves_first_recording(self):
        token = str(uuid.uuid4())
        data = {"client_token": token, "audio": audio()}
        result = self.client.post(reverse("fa_start", args=[self.enterprise.pk]), data)
        self.assertEqual(result.status_code, 200)
        repeated = self.client.post(
            reverse("fa_start", args=[self.enterprise.pk]), {"client_token": token}
        )
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(CallAttempt.objects.count(), 1)
        self.assertEqual(Recording.objects.count(), 1)
        recording = Recording.objects.get()
        self.assertTrue(recording.audio_file.storage.exists(recording.audio_file.name))
        another = self.client.post(
            reverse("fa_start", args=[self.enterprise.pk]),
            {"client_token": str(uuid.uuid4()), "audio": audio()},
        )
        self.assertEqual(another.status_code, 409)

    def test_other_agent_cannot_modify_or_download_recordings(self):
        attempt = self.start_call()
        recording = Recording.objects.get()
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.post(attempt["save_url"], {"q2_respondent": "Intrus"}).status_code, 403
        )
        self.assertEqual(
            self.client.post(attempt["state_url"], {"action": "pause"}).status_code, 403
        )
        self.assertEqual(
            self.client.post(attempt["upload_url"], {"audio": audio(), "sequence": 1}).status_code,
            403,
        )
        self.assertEqual(self.client.get(reverse("fa_audio", args=[recording.pk])).status_code, 403)
        self.other.groups.add(Group.objects.create(name="manager_fa"))
        response = self.client.get(reverse("fa_audio", args=[recording.pk]))
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_draft_pause_resume_and_final_audio_required(self):
        attempt = self.start_call()
        result = self.client.post(
            attempt["save_url"],
            {"q2_respondent": "Marie", "q12_need": "Non", "q13_amount": "wrong-hidden-input"},
        )
        self.assertEqual(result.status_code, 200, result.content)
        row = CallAttempt.objects.get()
        self.assertEqual(row.answers["q2_respondent"], "Marie")
        self.assertEqual(row.answers["q13_amount"], "")
        self.assertEqual(row.answers["survey_metadata"]["channel"], "Téléphone")
        self.assertEqual(
            self.client.post(attempt["state_url"], {"action": "pause"}).json()["status"], "pause"
        )
        self.assertEqual(
            self.client.post(attempt["state_url"], {"action": "resume"}).json()["status"],
            "en_cours",
        )
        self.assertEqual(
            self.client.post(attempt["finish_url"], {"status": "injoignable"}).status_code, 400
        )
        self.upload_final(attempt)
        self.assertEqual(
            self.client.post(attempt["finish_url"], {"status": "injoignable"}).status_code, 200
        )
        row.refresh_from_db()
        self.assertIsNotNone(row.ended_at)
        self.assertEqual(row.recordings.count(), 2)
        self.assertEqual(self.client.post(attempt["save_url"], {}).status_code, 409)

    def test_complete_form_conditional_validation_and_new_attempt_preserves_history(self):
        attempt = self.start_call()
        self.upload_final(attempt)
        incomplete = self.client.post(attempt["finish_url"], {"status": "formulaire_avec_audio"})
        self.assertEqual(incomplete.status_code, 400)
        self.assertIn("q2_respondent", incomplete.json()["errors"])
        data = complete_answers()
        data["status"] = "formulaire_avec_audio"
        result = self.client.post(attempt["finish_url"], data)
        self.assertEqual(result.status_code, 200, result.content)
        self.enterprise.refresh_from_db()
        self.assertEqual(self.enterprise.status, "formulaire_avec_audio")
        self.assertEqual(self.enterprise.answers["q11_permanent"], 0)
        next_attempt = self.start_call()
        self.assertNotEqual(next_attempt["attempt_id"], attempt["attempt_id"])
        self.assertEqual(CallAttempt.objects.count(), 2)
        self.assertEqual(Recording.objects.count(), 3)

    def test_callback_must_be_future_and_preserves_draft(self):
        attempt = self.start_call()
        self.upload_final(attempt)
        self.assertEqual(
            self.client.post(attempt["finish_url"], {"status": "a_rappeler"}).status_code, 400
        )
        result = self.client.post(
            attempt["finish_url"],
            {
                "status": "a_rappeler",
                "callback_at": (timezone.now() + timedelta(days=1)).isoformat(),
                "notes": "Après-midi",
            },
        )
        self.assertEqual(result.status_code, 200)
        self.enterprise.refresh_from_db()
        self.assertIsNotNone(self.enterprise.callback_at)

    def test_final_audio_cannot_be_reused_after_later_recording(self):
        attempt = self.start_call()
        self.upload_final(attempt)
        self.assertEqual(
            self.client.post(
                attempt["upload_url"], {"audio": audio(), "sequence": 2, "full": "1"}
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(attempt["finish_url"], {"status": "appel_tente"}).status_code, 400
        )
        self.upload_final(attempt, 3)
        self.assertEqual(
            self.client.post(attempt["finish_url"], {"status": "appel_tente"}).status_code, 200
        )

    def test_sequence_retry_cannot_overwrite_audio(self):
        attempt = self.start_call()
        result = self.upload_final(attempt)
        repeated = self.upload_final(attempt)
        self.assertEqual(result["recording_id"], repeated["recording_id"])
        changed = self.client.post(
            attempt["upload_url"],
            {"audio": audio(b"\x1aE\xdf\xa3" + b"different" * 10), "sequence": 1, "final": "1"},
        )
        self.assertEqual(changed.status_code, 409)
        self.assertEqual(Recording.objects.count(), 2)

    def test_filter_analytics_and_export_only_completed_answers(self):
        self.enterprise.status = "formulaire_avec_audio"
        self.enterprise.answers = {
            **complete_answers(),
            "q12_need": "Oui",
            "q13_amount": "1000000",
            "q28_stage": "Croissance",
        }
        self.enterprise.save()
        Enterprise.objects.create(
            reference="FA-002", name="Brouillon", city="Yaoundé", answers={"q13_amount": "9000000"}
        )
        response = self.client.get(reverse("fa_index"), {"city": "Douala"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["metrics"]["total"], 1)
        self.assertEqual(self.client.get(reverse("fa_analytics")).status_code, 403)
        self.agent.groups.add(Group.objects.create(name="manager_fa"))
        response = self.client.get(reverse("fa_analytics"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["funding_total"], Decimal("1000000"))
        self.assertEqual(response.context["funding_amount_count"], 1)
        self.assertTrue(response.context["answer_breakdowns"])
        result = self.client.get(reverse("fa_export"), {"city": "Douala"})
        self.assertContains(result, "Entreprise Exemple")
        self.assertNotContains(result, "Brouillon")

    def test_detail_has_all_sections_and_audio_is_private(self):
        self.start_call()
        response = self.client.get(reverse("fa_detail", args=[self.enterprise.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["form_sections"]), 7)
        self.assertEqual(response.context["next_sequence"], 1)
        self.assertTrue(response.context["can_edit"])

    def test_missing_phone_can_be_corrected_before_start(self):
        self.enterprise.phone = ""
        self.enterprise.save(update_fields=["phone"])
        result = self.client.post(
            reverse("fa_start", args=[self.enterprise.pk]),
            {"client_token": str(uuid.uuid4()), "audio": audio(), "q4_phone": "699 000 002"},
        )
        self.assertEqual(result.status_code, 200, result.content)
        self.enterprise.refresh_from_db()
        self.assertEqual(self.enterprise.phone, "699000002")
        self.assertEqual(self.enterprise.answers["q4_phone"], "699 000 002")
        self.assertEqual(Recording.objects.count(), 1)

    def test_history_remains_visible_when_operator_account_was_deleted(self):
        attempt = self.start_call()
        self.upload_final(attempt)
        self.client.post(attempt["finish_url"], {"status": "injoignable"})
        self.client.force_login(self.other)
        self.other.groups.add(Group.objects.create(name="manager_fa"))
        self.agent.delete()
        response = self.client.get(reverse("fa_detail", args=[self.enterprise.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Opérateur supprimé")
        self.assertEqual(response.content.count(b'preload="none"'), 2)

    def test_consultant_can_analyze_but_cannot_enter_operator_pages(self):
        self.agent.groups.add(Group.objects.get_or_create(name="consultant")[0])
        self.assertEqual(self.client.get(reverse("fa_analytics")).status_code, 200)
        self.assertEqual(self.client.get(reverse("fa_export")).status_code, 200)
        self.assertEqual(self.client.get(reverse("fa_index")).status_code, 302)

    def test_fa_landing_distinguishes_pme_and_future_funds_campaign(self):
        response = self.client.get(reverse("fa_home"))
        self.assertContains(response, reverse("fa_index"))
        self.assertContains(response, reverse("fa_funds"))
        self.assertContains(response, "Fonds d’amorçage")
        response = self.client.get(reverse("fa_funds"))
        self.assertContains(response, "En attente des données et du questionnaire")
        self.assertNotContains(response, "fa-questionnaire")
        self.assertNotContains(response, "Démarrer l’appel")

    def test_main_dashboard_shows_separate_pme_and_funds_call_totals(self):
        Enterprise.objects.create(
            reference="PME-APPELEE",
            name="PME appelée",
            campaign=Enterprise.CAMPAIGN_PME,
            status="appel_tente",
        )
        Enterprise.objects.create(
            reference="FONDS-FUTUR",
            name="Fonds futur",
            campaign=Enterprise.CAMPAIGN_FUNDS,
            status="en_attente",
        )
        cache.clear()
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["fa_pme_effectues"], 1)
        self.assertEqual(response.context["fa_pme_total"], 2)
        self.assertEqual(response.context["fa_funds_effectues"], 0)
        self.assertEqual(response.context["fa_funds_total"], 1)
        self.assertNotContains(response, "PME appelée")
        self.assertContains(response, "1 / 2")
        self.assertContains(response, "0 / 1")

    def test_funds_data_cannot_enter_pme_list_filters_analytics_or_export(self):
        self.agent.groups.add(Group.objects.get_or_create(name="manager_fa")[0])
        Enterprise.objects.create(
            reference="FONDS-FUTUR",
            campaign=Enterprise.CAMPAIGN_FUNDS,
            name="Fonds futur",
            sector="Investissement",
            city="Ville future",
            status="formulaire_avec_audio",
            answers={"q12_need": "Oui", "q13_amount": "999999"},
        )
        response = self.client.get(reverse("fa_index"))
        self.assertEqual(response.context["metrics"]["total"], 1)
        self.assertNotContains(response, "Fonds futur")
        self.assertNotIn("Investissement", response.context["sectors"])
        self.assertNotIn("Ville future", response.context["cities"])
        response = self.client.get(reverse("fa_analytics"))
        self.assertEqual(response.context["funding_total"], 0)
        self.assertNotContains(self.client.get(reverse("fa_export")), "Fonds futur")

    def test_pme_form_and_call_actions_reject_future_funds_contacts(self):
        enterprise = Enterprise.objects.create(
            reference="FONDS-FUTUR",
            name="Fonds futur",
            phone="699000005",
            campaign=Enterprise.CAMPAIGN_FUNDS,
        )
        self.assertEqual(
            self.client.get(reverse("fa_detail", args=[enterprise.pk])).status_code, 404
        )
        result = self.client.post(
            reverse("fa_start", args=[enterprise.pk]),
            {
                "client_token": str(uuid.uuid4()),
                "audio": audio(),
            },
        )
        self.assertEqual(result.status_code, 404)
        self.assertFalse(enterprise.attempts.exists())
        attempt = CallAttempt.objects.create(
            enterprise=enterprise,
            agent=self.agent,
            client_token=uuid.uuid4(),
        )
        self.assertEqual(
            self.client.post(reverse("fa_save", args=[attempt.pk]), {}).status_code, 404
        )


class FAQuestionnaireTests(TestCase):
    def test_all_36_questions_and_support_skip_logic(self):
        for number in range(1, 37):
            self.assertTrue(any(q["key"].startswith(f"q{number}_") for q in QUESTIONS))
        form = QuestionnaireForm(complete_answers(), complete=True)
        self.assertTrue(form.is_valid(), form.errors)
        data = complete_answers()
        data["q27_support_desired"] = []
        form = QuestionnaireForm(data, complete=True)
        self.assertFalse(form.is_valid())
        self.assertIn("q27_support_desired", form.errors)
        self.assertNotIn("q21_investor", form.errors)

    def test_zero_counts_and_amounts_are_valid_and_hidden_fields_cleared(self):
        data = complete_answers()
        data.update(
            q11_none=False,
            q11_permanent=0,
            q11_temporary=0,
            q12_need="Oui",
            q13_amount=0,
            q14_purposes=["Fonds de roulement / trésorerie"],
            q15_priority="Trésorerie",
            q16_frequency="Ponctuel",
        )
        form = QuestionnaireForm(data, complete=True)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.answers()["q13_amount"], "0")


class FAImportTests(TestCase):
    def test_pme_import_never_reuses_a_future_campaign_reference(self):
        row = Enterprise.objects.create(
            reference="FA-001",
            name="Fonds futur",
            campaign=Enterprise.CAMPAIGN_FUNDS,
        )
        with self.assertRaisesMessage(ValueError, "autre campagne"):
            import_records([{"source_number": 1, "name": "PME"}])
        row.refresh_from_db()
        self.assertEqual(row.name, "Fonds futur")
        self.assertEqual(row.campaign, Enterprise.CAMPAIGN_FUNDS)

    def test_import_idempotent_preserves_work_and_shared_phone(self):
        records = [
            {
                "source_number": 1,
                "name": "A",
                "phone_raw": 699000001,
                "city": "Douala",
                "annual_revenue_fcfa": 1200000,
            },
            {"source_number": 2, "name": "B", "phone_raw": "699000001 / 677000001"},
        ]
        self.assertEqual(import_records(records)["created"], 2)
        row = Enterprise.objects.get(reference="FA-001")
        row.status, row.answers = "refus", {"q2_respondent": "Marie"}
        row.save()
        self.assertEqual(import_records(records)["updated"], 2)
        row.refresh_from_db()
        self.assertEqual(row.status, "refus")
        self.assertEqual(row.answers["q2_respondent"], "Marie")
        self.assertEqual(Enterprise.objects.count(), 2)

    def test_invalid_or_duplicate_import_is_atomic_and_dry_run_does_not_write(self):
        with self.assertRaises(ValueError):
            import_records([{"source_number": 1, "name": "A"}, {"source_number": 1, "name": "B"}])
        self.assertFalse(Enterprise.objects.exists())
        result = import_records([{"source_number": 1, "name": "A"}], dry_run=True)
        self.assertEqual(result["created"], 1)
        self.assertFalse(Enterprise.objects.exists())

    def test_original_xlsx_columns(self):
        import openpyxl

        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append([None, "#", "Nom de l'entreprise", "Tel", "Ville", "CA FCFA", "Filières"])
        sheet.append([None, 1, "GIC Exemple", 699000001, "Douala", 1000000, "Fruits et légumes"])
        stream = io.BytesIO()
        stream.name = "entreprises.xlsx"
        workbook.save(stream)
        stream.seek(0)
        records = records_from_file(stream)
        self.assertEqual(records[0]["name"], "GIC Exemple")
        self.assertEqual(import_records(records)["created"], 1)

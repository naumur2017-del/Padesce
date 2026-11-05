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

from .campaigns import INVESTISSEURS, PORTEURS
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

    def test_fa_landing_distinguishes_pme_and_funds_campaigns(self):
        response = self.client.get(reverse("fa_home"))
        self.assertContains(response, reverse("fa_index"))
        self.assertContains(response, reverse("fa_funds"))
        self.assertContains(response, "Fonds d’amorçage")
        response = self.client.get(reverse("fa_funds"))
        self.assertContains(response, PORTEURS.urls["index"])
        self.assertContains(response, INVESTISSEURS.urls["index"])
        self.assertNotContains(response, "En attente des données et du questionnaire")

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
            campaign=Enterprise.CAMPAIGN_PORTEURS,
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
            campaign=Enterprise.CAMPAIGN_PORTEURS,
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

    def test_form_and_call_actions_reject_unknown_campaign(self):
        enterprise = Enterprise.objects.create(
            reference="FONDS-FUTUR",
            name="Fonds futur",
            phone="699000005",
            campaign="fonds_amorcage",
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
            campaign=Enterprise.CAMPAIGN_PORTEURS,
        )
        with self.assertRaisesMessage(ValueError, "autre campagne"):
            import_records([{"source_number": 1, "name": "PME"}])
        row.refresh_from_db()
        self.assertEqual(row.name, "Fonds futur")
        self.assertEqual(row.campaign, Enterprise.CAMPAIGN_PORTEURS)

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


def workbook_stream(*sheets):
    import openpyxl

    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for title, rows in sheets:
        sheet = workbook.create_sheet(title)
        for row in rows:
            sheet.append(row)
    stream = io.BytesIO()
    stream.name = "contacts.xlsx"
    workbook.save(stream)
    stream.seek(0)
    return stream


class FAFundsQuestionnaireTests(TestCase):
    def valid(self, campaign, data):
        form = QuestionnaireForm(data, campaign=campaign)
        self.assertTrue(form.is_valid(), form.errors)
        return form.cleaned_data

    def test_every_numbered_question_of_both_documents_is_present(self):
        for campaign, count in ((PORTEURS, 43), (INVESTISSEURS, 29)):
            numbers = {q["label"].split(".")[0] for q in campaign.questions}
            for number in range(1, count + 1):
                self.assertIn(str(number), numbers)
        self.assertEqual(
            len([q for q in INVESTISSEURS.questions if q["key"].startswith("ib_")]), 25
        )

    def test_keys_are_unique_and_no_question_is_mandatory(self):
        for campaign in (PORTEURS, INVESTISSEURS):
            keys = [q["key"] for q in campaign.questions]
            self.assertEqual(len(keys), len(set(keys)))
            self.assertFalse(campaign.has_required)

    def test_answering_no_to_question_32_goes_to_question_39(self):
        cleaned = self.valid(
            PORTEURS,
            {
                "p32_applied": "Non",
                "p33_organisations": "Banque",
                "p35_requested": "1000",
                "p38_reasons": ["Dossier"],
                "p39_support": "Oui",
                "p40_organisation": "Incubateur",
            },
        )
        self.assertEqual(cleaned["p33_organisations"], "")
        self.assertEqual(cleaned["p35_requested"], "")
        self.assertEqual(cleaned["p38_reasons"], [])
        self.assertEqual(cleaned["p39_support"], "Oui")
        self.assertEqual(cleaned["p40_organisation"], "Incubateur")

    def test_no_funding_need_hides_questions_23_to_28(self):
        data = {"p23_total": "5000", "p25_use": ["Prototype"], "p28_type": "Prêt"}
        cleaned = self.valid(PORTEURS, {**data, "p22_need": "Non"})
        self.assertEqual(cleaned["p23_total"], "")
        self.assertEqual(cleaned["p25_use"], [])
        self.assertEqual(cleaned["p28_type"], "")
        for need in ("Oui maintenant", "Plus tard"):
            cleaned = self.valid(PORTEURS, {**data, "p22_need": need})
            self.assertEqual(cleaned["p23_total"], 5000)
            self.assertEqual(cleaned["p28_type"], "Prêt")

    def test_investor_conditions_with_several_values_and_stage_table(self):
        data = {"i17_aspects": ["Marché"], "ib_seed_usual": "2000"}
        cleaned = self.valid(
            INVESTISSEURS, {**data, "i16_audit": "Rarement", "i5_stages": ["Seed (prototype)"]}
        )
        self.assertEqual(cleaned["i17_aspects"], ["Marché"])
        self.assertEqual(cleaned["ib_seed_usual"], 2000)
        cleaned = self.valid(INVESTISSEURS, {**data, "i16_audit": "Jamais", "i5_stages": []})
        self.assertEqual(cleaned["i17_aspects"], [])
        self.assertEqual(cleaned["ib_seed_usual"], "")

    def test_condition_values_reach_the_browser(self):
        form = QuestionnaireForm(campaign=PORTEURS)
        self.assertEqual(
            form.fields["p23_total"].widget.attrs["data-condition-value"],
            "Oui maintenant||Plus tard",
        )


class FAFundsImportTests(TestCase):
    def test_facebook_list_columns_and_contact_without_name(self):
        stream = workbook_stream(
            (
                "Contacts",
                [
                    [
                        "country_code",
                        "public_name",
                        "country_name",
                        "public_name",
                        "phone_number",
                        "formatted_phone",
                    ],
                    [1, None, "CM", None, 237693107409, "+237 6 93 10 74 09"],
                    [2, "Élie Zang", "CM", "Élie Zang", 237691706140, "+237 6 91 70 61 40"],
                ],
            )
        )
        records = records_from_file(stream, PORTEURS)
        self.assertEqual(import_records(records, campaign=PORTEURS)["created"], 2)
        row = Enterprise.objects.get(reference="FP-002")
        self.assertEqual(row.campaign, Enterprise.CAMPAIGN_PORTEURS)
        self.assertEqual((row.name, row.phone), ("Élie Zang", "237691706140"))
        self.assertEqual(
            Enterprise.objects.get(reference="FP-001").name, "Contact sans nom (237693107409)"
        )
        self.assertEqual(import_records(records, campaign=PORTEURS)["updated"], 2)

    def test_directory_sheets_restart_numbering_and_shared_structures_are_merged(self):
        header = ["N°", "Structure / dispositif", "Type", "Ville / pays", "Téléphone", "Courriel"]
        stream = workbook_stream(
            (
                "Fonds et dispositifs",
                [
                    ["Titre du répertoire"],
                    header,
                    [1, "Janngo Capital", "Fonds", "Abidjan", "+33 6 23 13 71 72", "Non renseigné"],
                    [
                        2,
                        "ATIDI",
                        "Garantie",
                        "Nairobi",
                        "+254 (0)20 272 6999\n+254 719 014 000",
                        "i@a.org",
                    ],
                ],
            ),
            (
                "Investisseurs potentiels",
                [
                    [*header, "Précisions / points à confirmer"],
                    [1, "BICEC", "Banque", "Douala", "Non renseigné", "c@b.com", "À confirmer"],
                    [
                        2,
                        "Janngo Capital",
                        "Fonds",
                        "Abidjan",
                        "+33 6 23 13 71 72",
                        "j@j.com",
                        "Note",
                    ],
                ],
            ),
        )
        records = records_from_file(stream, INVESTISSEURS)
        result = import_records(records, campaign=INVESTISSEURS)
        self.assertEqual(result["created"], 3)
        janngo = Enterprise.objects.get(reference="FI-1-001")
        self.assertEqual(janngo.email, "j@j.com")
        self.assertEqual(janngo.source_data["notes"], "Note")
        self.assertEqual(janngo.phone, "+33623137172")
        atidi = Enterprise.objects.get(name="ATIDI")
        self.assertEqual(atidi.phone_numbers, ["+254202726999", "+254719014000"])
        bicec = Enterprise.objects.get(reference="FI-2-001")
        self.assertEqual((bicec.phone, bicec.sector), ("", "Banque"))
        self.assertEqual(import_records(records, campaign=INVESTISSEURS)["updated"], 3)

    def test_same_number_can_exist_in_each_campaign(self):
        import_records([{"source_number": 1, "name": "PME"}])
        import_records([{"source_number": 1, "name": "Porteur"}], campaign=PORTEURS)
        self.assertEqual(Enterprise.objects.count(), 2)


@override_settings(
    PADESCE_ACTIVITY_TRACKING_ENABLED=False,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class FAFundsWorkflowTests(TestCase):
    def setUp(self):
        self.agent = get_user_model().objects.create_user(username="fa-agent", password="test-pass")
        self.porteur = Enterprise.objects.create(
            reference="FP-001",
            campaign=Enterprise.CAMPAIGN_PORTEURS,
            name="tchangou",
            phone="237653192874",
        )
        self.waiting = Enterprise.objects.create(
            reference="FP-002", campaign=Enterprise.CAMPAIGN_PORTEURS, name="Pas appelé"
        )
        self.structure = Enterprise.objects.create(
            reference="FI-1-001",
            campaign=Enterprise.CAMPAIGN_INVESTORS,
            name="Fonds Exemple",
            phone="+237222000000",
            city="Douala",
            source_data={"email": "a@b.cm\nc@d.cm", "notes": "Contact à confirmer"},
        )
        self.client.force_login(self.agent)

    def manager(self):
        self.agent.groups.add(Group.objects.get_or_create(name="manager_fa")[0])

    def complete_call(self, enterprise, answers):
        attempt = self.client.post(
            reverse("fa_start", args=[enterprise.pk]),
            {"client_token": str(uuid.uuid4()), "audio": audio()},
        ).json()
        self.client.post(
            attempt["upload_url"],
            {"audio": audio(), "sequence": 1, "full": "1", "final": "1"},
        )
        result = self.client.post(
            attempt["finish_url"], {"status": "formulaire_avec_audio", **answers}
        )
        self.assertEqual(result.status_code, 200, result.content)

    def test_lists_are_separated_by_campaign(self):
        response = self.client.get(PORTEURS.urls["index"])
        self.assertContains(response, "tchangou")
        self.assertNotContains(response, "Fonds Exemple")
        response = self.client.get(INVESTISSEURS.urls["index"])
        self.assertContains(response, "Fonds Exemple")
        self.assertNotContains(response, "tchangou")
        self.assertEqual(self.client.get("/fa/fonds-amorcage/inconnue/").status_code, 404)

    def test_detail_shows_the_form_of_the_contact_campaign(self):
        response = self.client.get(reverse("fa_detail", args=[self.porteur.pk]))
        self.assertContains(response, "43. Qu’attendez-vous principalement")
        self.assertNotContains(response, "Déclaration du répondant")
        self.assertNotContains(response, "Les champs marqués *")
        response = self.client.get(reverse("fa_detail", args=[self.structure.pk]))
        self.assertContains(response, "Introduction à lire")
        self.assertContains(response, "Contact à confirmer")
        form = response.context["form"]
        self.assertEqual(form["i_org"].value(), "Fonds Exemple")
        self.assertEqual(form["i_email"].value(), "a@b.cm / c@d.cm")

    def test_answers_fill_the_row_of_the_called_contact(self):
        self.manager()
        self.complete_call(
            self.porteur,
            {
                "q4_phone": "237653192874",
                "p1_name": "Paul Tchangou",
                "p14_clients": ["Particuliers", "Entreprises"],
                "p22_need": "Oui maintenant",
                "p23_total": "5000000",
                "p12_none": "on",
            },
        )
        response = self.client.get(PORTEURS.urls["responses"])
        self.assertEqual(response.status_code, 200)
        rows = {row[0]: row for row in response.context["table_rows"]}
        offset = len(response.context["contact_columns"])
        keys = [q["key"] for q in PORTEURS.questions]
        row = rows["FP-001"]
        self.assertEqual(len(row), offset + len(keys))
        self.assertEqual(row[offset + keys.index("p1_name")], "Paul Tchangou")
        self.assertEqual(row[offset + keys.index("p14_clients")], "Particuliers / Entreprises")
        self.assertEqual(row[offset + keys.index("p23_total")], 5000000)
        self.assertEqual(row[offset + keys.index("p12_none")], "Oui")
        self.assertEqual(row[response.context["contact_columns"].index("Opérateur")], "fa-agent")
        self.assertEqual(rows["FP-002"][offset + keys.index("p1_name")], "")
        self.assertContains(response, "1. Quels sont vos nom et prénoms ?")

    def test_excel_export_has_one_column_per_question_and_one_row_per_contact(self):
        import openpyxl

        self.manager()
        self.complete_call(self.porteur, {"p1_name": "=SOMME(A1)", "p7_year": "2024"})
        response = self.client.get(PORTEURS.urls["export_xlsx"])
        self.assertEqual(response.status_code, 200)
        sheet = openpyxl.load_workbook(io.BytesIO(response.content)).active
        rows = list(sheet.iter_rows(values_only=True))
        header = list(rows[0])
        for question in PORTEURS.questions:
            self.assertIn(question["label"], header)
        self.assertEqual(len(rows), 3)
        row = next(item for item in rows if item[0] == "FP-001")
        self.assertEqual(
            row[header.index("7. En quelle année avez-vous commencé ce projet ?")], 2024
        )
        cell = sheet.cell(
            row=rows.index(row) + 1, column=header.index("1. Quels sont vos nom et prénoms ?") + 1
        )
        self.assertEqual((cell.value, cell.data_type), ("=SOMME(A1)", "s"))

    def test_csv_export_is_separated_by_campaign(self):
        self.manager()
        response = self.client.get(INVESTISSEURS.urls["export"])
        self.assertContains(response, "Fonds Exemple")
        self.assertContains(response, "29. Selon vous")
        self.assertNotContains(response, "tchangou")

    def test_responses_are_reserved_to_analysis_roles(self):
        urls = (PORTEURS.urls["responses"], PORTEURS.urls["export_xlsx"])
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)
        self.agent.groups.add(Group.objects.get_or_create(name="consultant")[0])
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_analytics_use_the_questions_of_the_campaign(self):
        self.manager()
        self.complete_call(self.porteur, {"p22_need": "Plus tard"})
        response = self.client.get(PORTEURS.urls["analytics"])
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Besoin total exprimé")
        group = next(
            item
            for item in response.context["answer_breakdowns"]
            if item["label"].startswith("22.")
        )
        self.assertEqual(group["rows"], [{"label": "Plus tard", "count": 1}])

    def test_superuser_imports_into_the_selected_campaign(self):
        self.agent.is_superuser = True
        self.agent.save()
        stream = workbook_stream(("Contacts", [["public_name", "phone_number"], ["Ada", 237699]]))
        response = self.client.post(PORTEURS.urls["import"], {"file": stream})
        self.assertRedirects(response, PORTEURS.urls["index"], fetch_redirect_response=False)
        row = Enterprise.objects.get(name="Ada")
        self.assertEqual(row.campaign, Enterprise.CAMPAIGN_PORTEURS)

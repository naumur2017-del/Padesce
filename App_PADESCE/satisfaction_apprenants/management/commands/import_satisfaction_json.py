import json
from datetime import date, time, datetime

from django.core.management import CommandError
from django.core.management.base import BaseCommand
from django.db import IntegrityError

from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.formations.models import Classe
from App_PADESCE.satisfaction_apprenants.models import SatisfactionApprenant


class Command(BaseCommand):
    help = "Import satisfaction entries from a JSON list and save them as SatisfactionApprenant."

    def add_arguments(self, parser):
        parser.add_argument("json_path", help="Path to the JSON file")
        parser.add_argument("--classe", help="Default classe code if the payload omits one")
        parser.add_argument("--apprenant", help="Default apprenant code if the payload omits one")
        parser.add_argument("--date", help="Date for all entries (YYYY-MM-DD)", default=date.today().isoformat())
        parser.add_argument("--heure", help="Time for all entries (HH:MM)", default="12:00")
        parser.add_argument("--q-score", type=int, help="Default score for Q1..Q9 (1-5)", default=3)

    def handle(self, *args, **options):
        path = options["json_path"]
        default_classe = options.get("classe")
        default_apprenant = options.get("apprenant")
        q_score = min(5, max(1, options.get("q_score", 3)))
        try:
            base_date = datetime.strptime(options["date"], "%Y-%m-%d").date()
        except ValueError as exc:
            raise CommandError(f"Invalid date: {exc}")
        try:
            base_time = datetime.strptime(options["heure"], "%H:%M").time()
        except ValueError as exc:
            raise CommandError(f"Invalid time: {exc}")

        with open(path, encoding="utf-8") as f:
            payload = json.load(f)

        created = 0
        for entry in payload:
            classe_code = entry.get("classe_code") or default_classe
            apprenant_code = entry.get("apprenant_code") or default_apprenant
            classe = None
            if classe_code:
                classe = Classe.objects.filter(code=classe_code).first()
                if not classe:
                    self.stderr.write(
                        f"Classe '{classe_code}' not found; record will be saved without classe."
                    )
            apprenant = None
            if apprenant_code:
                apprenant = Apprenant.objects.filter(code__iexact=apprenant_code).first()
            if not apprenant:
                self.stderr.write(f"Apprenant '{apprenant_code or 'unnamed'}' missing; record will rely on classe only.")

            comment = " | ".join(
                filter(None, [entry.get("reason_summary"), entry.get("facts")])
            )
            obj = SatisfactionApprenant(
                classe=classe,
                apprenant=apprenant,
                date=base_date,
                heure=base_time,
                q1_clarte_exposes=q_score,
                q2_interaction_formateur=q_score,
                q3_rythme_formation=q_score,
                q4_qualite_supports=q_score,
                q5_applicabilite_contenu=q_score,
                q6_organisation_logistique=q_score,
                q7_respect_programme=q_score,
                q8_adequation_besoins=q_score,
                q9_satisfaction_globale=q_score,
                commentaire=comment or entry.get("reason_summary", ""),
                recommandations=entry.get("reason_summary") or entry.get("question_category"),
                transcription=entry.get("reason_summary"),
            )
            try:
                obj.save()
            except IntegrityError as exc:
                self.stderr.write(f"Error saving entry {entry.get('audio')}: {exc}")
                continue
            created += 1

        self.stdout.write(self.style.SUCCESS(f"{created} satisfaction records imported."))

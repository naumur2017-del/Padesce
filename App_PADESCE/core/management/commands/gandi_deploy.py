from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from App_PADESCE.core.gandi_deploy import make_run_id, run_deployment


class Command(BaseCommand):
    help = "Execute un pipeline de deploiement Gandi avec suivi JSON persistant."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--run-id",
            default="",
            help="Identifiant de run existant. Si absent, un nouvel identifiant est genere.",
        )
        parser.add_argument(
            "--mode",
            choices=("preview", "deploy"),
            default="deploy",
            help="Mode du pipeline: previsualisation ou deploiement reel.",
        )

    def handle(self, *args, **options):
        run_id = str(options.get("run_id") or "").strip() or make_run_id()
        mode = str(options.get("mode") or "deploy").strip()
        result = run_deployment(run_id=run_id, mode=mode)
        self.stdout.write(self.style.NOTICE(f"Run: {run_id}"))
        self.stdout.write(self.style.NOTICE(f"Status: {result.get('status', 'unknown')}"))
        if result.get("status") != "completed":
            raise CommandError(result.get("error") or "Le pipeline de deploiement a echoue.")

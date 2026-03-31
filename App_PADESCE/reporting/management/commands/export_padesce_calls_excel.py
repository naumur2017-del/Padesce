from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from App_PADESCE.reporting.padesce_calls_excel import build_padesce_calls_report


class Command(BaseCommand):
    help = "Genere un rapport Excel complet des appels PADESCE."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="",
            help="Chemin de sortie du fichier Excel. Par defaut: output/spreadsheet/rapport_appels_padesce_<timestamp>.xlsx",
        )

    def handle(self, *args, **options):
        output = options["output"]
        if output:
            output_path = Path(output)
        else:
            stamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
            output_path = Path("output/spreadsheet") / f"rapport_appels_padesce_{stamp}.xlsx"

        summary = build_padesce_calls_report(output_path)
        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Rapport Excel genere: {summary['path']} | total={summary['total_calls']} | "
                    f"reussis={summary['successful_calls']} | echoues={summary['failed_calls']}"
                )
            )
        )

"""
Commande de management Django — Rapport journalier automatique.
Usage :
    python manage.py send_daily_app_report
    python manage.py send_daily_app_report --dry-run
    python manage.py send_daily_app_report --start 2025-01-01 --end 2025-01-31
"""
import logging
from datetime import date, timedelta

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Genere et envoie le rapport journalier de l'application par email."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Genere le rapport sans l'envoyer par email. Affiche un apercu en console.",
        )
        parser.add_argument(
            "--start",
            type=str,
            default=None,
            help="Date de debut au format YYYY-MM-DD (defaut: aujourd'hui).",
        )
        parser.add_argument(
            "--end",
            type=str,
            default=None,
            help="Date de fin au format YYYY-MM-DD (defaut: aujourd'hui).",
        )

    def handle(self, *args, **options):
        from App_PADESCE.reporting.app_report import (
            build_application_report,
            build_report_text,
            get_report_email_recipients,
            parse_report_dates,
            send_report_by_email,
        )

        start_date, end_date = parse_report_dates(options.get("start"), options.get("end"))
        dry_run: bool = options.get("dry_run", False)

        self.stdout.write(f"Chargement du rapport du {start_date} au {end_date}...")
        try:
            report = build_application_report(start_date, end_date)
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Erreur lors de la generation du rapport: {exc}"))
            logger.exception("send_daily_app_report — erreur build_application_report")
            raise

        self.stdout.write(self.style.SUCCESS("Rapport genere avec succes."))
        self.stdout.write(build_report_text(report))

        if dry_run:
            self.stdout.write(self.style.WARNING("Mode dry-run : le rapport n'est pas envoye par email."))
            recipients = get_report_email_recipients()
            if recipients:
                self.stdout.write(f"Destinataires configures: {', '.join(recipients)}")
            else:
                self.stdout.write(self.style.WARNING("ATTENTION: Aucun destinataire configure (REPORT_EMAIL_TO vide)."))
            return

        self.stdout.write("Envoi du rapport par email...")
        try:
            result = send_report_by_email(report)
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Erreur lors de l'envoi du rapport: {exc}"))
            logger.exception("send_daily_app_report — erreur send_report_by_email")
            raise

        if result.get("ok"):
            self.stdout.write(self.style.SUCCESS(result["detail"]))
        else:
            self.stdout.write(self.style.WARNING(f"Rapport non envoye: {result['detail']}"))

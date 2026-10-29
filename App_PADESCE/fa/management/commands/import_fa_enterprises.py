from django.core.management.base import BaseCommand, CommandError

from App_PADESCE.fa.imports import import_records, records_from_file


class Command(BaseCommand):
    help = "Importe les entreprises FA sans supprimer les appels, réponses ou enregistrements."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Registre .xlsx ou .json")
        parser.add_argument("--dry-run", action="store_true", help="Valide sans enregistrer")

    def handle(self, *args, **options):
        try:
            result = import_records(records_from_file(options["path"]), dry_run=options["dry_run"])
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        prefix = "Simulation : " if options["dry_run"] else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}{result['created']} créées, {result['updated']} existantes, {result['skipped']} ignorées."
            )
        )
        for warning in result["warnings"][:100]:
            self.stdout.write(self.style.WARNING(warning))

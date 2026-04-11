from django.core.management.base import BaseCommand, CommandError

from App_PADESCE.satisfaction_apprenants.cutoff_sync import sync_cutoff_reference_data


class Command(BaseCommand):
    help = (
        "Synchronise les prestations, classes, apprenants et appels a partir du classeur "
        "reseau (par defaut le cutoff), puis desactive les donnees locales hors source."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="cutoff",
            help="Cle de la source reseau a utiliser. Defaut: cutoff.",
        )
        parser.add_argument(
            "--skip-appels",
            action="store_true",
            help="Ne rattache pas les appels existants a la source et ne modifie pas leur statut actif.",
        )
        parser.add_argument(
            "--keep-missing-active",
            action="store_true",
            help="Conserve actives les entites locales absentes du cutoff.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Calcule la synchronisation sans valider les modifications en base.",
        )

    def handle(self, *args, **options):
        source_key = str(options.get("source") or "cutoff").strip() or "cutoff"
        sync_appels = not bool(options.get("skip_appels"))
        deactivate_missing = not bool(options.get("keep_missing_active"))
        dry_run = bool(options.get("dry_run"))

        try:
            summary = sync_cutoff_reference_data(
                source_key=source_key,
                sync_appels=sync_appels,
                deactivate_missing=deactivate_missing,
                dry_run=dry_run,
            )
        except Exception as exc:
            raise CommandError(f"Synchronisation cutoff impossible: {exc}") from exc

        message = (
            f"Source {summary['source_key']} | "
            f"{summary['source_records']} lignes source | "
            f"{summary['synced_apprenants']} apprenants | "
            f"{summary['synced_classes']} classes | "
            f"{summary['synced_prestations']} prestations"
        )
        if sync_appels:
            message += (
                f" | appels maj={summary['appels_updated']}"
                f", appels desactives={summary['appels_deactivated']}"
                f", fiches reliees={summary['surveys_linked']}"
            )
        if deactivate_missing:
            message += (
                f" | hors source desactives: apprenants={summary['apprenants_deactivated']},"
                f" classes={summary['classes_deactivated']},"
                f" prestations={summary['prestations_deactivated']}"
            )
        if dry_run:
            message += " | dry-run"

        self.stdout.write(self.style.SUCCESS(message))

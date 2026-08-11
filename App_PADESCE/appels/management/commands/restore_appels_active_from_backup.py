import sqlite3
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from App_PADESCE.appels.models import Appel


class Command(BaseCommand):
    help = (
        "Restaure les drapeaux is_active des appels depuis un backup SQLite. "
        "Par defaut, affiche seulement un apercu; utiliser --apply pour modifier."
    )

    def add_arguments(self, parser):
        parser.add_argument("backup_path", help="Chemin du backup SQLite source.")
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Applique la restauration. Sans cette option, aucune donnee n'est modifiee.",
        )

    def handle(self, *args, **options):
        backup_path = Path(options["backup_path"]).expanduser()
        if not backup_path.exists():
            raise CommandError(f"Backup introuvable: {backup_path}")

        active_ids, active_codes = self._read_active_keys(backup_path)
        if not active_ids and not active_codes:
            raise CommandError("Aucun appel actif trouve dans le backup.")

        queryset = Appel.objects.filter(is_active=False)
        by_id = queryset.filter(pk__in=active_ids)
        by_code = queryset.filter(code__in=active_codes)
        ids_to_restore = set(by_id.values_list("pk", flat=True)) | set(
            by_code.values_list("pk", flat=True)
        )

        self.stdout.write(f"Backup: {backup_path}")
        self.stdout.write(f"Appels actifs dans le backup: {len(active_ids)}")
        self.stdout.write(f"Appels actuellement inactifs a reactiver: {len(ids_to_restore)}")

        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Apercu seulement. Relancer avec --apply pour appliquer."))
            return

        with transaction.atomic():
            updated = Appel.objects.filter(pk__in=ids_to_restore, is_active=False).update(
                is_active=True
            )

        self.stdout.write(self.style.SUCCESS(f"Restauration terminee: {updated} appel(s) reactive(s)."))

    def _read_active_keys(self, backup_path):
        try:
            with sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True) as conn:
                rows = conn.execute(
                    "select id, code from appels_appel where is_active = 1"
                ).fetchall()
        except sqlite3.Error as exc:
            raise CommandError(f"Impossible de lire le backup SQLite: {exc}") from exc

        active_ids = {row[0] for row in rows if row[0] is not None}
        active_codes = {str(row[1]).strip() for row in rows if str(row[1] or "").strip()}
        return active_ids, active_codes

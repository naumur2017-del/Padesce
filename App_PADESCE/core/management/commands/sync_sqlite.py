from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from App_PADESCE.core.db_sync import sync_sqlite_databases


class Command(BaseCommand):
    help = "Fusionne une ou plusieurs bases SQLite source vers une base SQLite cible."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--source",
            action="append",
            dest="sources",
            required=True,
            help="Base SQLite source. Repetable.",
        )
        parser.add_argument("--target", required=True, help="Base SQLite cible a mettre a jour.")
        parser.add_argument(
            "--table",
            action="append",
            dest="tables",
            help="Limiter la synchronisation a une table. Repetable.",
        )
        parser.add_argument(
            "--exclude-table",
            action="append",
            dest="exclude_tables",
            help="Exclure une table. Repetable.",
        )
        parser.add_argument(
            "--conflict-strategy", choices=["newer", "source", "target"], default="newer"
        )
        parser.add_argument("--dry-run", action="store_true", help="Apercu sans ecriture.")
        parser.add_argument(
            "--no-backup", action="store_true", help="Desactive la sauvegarde avant ecriture."
        )
        parser.add_argument("--backup-dir", help="Dossier de sauvegarde.")
        parser.add_argument("--timeout", type=int, default=60, help="Timeout SQLite en secondes.")

    def handle(self, *args, **options) -> None:
        try:
            result = sync_sqlite_databases(
                target_path=options["target"],
                source_paths=options["sources"],
                include_tables=options.get("tables"),
                exclude_tables=options.get("exclude_tables"),
                conflict_strategy=options["conflict_strategy"],
                dry_run=options["dry_run"],
                backup=not options["no_backup"],
                backup_dir=options.get("backup_dir"),
                timeout_seconds=options["timeout"],
            )
        except (FileNotFoundError, ValueError, OSError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Synchronisation SQLite"))
        self.stdout.write(f"Cible: {result.target_path}")
        self.stdout.write(f"Mode: {'DRY-RUN' if result.dry_run else 'EXECUTION'}")
        self.stdout.write(f"Conflits: {result.conflict_strategy}")
        if result.backup_path:
            self.stdout.write(self.style.SUCCESS(f"Sauvegarde: {result.backup_path}"))

        for source_result in result.source_results:
            self.stdout.write("")
            self.stdout.write(self.style.HTTP_INFO(f"Source: {source_result.source_path}"))
            for table_result in source_result.tables:
                if table_result.skipped:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  - {table_result.table_name}: ignoree ({table_result.reason})"
                        )
                    )
                    continue
                self.stdout.write(
                    f"  - {table_result.table_name}: "
                    f"source={table_result.source_rows}, "
                    f"inserts={table_result.inserted}, "
                    f"updates={table_result.updated}, "
                    f"conflits_sautes={table_result.skipped_conflicts}, "
                    f"identiques={table_result.identical}"
                )
            for warning in source_result.warnings:
                self.stdout.write(self.style.WARNING(f"  ! {warning}"))

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Total: {result.inserted} insertions, {result.updated} mises a jour, "
                f"{result.skipped_conflicts} conflits ignores."
            )
        )
        if result.dry_run:
            self.stdout.write(self.style.WARNING("Aucune ecriture n'a ete faite."))
        for warning in result.warnings:
            self.stdout.write(self.style.WARNING(f"Attention: {warning}"))

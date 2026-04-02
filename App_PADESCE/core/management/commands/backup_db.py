"""
Commande de gestion Django : backup_db

Usage :
    python manage.py backup_db

Crée un backup de la base PostgreSQL (ou SQLite en dev) vers un fichier .sqlite3
dans le dossier backups/. Utilisée par le workflow GitHub Actions backup-daily.yml.
"""

from __future__ import annotations

import time

from django.core.management.base import BaseCommand, CommandError

from App_PADESCE.core import backup_manager


class Command(BaseCommand):
    help = "Crée un backup de la base de données vers backups/backup_<timestamp>.sqlite3"

    def handle(self, *args, **options) -> None:
        self.stdout.write(
            self.style.MIGRATE_HEADING("Démarrage du backup de la base de données...")
        )

        job_id = backup_manager.start_backup(triggered_by="management-command")
        last_progress = -1

        while True:
            job = backup_manager.get_job(job_id)
            if job is None:
                raise CommandError("Job de backup introuvable (erreur interne).")

            progress = job.get("progress", 0)
            message = job.get("message", "")
            status = job.get("status", "pending")

            if progress != last_progress:
                bar_filled = int(progress / 5)
                bar = "#" * bar_filled + "-" * (20 - bar_filled)
                self.stdout.write(f"  [{bar}] {progress:3d}%  {message}")
                last_progress = progress

            if status == "success":
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nBackup terminé : {job.get('backup_file')}  "
                        f"({_fmt_size(job.get('file_size', 0))}  |  "
                        f"{job.get('tables_count', '?')} tables)"
                    )
                )
                return

            if status == "error":
                raise CommandError(f"Backup échoué : {job.get('error') or job.get('message')}")

            if status == "partial":
                self.stdout.write(
                    self.style.WARNING(
                        f"\nBackup partiel : {job.get('backup_file')} — {job.get('error')}"
                    )
                )
                return

            time.sleep(0.5)


def _fmt_size(size: int | None) -> str:
    if not size:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024  # type: ignore[assignment]
    return f"{size:.1f} TB"

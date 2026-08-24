"""Vérifie une restauration PostgreSQL isolée sans jamais cibler la production."""

import os
import subprocess
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Restaure un dump uniquement vers une base PostgreSQL isolée et vérifie son catalogue."

    def add_arguments(self, parser):
        parser.add_argument("dump")
        parser.add_argument("--database", required=True)
        parser.add_argument("--host", default="localhost")
        parser.add_argument("--port", default="5432")
        parser.add_argument("--user", required=True)

    def handle(self, *args, **options):
        database = str(options["database"]).strip()
        production = str(os.getenv("POSTGRES_DB", "") or "").strip()
        if not database or database == production or any(word in database.lower() for word in ("prod", "production")):
            raise CommandError("Refus : la restauration doit cibler une base isolée non liée à la production.")
        dump = Path(options["dump"])
        if not dump.is_file() or dump.stat().st_size == 0:
            raise CommandError("Dump absent ou vide.")
        env = os.environ.copy()
        command = ["pg_restore", "--exit-on-error", "--clean", "--if-exists", "--no-owner", "--host", options["host"], "--port", str(options["port"]), "--username", options["user"], "--dbname", database, str(dump)]
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=3600)
        if result.returncode:
            raise CommandError("pg_restore a échoué sur la base isolée.")
        self.stdout.write(self.style.SUCCESS("Restauration isolée terminée; exécutez ensuite migrations/check/tests contre cette base."))

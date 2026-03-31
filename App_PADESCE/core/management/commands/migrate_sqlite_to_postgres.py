from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from App_PADESCE.core.db_migration import DatabaseCopyIntegrityError, copy_database_contents


class Command(BaseCommand):
    help = "Cree le schema PostgreSQL puis copie toutes les donnees de SQLite vers PostgreSQL."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--source",
            default="db.sqlite3",
            help="Chemin vers la base SQLite source (par defaut: db.sqlite3).",
        )
        parser.add_argument(
            "--target",
            default="default",
            help="Alias Django de la base PostgreSQL cible (par defaut: default).",
        )
        parser.add_argument(
            "--model",
            action="append",
            dest="model_labels",
            help="Limiter la copie a certains modeles (app_label.modelname). Repetable.",
        )
        parser.add_argument(
            "--exclude-table",
            action="append",
            dest="exclude_tables",
            help="Exclure une table cible precise. Repetable.",
        )
        parser.add_argument("--batch-size", type=int, default=1000, help="Taille des lots de copie.")
        parser.add_argument("--skip-migrate", action="store_true", help="N'execute pas les migrations sur PostgreSQL.")
        parser.add_argument("--skip-flush", action="store_true", help="Ne vide pas la base cible avant import.")
        parser.add_argument("--no-verify", action="store_true", help="Desactive la verification des comptes par table.")

    def handle(self, *args, **options) -> None:
        target_alias = options["target"]
        if target_alias not in settings.DATABASES:
            raise CommandError(f"Alias de base inconnu: {target_alias}")

        target_connection = connections[target_alias]
        if target_connection.vendor != "postgresql":
            raise CommandError(
                "La base cible doit etre PostgreSQL. Configurez DB_ENGINE=postgresql, "
                "DATABASE_URL ou POSTGRES_* avant d'executer cette commande."
            )

        source_path = Path(options["source"]).expanduser()
        if not source_path.is_absolute():
            source_path = Path.cwd() / source_path
        source_path = source_path.resolve(strict=False)
        if not source_path.exists():
            raise CommandError(f"Base SQLite source introuvable: {source_path}")

        source_alias = "sqlite_migration_source"
        self._register_sqlite_source(alias=source_alias, source_path=source_path, target_alias=target_alias)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Migration SQLite -> PostgreSQL"))
        self.stdout.write(f"Source SQLite : {source_path}")
        self.stdout.write(f"Cible PostgreSQL : alias '{target_alias}'")

        if not options["skip_migrate"]:
            self.stdout.write("Application des migrations PostgreSQL...")
            call_command(
                "migrate",
                database=target_alias,
                interactive=False,
                verbosity=max(options["verbosity"] - 1, 0),
            )

        try:
            result = copy_database_contents(
                source_alias=source_alias,
                target_alias=target_alias,
                model_labels=options.get("model_labels"),
                exclude_tables=options.get("exclude_tables"),
                batch_size=options["batch_size"],
                flush_target=not options["skip_flush"],
                verify_counts=not options["no_verify"],
            )
        except DatabaseCopyIntegrityError as exc:
            raise CommandError(str(exc)) from exc
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        finally:
            connections[source_alias].close()

        self.stdout.write("")
        self.stdout.write(f"Tables videes: {result.flush_statements}")
        self.stdout.write(f"Sequences recalees: {result.sequence_statements}")

        if result.skipped_tables and options["verbosity"] > 1:
            self.stdout.write("Tables ignorees: " + ", ".join(sorted(set(result.skipped_tables))))

        for item in result.model_results:
            self.stdout.write(
                f"- {item.model_label} [{item.table_name}] : "
                f"{item.inserted}/{item.source_count} lignes copiees"
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Migration terminee: {result.inserted} lignes chargees dans PostgreSQL."
            )
        )
        if options["no_verify"]:
            self.stdout.write(self.style.WARNING("Verification des comptes desactivee."))
        else:
            self.stdout.write(self.style.SUCCESS("Verification des comptes: OK."))

    def _register_sqlite_source(self, *, alias: str, source_path: Path, target_alias: str) -> None:
        base_config = settings.DATABASES[target_alias].copy()
        base_config.update(
            {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(source_path),
                "USER": "",
                "PASSWORD": "",
                "HOST": "",
                "PORT": "",
                "OPTIONS": {},
                "CONN_MAX_AGE": 0,
                "CONN_HEALTH_CHECKS": False,
                "ATOMIC_REQUESTS": False,
                "AUTOCOMMIT": True,
                "TIME_ZONE": None,
                "TEST": {},
            }
        )
        if alias in connections.databases:
            connections[alias].close()
        connections.databases[alias] = base_config

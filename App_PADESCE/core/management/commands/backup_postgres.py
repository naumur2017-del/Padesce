from django.core.management.base import BaseCommand, CommandError

from App_PADESCE.core.postgres_backup import NativeBackupError, create_native_backup


class Command(BaseCommand):
    help = "Crée un backup PostgreSQL natif pg_dump au format personnalisé."

    def handle(self, *args, **options):
        try:
            result = create_native_backup()
        except NativeBackupError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Backup PostgreSQL validé : {result['path'].name}"))
        self.stdout.write(f"SHA-256 : {result['checksum']}")

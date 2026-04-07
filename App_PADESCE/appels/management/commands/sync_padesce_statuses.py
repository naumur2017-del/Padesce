from django.core.management.base import BaseCommand
from django.db import transaction

from App_PADESCE.appels.models import Appel, derive_padesce_status


class Command(BaseCommand):
    help = "Recalcule les statuts PADESCE a partir des reponses au formulaire et des audios."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche les changements sans les sauvegarder.",
        )
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            help="Inclut aussi les lignes PADESCE inactives.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        include_inactive = options["include_inactive"]

        queryset = Appel.objects.all() if include_inactive else Appel.objects.filter(is_active=True)
        rows = list(queryset.select_related("answers", "satisfaction_apprenant").order_by("id"))

        transitions: dict[tuple[str, str], int] = {}
        to_update: list[Appel] = []

        for appel in rows:
            previous_status = appel.status
            new_status = derive_padesce_status(appel)
            if new_status == previous_status:
                continue
            transitions[(previous_status, new_status)] = transitions.get((previous_status, new_status), 0) + 1
            appel.status = new_status
            to_update.append(appel)

        self.stdout.write("=== Synchronisation des statuts PADESCE ===")
        self.stdout.write(f"Lignes inspectees : {len(rows)}")
        self.stdout.write(f"Lignes a corriger : {len(to_update)}")
        for (old_status, new_status), total in sorted(transitions.items()):
            self.stdout.write(f"  - {old_status} -> {new_status}: {total}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run termine: aucune ligne n'a ete modifiee."))
            return

        if not to_update:
            self.stdout.write(self.style.SUCCESS("Aucune correction necessaire."))
            return

        with transaction.atomic():
            Appel.objects.bulk_update(to_update, ["status", "updated_at"])

        self.stdout.write(self.style.SUCCESS(f"{len(to_update)} ligne(s) PADESCE ont ete mises a jour."))

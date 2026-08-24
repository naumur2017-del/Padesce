import json

from django.core.management.base import BaseCommand

from App_PADESCE.core.media_integrity import audit_media_integrity


class Command(BaseCommand):
    help = "Audite les références médias sans modifier fichiers ni données."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        report = audit_media_integrity()
        if options["json"]:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
            return
        self.stdout.write(f"Fichiers présents : {report['files_count']}")
        self.stdout.write(f"Références DB : {report['referenced_count']}")
        self.stdout.write(f"Références absentes : {len(report['missing_references'])}")
        self.stdout.write(f"Fichiers orphelins : {len(report['orphan_files'])}")

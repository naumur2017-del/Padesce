import hashlib
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Command(BaseCommand):
    help = "Archive MEDIA_ROOT sans supprimer de fichier."

    def handle(self, *args, **options):
        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            raise CommandError("MEDIA_ROOT est introuvable.")
        output_dir = Path(settings.BASE_DIR) / "backups" / "media"
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive = output_dir / f"padesce-media-{stamp}.tar.gz"
        file_count = 0
        total_size = 0
        with tarfile.open(archive, "w:gz") as tar:
            for path in media_root.rglob("*"):
                if path.is_file():
                    tar.add(path, arcname=path.relative_to(media_root))
                    file_count += 1
                    total_size += path.stat().st_size
        checksum = _sha256(archive)
        archive.with_suffix(".tar.gz.sha256").write_text(f"{checksum}  {archive.name}\n")
        self.stdout.write(self.style.SUCCESS(f"Archive média validée : {archive.name}"))
        self.stdout.write(f"Fichiers : {file_count}; octets : {total_size}; SHA-256 : {checksum}")

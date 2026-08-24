"""Sauvegarde PostgreSQL native, séparée de l'export SQLite historique."""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.conf import settings


class NativeBackupError(RuntimeError):
    """Erreur sûre à afficher sans révéler les identifiants de la base."""


def _backup_dir() -> Path:
    configured = str(os.getenv("PADESCE_NATIVE_BACKUP_DIR", "") or "").strip()
    path = Path(configured) if configured else Path(settings.BASE_DIR) / "backups" / "postgres"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _connection_env() -> tuple[list[str], dict[str, str]]:
    database_url = str(os.getenv("DATABASE_URL", "") or "").strip()
    if database_url:
        parsed = urlparse(database_url)
        if parsed.scheme not in {"postgres", "postgresql"} or not parsed.path.lstrip("/"):
            raise NativeBackupError("DATABASE_URL PostgreSQL invalide.")
        args = ["--host", parsed.hostname or "localhost", "--port", str(parsed.port or 5432)]
        if parsed.username:
            args.extend(["--username", unquote(parsed.username)])
        args.append(unquote(parsed.path.lstrip("/")))
        password = unquote(parsed.password or "")
    else:
        name = str(os.getenv("POSTGRES_DB", "") or "").strip()
        if not name:
            raise NativeBackupError("Configuration PostgreSQL absente.")
        args = [
            "--host",
            str(os.getenv("POSTGRES_HOST", "localhost") or "localhost"),
            "--port",
            str(os.getenv("POSTGRES_PORT", "5432") or "5432"),
            "--username",
            str(os.getenv("POSTGRES_USER", "") or ""),
            name,
        ]
        password = str(os.getenv("POSTGRES_PASSWORD", "") or "")
    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password
    return args, env


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_native_backup() -> dict[str, object]:
    directory = _backup_dir()
    lock_path = directory / ".backup.lock"
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise NativeBackupError("Un backup PostgreSQL est déjà en cours.") from exc

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    final_path = directory / f"padesce-postgres-{timestamp}.dump"
    try:
        args, env = _connection_env()
        with tempfile.NamedTemporaryFile(dir=directory, suffix=".partial", delete=False) as temp:
            temp_path = Path(temp.name)
        command = [
            "pg_dump",
            "--format=custom",
            "--compress=9",
            "--no-owner",
            "--file",
            str(temp_path),
            *args,
        ]
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=3600)
        if result.returncode != 0:
            temp_path.unlink(missing_ok=True)
            raise NativeBackupError("pg_dump a échoué; aucun backup natif n'a été validé.")
        if not temp_path.exists() or temp_path.stat().st_size == 0:
            raise NativeBackupError("Le fichier pg_dump généré est vide ou absent.")
        temp_path.replace(final_path)
        checksum = sha256(final_path)
        checksum_path = final_path.with_suffix(".dump.sha256")
        checksum_path.write_text(f"{checksum}  {final_path.name}\n", encoding="utf-8")
        return {"path": final_path, "checksum": checksum, "size": final_path.stat().st_size}
    finally:
        os.close(lock_fd)
        lock_path.unlink(missing_ok=True)


def purge_native_backups(retention_days: int) -> list[str]:
    """Conserve toujours le plus récent backup natif validé."""
    files = sorted(
        _backup_dir().glob("padesce-postgres-*.dump"), key=lambda item: item.stat().st_mtime
    )
    if len(files) < 2:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    deleted = []
    for path in files[:-1]:
        if datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc) < cutoff:
            path.unlink()
            path.with_suffix(".dump.sha256").unlink(missing_ok=True)
            deleted.append(path.name)
    return deleted

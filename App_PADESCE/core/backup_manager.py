"""
backup_manager.py – Backup PostgreSQL → SQLite avec suivi de progression.

Chaque job tourne dans un thread daemon et met à jour un dictionnaire
en mémoire. L'historique est persisté dans backups/history.json.
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from django.conf import settings

from App_PADESCE.core import huggingface_sync

# ---------------------------------------------------------------------------
# État en mémoire (jobs actifs / récents)
# ---------------------------------------------------------------------------

_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()
MIN_BACKUP_RETENTION_DAYS = 14
MAX_BACKUP_RETENTION_DAYS = 30
DEFAULT_BACKUP_RETENTION_DAYS = 30
_BACKUP_FILENAME_RE = re.compile(r"^backup_(\d{8}_\d{6})\.sqlite3$")


# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------


def _backup_dir() -> Path:
    d = Path(settings.BASE_DIR) / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _history_file() -> Path:
    return _backup_dir() / "history.json"


# ---------------------------------------------------------------------------
# Historique persisté
# ---------------------------------------------------------------------------


def load_history() -> list[dict]:
    f = _history_file()
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_history(history: list[dict]) -> None:
    _history_file().write_text(
        json.dumps(history[:200], ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _append_history(entry: dict) -> None:
    history = load_history()
    history.insert(0, entry)
    _save_history(history)


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------


def get_job(job_id: str) -> dict | None:
    with _lock:
        return dict(_jobs[job_id]) if job_id in _jobs else None


def get_history_entry(job_id: str) -> dict | None:
    for entry in load_history():
        if entry.get("id") == job_id:
            return entry
    return None


def get_latest_history_entry() -> dict | None:
    history = load_history()
    return history[0] if history else None


def resolve_backup_retention_days(retention_days: Any = None) -> int:
    raw_value = retention_days
    if raw_value in (None, ""):
        raw_value = getattr(settings, "BACKUP_RETENTION_DAYS", DEFAULT_BACKUP_RETENTION_DAYS)
    try:
        days = int(str(raw_value).strip())
    except (TypeError, ValueError):
        days = DEFAULT_BACKUP_RETENTION_DAYS
    return max(MIN_BACKUP_RETENTION_DAYS, min(MAX_BACKUP_RETENTION_DAYS, days))


def _backup_created_at(backup_path: Path) -> datetime | None:
    match = _BACKUP_FILENAME_RE.match(backup_path.name)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def purge_old_backups(retention_days: Any = None) -> dict[str, Any]:
    resolved_retention_days = resolve_backup_retention_days(retention_days)
    cutoff = datetime.now() - timedelta(days=resolved_retention_days)
    deleted_files: list[str] = []

    for backup_path in _backup_dir().glob("backup_*.sqlite3"):
        created_at = _backup_created_at(backup_path)
        if created_at is None or created_at >= cutoff:
            continue
        try:
            backup_path.unlink()
            deleted_files.append(backup_path.name)
        except OSError:
            continue

    deleted_set = set(deleted_files)
    cleaned_history = []
    removed_history_entries = 0
    for entry in load_history():
        backup_file = str(entry.get("backup_file", "") or "").strip()
        if backup_file in deleted_set:
            removed_history_entries += 1
            continue

        backup_created_at = _backup_created_at(Path(backup_file)) if backup_file else None
        if backup_created_at and backup_created_at < cutoff:
            removed_history_entries += 1
            continue

        cleaned_history.append(entry)

    _save_history(cleaned_history)

    return {
        "retention_days": resolved_retention_days,
        "deleted_files": deleted_files,
        "deleted_count": len(deleted_files),
        "history_deleted_count": removed_history_entries,
    }


def start_backup(
    triggered_by: str = "manual",
    retention_days: int | None = None,
    sync_huggingface: bool | None = None,
    require_huggingface: bool | None = None,
) -> str:
    job_id = uuid.uuid4().hex
    resolved_retention_days = resolve_backup_retention_days(retention_days)
    resolved_sync_huggingface = huggingface_sync.resolve_sync_enabled(sync_huggingface)
    resolved_require_huggingface = huggingface_sync.resolve_sync_required(
        require_huggingface,
        enabled=resolved_sync_huggingface,
    )
    with _lock:
        _jobs[job_id] = {
            "id": job_id,
            "status": "pending",
            "progress": 0,
            "message": "Initialisation...",
            "started_at": datetime.now().isoformat(),
            "triggered_by": triggered_by,
            "backup_file": None,
            "file_size": None,
            "tables_count": None,
            "retention_days": resolved_retention_days,
            "purged_backups": [],
            "sync_huggingface": resolved_sync_huggingface,
            "require_huggingface": resolved_require_huggingface,
            "huggingface": huggingface_sync.initial_status(
                enabled=resolved_sync_huggingface,
                required=resolved_require_huggingface,
            ),
            "finished_at": None,
            "error": None,
        }
    thread = threading.Thread(target=_run_backup, args=(job_id,), daemon=True)
    thread.start()
    return job_id


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------


def _update(job_id: str, **kwargs: Any) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)


def _pg_type_to_sqlite(pg_type: str) -> str:
    t = pg_type.lower()
    if any(x in t for x in ("int", "serial", "bigint", "smallint")):
        return "INTEGER"
    if any(x in t for x in ("float", "double", "numeric", "decimal", "real", "money")):
        return "REAL"
    if "bool" in t:
        return "INTEGER"
    if any(x in t for x in ("bytea", "blob")):
        return "BLOB"
    return "TEXT"


def _coerce(value: Any) -> Any:
    """Convertit les types Python non-natifs SQLite."""
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str, bytes)):
        return value
    return str(value)


# ---------------------------------------------------------------------------
# Moteur principal
# ---------------------------------------------------------------------------


def _run_backup(job_id: str) -> None:
    backup_path: Path | None = None
    started_at = _jobs[job_id]["started_at"]

    try:
        _update(job_id, status="running", progress=5, message="Connexion à la base de données...")

        db_cfg = settings.DATABASES.get("default", {})
        engine = db_cfg.get("ENGINE", "")

        if "postgresql" not in engine and "postgis" not in engine:
            # Fallback SQLite → copie directe
            _run_sqlite_copy(job_id, started_at)
            return

        # ------------------------------------------------------------------ #
        # Import psycopg2 lazily pour ne pas planter si absent en dev SQLite  #
        # ------------------------------------------------------------------ #
        try:
            import psycopg2  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError(
                "psycopg2 est requis pour le backup PostgreSQL. "
                "Installez-le via: pip install psycopg2-binary"
            ) from exc

        conn_kwargs: dict[str, Any] = {}
        if db_cfg.get("NAME"):
            conn_kwargs["dbname"] = db_cfg["NAME"]
        if db_cfg.get("USER"):
            conn_kwargs["user"] = db_cfg["USER"]
        if db_cfg.get("PASSWORD"):
            conn_kwargs["password"] = db_cfg["PASSWORD"]
        if db_cfg.get("HOST"):
            conn_kwargs["host"] = db_cfg["HOST"]
        if db_cfg.get("PORT"):
            conn_kwargs["port"] = str(db_cfg["PORT"])

        # OPTIONS (ex. sslmode)
        for k, v in db_cfg.get("OPTIONS", {}).items():
            conn_kwargs[k] = v

        pg_conn = psycopg2.connect(**conn_kwargs)
        pg_cur = pg_conn.cursor()

        _update(job_id, progress=10, message="Récupération de la liste des tables...")

        pg_cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )
        tables: list[str] = [row[0] for row in pg_cur.fetchall()]

        if not tables:
            raise RuntimeError("Aucune table trouvée dans le schéma 'public'.")

        _update(
            job_id,
            progress=12,
            message=f"{len(tables)} tables détectées. Création du fichier SQLite...",
        )

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = _backup_dir() / f"backup_{ts}.sqlite3"
        sq_conn = sqlite3.connect(str(backup_path))
        sq_conn.execute("PRAGMA journal_mode=WAL")
        sq_conn.execute("PRAGMA synchronous=NORMAL")
        sq_cur = sq_conn.cursor()

        total = len(tables)
        errors: list[str] = []

        for idx, table in enumerate(tables):
            progress = 12 + int((idx / total) * 80)
            _update(
                job_id,
                progress=progress,
                message=f"Export table {table} ({idx + 1}/{total})...",
            )

            try:
                # Colonnes + types
                pg_cur.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (table,),
                )
                col_info = pg_cur.fetchall()
                if not col_info:
                    continue

                col_names = [c[0] for c in col_info]
                col_defs = ", ".join(f'"{c[0]}" {_pg_type_to_sqlite(c[1])}' for c in col_info)

                sq_cur.execute(f'DROP TABLE IF EXISTS "{table}"')
                sq_cur.execute(f'CREATE TABLE "{table}" ({col_defs})')

                pg_cur.execute(f'SELECT * FROM "{table}"')
                placeholders = ", ".join(["?"] * len(col_names))
                insert_sql = f'INSERT INTO "{table}" VALUES ({placeholders})'

                while True:
                    batch = pg_cur.fetchmany(1000)
                    if not batch:
                        break
                    sq_cur.executemany(
                        insert_sql,
                        [tuple(_coerce(v) for v in row) for row in batch],
                    )

                sq_conn.commit()

            except Exception as exc:
                errors.append(f"{table}: {exc}")
                sq_conn.rollback()

        sq_conn.close()
        pg_cur.close()
        pg_conn.close()

        _finalize_backup(
            job_id,
            started_at,
            backup_path,
            tables_count=len(tables),
            errors=errors,
            success_message="Backup terminé avec succès.",
            partial_message=f"Backup partiel ({len(errors)} erreur(s)).",
        )

    except Exception as exc:
        finished_at = datetime.now().isoformat()
        _update(
            job_id,
            status="error",
            progress=0,
            message=f"Erreur: {exc}",
            finished_at=finished_at,
            error=str(exc),
        )
        _append_history(
            {
                "id": job_id,
                "status": "error",
                "started_at": started_at,
                "finished_at": finished_at,
                "triggered_by": _jobs.get(job_id, {}).get("triggered_by", "unknown"),
                "error": str(exc),
            }
        )
        if backup_path and backup_path.exists():
            try:
                backup_path.unlink()
            except OSError:
                pass


def _run_sqlite_copy(job_id: str, started_at: str) -> None:
    """Copie directe si le backend est SQLite (environnement de dev)."""
    _update(job_id, progress=30, message="Copie de la base SQLite locale...")
    source = Path(settings.BASE_DIR) / "db.sqlite3"
    if not source.exists():
        raise FileNotFoundError("db.sqlite3 introuvable (backend SQLite).")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = _backup_dir() / f"backup_{ts}.sqlite3"
    shutil.copy2(str(source), str(backup_path))

    _finalize_backup(
        job_id,
        started_at,
        backup_path,
        tables_count=None,
        errors=[],
        success_message="Copie SQLite terminée.",
        partial_message="Copie SQLite partielle.",
    )


def _finalize_backup(
    job_id: str,
    started_at: str,
    backup_path: Path,
    *,
    tables_count: int | None,
    errors: list[str],
    success_message: str,
    partial_message: str,
) -> None:
    file_size = backup_path.stat().st_size
    purge_summary = purge_old_backups(_jobs[job_id]["retention_days"])
    purged_backups = purge_summary["deleted_files"]
    huggingface_status = _sync_huggingface(
        job_id,
        started_at,
        backup_path,
        tables_count,
        file_size,
        errors,
    )
    hf_error = (
        str(huggingface_status.get("error") or "")
        if huggingface_status.get("status") == "error"
        else ""
    )

    status = "success" if not errors else "partial"
    message = success_message if not errors else partial_message
    final_errors = list(errors)

    if purged_backups:
        message += f" {len(purged_backups)} ancien(s) backup(s) supprimé(s)."

    if huggingface_status.get("status") == "success":
        message += " Hugging Face mis a jour."
    elif hf_error:
        if _jobs[job_id]["require_huggingface"]:
            status = "partial"
            final_errors.append(f"Hugging Face: {hf_error}")
            message += f" Synchronisation Hugging Face echouee: {hf_error}"
        else:
            message += f" Avertissement Hugging Face: {hf_error}"
    elif huggingface_status.get("status") == "skipped" and _jobs[job_id]["sync_huggingface"]:
        message += f" Hugging Face ignore: {huggingface_status.get('message')}"

    finished_at = datetime.now().isoformat()
    error_text = "; ".join(final_errors) if final_errors else None
    entry = {
        "id": job_id,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "triggered_by": _jobs[job_id]["triggered_by"],
        "backup_file": backup_path.name,
        "file_size": file_size,
        "tables_count": tables_count,
        "retention_days": purge_summary["retention_days"],
        "purged_backups": purged_backups,
        "huggingface": huggingface_status,
        "error": error_text,
    }
    if tables_count is None:
        entry.pop("tables_count")

    _update(
        job_id,
        status=status,
        progress=100,
        message=message,
        finished_at=finished_at,
        backup_file=backup_path.name,
        file_size=file_size,
        tables_count=tables_count,
        retention_days=purge_summary["retention_days"],
        purged_backups=purged_backups,
        huggingface=huggingface_status,
        error=error_text,
    )
    _append_history(entry)


def _sync_huggingface(
    job_id: str,
    started_at: str,
    backup_path: Path,
    tables_count: int | None,
    file_size: int,
    errors: list[str],
) -> dict[str, Any]:
    huggingface_status = _jobs[job_id]["huggingface"]
    if not _jobs[job_id]["sync_huggingface"]:
        return huggingface_status

    if errors:
        return huggingface_sync.mark_skipped(
            huggingface_status,
            "Synchronisation ignoree car le backup est partiel.",
        )

    running_status = huggingface_sync.mark_running(huggingface_status)
    _update(
        job_id,
        progress=94,
        message="Synchronisation Hugging Face...",
        huggingface=running_status,
    )
    synced_status = huggingface_sync.sync_sqlite_backup_to_huggingface(
        backup_path,
        backup_file=backup_path.name,
        job_id=job_id,
        started_at=started_at,
        triggered_by=_jobs[job_id]["triggered_by"],
        tables_count=tables_count,
        file_size=file_size,
        status=running_status,
    )
    _update(job_id, progress=98, huggingface=synced_status)
    return synced_status

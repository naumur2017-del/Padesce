"""
backup_manager.py – Backup PostgreSQL → SQLite avec suivi de progression.

Chaque job tourne dans un thread daemon et met à jour un dictionnaire
en mémoire. L'historique est persisté dans backups/history.json.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from django.conf import settings

# ---------------------------------------------------------------------------
# État en mémoire (jobs actifs / récents)
# ---------------------------------------------------------------------------

_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


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


def start_backup(triggered_by: str = "manual") -> str:
    job_id = uuid.uuid4().hex
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

        file_size = backup_path.stat().st_size
        finished_at = datetime.now().isoformat()
        status = "success" if not errors else "partial"
        msg = (
            "Backup terminé avec succès."
            if not errors
            else f"Backup partiel ({len(errors)} erreur(s))."
        )

        _update(
            job_id,
            status=status,
            progress=100,
            message=msg,
            finished_at=finished_at,
            backup_file=backup_path.name,
            file_size=file_size,
            tables_count=len(tables),
            error="; ".join(errors) if errors else None,
        )
        _append_history(
            {
                "id": job_id,
                "status": status,
                "started_at": started_at,
                "finished_at": finished_at,
                "triggered_by": _jobs[job_id]["triggered_by"],
                "backup_file": backup_path.name,
                "file_size": file_size,
                "tables_count": len(tables),
                "error": "; ".join(errors) if errors else None,
            }
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

    file_size = backup_path.stat().st_size
    finished_at = datetime.now().isoformat()
    _update(
        job_id,
        status="success",
        progress=100,
        message="Copie SQLite terminée.",
        finished_at=finished_at,
        backup_file=backup_path.name,
        file_size=file_size,
    )
    _append_history(
        {
            "id": job_id,
            "status": "success",
            "started_at": started_at,
            "finished_at": finished_at,
            "triggered_by": _jobs[job_id]["triggered_by"],
            "backup_file": backup_path.name,
            "file_size": file_size,
        }
    )

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

from django.conf import settings


DEFAULT_SPACE_REPO_ID = "JackBrayan17/padesce-bot"
DEFAULT_SPACE_REPO_TYPE = "space"
DEFAULT_SPACE_DB_PATH = "db.sqlite3"
DEFAULT_SPACE_META_PATH = "db_metadata.json"
DEFAULT_SPACE_URL = "https://jackbrayan17-padesce-bot.hf.space"


def bool_from_value(value: Any, default: bool = False) -> bool:
    if value in (None, ""):
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on", "enabled"}:
        return True
    if normalized in {"0", "false", "no", "off", "disabled"}:
        return False
    return default


def resolve_sync_enabled(value: Any = None) -> bool:
    if value not in (None, ""):
        return bool_from_value(value)
    return bool(getattr(settings, "HUGGINGFACE_BACKUP_SYNC_ENABLED", False))


def resolve_sync_required(value: Any = None, *, enabled: bool) -> bool:
    if value not in (None, ""):
        return bool_from_value(value)
    return bool(getattr(settings, "HUGGINGFACE_BACKUP_SYNC_REQUIRED", False) and enabled)


def initial_status(*, enabled: bool, required: bool) -> dict[str, Any]:
    repo_id = _setting("HUGGINGFACE_SPACE_REPO_ID", DEFAULT_SPACE_REPO_ID)
    return {
        "enabled": enabled,
        "required": required,
        "status": "pending" if enabled else "skipped",
        "repo_id": repo_id,
        "repo_type": _setting("HUGGINGFACE_SPACE_REPO_TYPE", DEFAULT_SPACE_REPO_TYPE),
        "revision": _setting("HUGGINGFACE_SPACE_REVISION", "main"),
        "path_in_repo": _setting("HUGGINGFACE_SPACE_DB_PATH", DEFAULT_SPACE_DB_PATH),
        "metadata_path": _setting("HUGGINGFACE_SPACE_META_PATH", DEFAULT_SPACE_META_PATH),
        "space_url": _setting("HUGGINGFACE_SPACE_URL", DEFAULT_SPACE_URL),
        "started_at": None,
        "finished_at": None,
        "commit_url": None,
        "metadata_commit_url": None,
        "quick_check": None,
        "message": "Synchronisation Hugging Face non demandee." if not enabled else "",
        "error": None,
    }


def mark_skipped(status: dict[str, Any], message: str) -> dict[str, Any]:
    updated = dict(status)
    updated.update(
        {
            "status": "skipped",
            "message": message,
            "finished_at": _now_iso(),
        }
    )
    return updated


def mark_running(status: dict[str, Any]) -> dict[str, Any]:
    updated = dict(status)
    updated.update(
        {
            "status": "running",
            "started_at": _now_iso(),
            "message": "Upload de la base SQLite vers Hugging Face...",
            "error": None,
        }
    )
    return updated


def sync_sqlite_backup_to_huggingface(
    backup_path: Path,
    *,
    backup_file: str,
    job_id: str,
    started_at: str,
    triggered_by: str,
    tables_count: int | None,
    file_size: int,
    status: dict[str, Any],
) -> dict[str, Any]:
    if not status.get("enabled"):
        return mark_skipped(status, "Synchronisation Hugging Face non demandee.")

    running_status = mark_running(status)
    try:
        repo_id = str(running_status["repo_id"]).strip()
        token = _token()
        if not repo_id:
            raise RuntimeError("HUGGINGFACE_SPACE_REPO_ID non configure.")
        if not token:
            raise RuntimeError("HUGGINGFACE_TOKEN ou HF_TOKEN non configure.")

        quick_check = evaluate_sqlite_backup(backup_path)
        if not quick_check["ok"]:
            raise RuntimeError(f"Controle SQLite echoue: {quick_check['result']}")

        try:
            from huggingface_hub import HfApi  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError(
                "huggingface_hub est requis pour publier le backup vers Hugging Face."
            ) from exc

        api = HfApi()
        revision = str(running_status.get("revision") or "main").strip() or None
        commit_message = _commit_message(backup_file)
        upload_result = api.upload_file(
            path_or_fileobj=str(backup_path),
            path_in_repo=str(running_status["path_in_repo"]),
            repo_id=repo_id,
            repo_type=str(running_status["repo_type"]),
            revision=revision,
            token=token,
            commit_message=commit_message,
        )

        metadata_commit_url = None
        metadata_path = str(running_status.get("metadata_path") or "").strip()
        if metadata_path:
            metadata_file = _write_metadata_file(
                {
                    "job_id": job_id,
                    "backup_file": backup_file,
                    "source": _setting("HUGGINGFACE_BACKUP_SOURCE_URL", "https://call.naumur.com"),
                    "started_at": started_at,
                    "synced_at": _now_iso(),
                    "triggered_by": triggered_by,
                    "repo_id": repo_id,
                    "path_in_repo": running_status["path_in_repo"],
                    "file_size": file_size,
                    "tables_count": tables_count,
                    "quick_check": quick_check,
                }
            )
            try:
                metadata_upload_result = api.upload_file(
                    path_or_fileobj=str(metadata_file),
                    path_in_repo=metadata_path,
                    repo_id=repo_id,
                    repo_type=str(running_status["repo_type"]),
                    revision=revision,
                    token=token,
                    commit_message=f"Update backup metadata for {backup_file}",
                )
                metadata_commit_url = _stringify_upload_result(metadata_upload_result)
            finally:
                metadata_file.unlink(missing_ok=True)

        finished_at = _now_iso()
        return {
            **running_status,
            "status": "success",
            "finished_at": finished_at,
            "commit_url": _stringify_upload_result(upload_result),
            "metadata_commit_url": metadata_commit_url,
            "quick_check": quick_check,
            "message": "Base Hugging Face mise a jour.",
            "error": None,
        }
    except Exception as exc:
        return {
            **running_status,
            "status": "error",
            "finished_at": _now_iso(),
            "message": "Echec de la synchronisation Hugging Face.",
            "error": str(exc),
        }


def evaluate_sqlite_backup(backup_path: Path) -> dict[str, Any]:
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup introuvable: {backup_path}")

    uri = f"{backup_path.resolve().as_uri()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        quick_check_result = str(conn.execute("PRAGMA quick_check").fetchone()[0])
        tables_count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]
        page_count = conn.execute("PRAGMA page_count").fetchone()[0]
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]

    return {
        "ok": quick_check_result.lower() == "ok",
        "result": quick_check_result,
        "tables_count": tables_count,
        "page_count": page_count,
        "page_size": page_size,
        "checked_at": _now_iso(),
    }


def _setting(name: str, default: str = "") -> str:
    value = getattr(settings, name, None)
    if value in (None, ""):
        value = os.getenv(name, default)
    return str(value or "").strip()


def _token() -> str:
    if hasattr(settings, "HUGGINGFACE_TOKEN") or hasattr(settings, "HF_TOKEN"):
        configured = getattr(settings, "HUGGINGFACE_TOKEN", "") or getattr(settings, "HF_TOKEN", "")
        return str(configured or "").strip()
    return str(os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN") or "").strip()


def _commit_message(backup_file: str) -> str:
    prefix = _setting("HUGGINGFACE_BACKUP_COMMIT_PREFIX", "Update PADESCE SQLite backup")
    return f"{prefix}: {backup_file}"


def _write_metadata_file(payload: dict[str, Any]) -> Path:
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        prefix="padesce-hf-backup-",
        encoding="utf-8",
        delete=False,
    )
    with handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return Path(handle.name)


def _stringify_upload_result(result: Any) -> str:
    if result is None:
        return ""
    commit_url = getattr(result, "commit_url", None)
    if commit_url:
        return str(commit_url)
    return str(result)


def _now_iso() -> str:
    return datetime.now().isoformat()

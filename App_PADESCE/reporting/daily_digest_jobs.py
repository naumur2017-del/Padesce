from __future__ import annotations

import logging
import json
import threading
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from django.conf import settings

from App_PADESCE.reporting.app_report import send_daily_digest_email

logger = logging.getLogger(__name__)

_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()
_MAX_JOBS = 50


def _jobs_file() -> Path:
    directory = Path(settings.BASE_DIR) / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "daily_digest_jobs.json"


def _load_jobs_from_disk() -> None:
    path = _jobs_file()
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if isinstance(data, dict):
        _jobs.update({str(key): value for key, value in data.items() if isinstance(value, dict)})


def _save_jobs_to_disk() -> None:
    path = _jobs_file()
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(_jobs, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _serialize_date(value: date) -> str:
    return value.isoformat()


def _prune_jobs() -> None:
    if len(_jobs) <= _MAX_JOBS:
        return
    removable = sorted(
        _jobs.values(),
        key=lambda item: str(item.get("started_at") or ""),
    )
    for job in removable[: max(0, len(_jobs) - _MAX_JOBS)]:
        _jobs.pop(str(job.get("id")), None)


def _update_job(job_id: str, **values: Any) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(values)
            _save_jobs_to_disk()


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        if job_id not in _jobs:
            _load_jobs_from_disk()
        job = _jobs.get(job_id)
        return dict(job) if job else None


def start_daily_digest(
    start_date: date,
    end_date: date,
    *,
    backup_job_id: str = "",
    backup_error: str = "",
    recipients: str | None = None,
    triggered_by: str = "scheduled/github-actions",
) -> str:
    job_id = uuid.uuid4().hex
    now = datetime.now().isoformat()
    with _lock:
        _jobs[job_id] = {
            "id": job_id,
            "status": "pending",
            "message": "Digest quotidien en attente de traitement.",
            "started_at": now,
            "finished_at": None,
            "triggered_by": triggered_by,
            "start_date": _serialize_date(start_date),
            "end_date": _serialize_date(end_date),
            "backup_job_id": backup_job_id,
            "backup_error": backup_error,
            "recipients": recipients or "",
            "result": None,
            "error": None,
        }
        _prune_jobs()
        _save_jobs_to_disk()

    thread = threading.Thread(target=_run_daily_digest, args=(job_id,), daemon=True)
    thread.start()
    return job_id


def _run_daily_digest(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return

    _update_job(job_id, status="running", message="Generation et envoi du digest quotidien.")
    try:
        result = send_daily_digest_email(
            date.fromisoformat(str(job["start_date"])),
            date.fromisoformat(str(job["end_date"])),
            backup_job_id=str(job.get("backup_job_id") or ""),
            backup_error=str(job.get("backup_error") or ""),
            recipients=str(job.get("recipients") or "") or None,
        )
    except Exception as exc:  # pragma: no cover - defensive guard for background workers
        logger.exception("Daily digest job %s failed", job_id)
        _update_job(
            job_id,
            status="error",
            message="Le digest quotidien a echoue.",
            finished_at=datetime.now().isoformat(),
            result=None,
            error=str(exc),
        )
        return

    ok = bool(result.get("ok"))
    detail = str(result.get("detail") or result.get("error") or "")
    _update_job(
        job_id,
        status="success" if ok else "error",
        message=detail or ("Digest quotidien envoye." if ok else "Le digest quotidien a echoue."),
        finished_at=datetime.now().isoformat(),
        result=result,
        error="" if ok else detail,
    )

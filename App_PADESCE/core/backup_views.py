"""
backup_views.py – Vues Django pour le tableau de bord de backup.

Endpoints:
  GET  /backup/                           → page de backup (superadmin)
  POST /backup/api/start/                 → démarre un backup, retourne {job_id}
  GET  /backup/api/status/<job_id>/      → progression JSON
  POST /backup/api/trigger/              → déclenchement automatique (token)
  GET  /backup/download/<filename>/      → télécharge un fichier SQLite
  POST /backup/delete/<filename>/        → supprime un fichier de backup
"""

from __future__ import annotations

import re

from django.conf import settings
from django.http import FileResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from App_PADESCE.core import backup_manager, huggingface_sync
from App_PADESCE.core.access import require_superadmin_access

# Only allow safe filenames: letters, digits, underscores, hyphens, dots
_SAFE_FILENAME_RE = re.compile(r"^[\w\-\.]+\.sqlite3$")

# ---------------------------------------------------------------------------
# Page principale
# ---------------------------------------------------------------------------


@require_superadmin_access
def backup_dashboard(request):
    history = backup_manager.load_history()
    return render(request, "core/backup_dashboard.html", {"history": history})


# ---------------------------------------------------------------------------
# API – démarrage manuel
# ---------------------------------------------------------------------------


@require_superadmin_access
@require_POST
def backup_start(request):
    triggered_by = getattr(request.user, "username", "admin")
    sync_huggingface = _request_bool(
        request,
        "X-HuggingFace-Sync",
        "sync_huggingface",
        default=getattr(settings, "HUGGINGFACE_BACKUP_SYNC_ENABLED", False),
    )
    require_huggingface = _request_bool(
        request,
        "X-HuggingFace-Required",
        "require_huggingface",
        default=getattr(settings, "HUGGINGFACE_BACKUP_SYNC_REQUIRED", False),
    )
    job_id = backup_manager.start_backup(
        triggered_by=triggered_by,
        sync_huggingface=sync_huggingface,
        require_huggingface=require_huggingface,
    )
    return JsonResponse(
        {
            "job_id": job_id,
            "sync_huggingface": sync_huggingface,
            "require_huggingface": require_huggingface,
        }
    )


# ---------------------------------------------------------------------------
# API – progression
# ---------------------------------------------------------------------------


@require_superadmin_access
@require_GET
def backup_status(request, job_id: str):
    job = backup_manager.get_job(job_id)
    if job is None:
        return JsonResponse({"error": "Job introuvable."}, status=404)
    return JsonResponse(job)


# ---------------------------------------------------------------------------
# API – déclenchement automatique (GitHub Actions / cron)
# ---------------------------------------------------------------------------


@csrf_exempt
@require_POST
def backup_trigger(request):
    """Déclenche un backup via un token partagé avec GitHub Actions."""
    is_valid, error_response = _validate_backup_trigger_token(request)
    if not is_valid:
        return error_response

    raw_retention_days = request.headers.get("X-Backup-Retention-Days", "") or request.POST.get(
        "retention_days", ""
    )
    retention_days = backup_manager.resolve_backup_retention_days(raw_retention_days)
    sync_huggingface = _request_bool(
        request,
        "X-HuggingFace-Sync",
        "sync_huggingface",
        default=getattr(settings, "HUGGINGFACE_BACKUP_SYNC_ENABLED", False),
    )
    require_huggingface = _request_bool(
        request,
        "X-HuggingFace-Required",
        "require_huggingface",
        default=getattr(settings, "HUGGINGFACE_BACKUP_SYNC_REQUIRED", False),
    )
    job_id = backup_manager.start_backup(
        triggered_by="scheduled/github-actions",
        retention_days=retention_days,
        sync_huggingface=sync_huggingface,
        require_huggingface=require_huggingface,
    )
    return JsonResponse(
        {
            "job_id": job_id,
            "message": "Backup démarré.",
            "retention_days": retention_days,
            "sync_huggingface": sync_huggingface,
            "require_huggingface": require_huggingface,
        }
    )


def _validate_backup_trigger_token(request):
    expected_token: str = getattr(settings, "BACKUP_TRIGGER_TOKEN", "")
    if not expected_token:
        return False, JsonResponse({"error": "BACKUP_TRIGGER_TOKEN non configuré."}, status=503)

    provided_token = request.headers.get("X-Backup-Token", "") or request.POST.get("token", "")
    provided_token = str(provided_token or "").strip()

    if not provided_token or provided_token != expected_token:
        return False, JsonResponse({"error": "Token invalide ou manquant."}, status=403)

    return True, None


def _request_bool(request, header_name: str, field_name: str, *, default: bool) -> bool:
    raw_value = request.headers.get(header_name, "")
    if raw_value in (None, ""):
        raw_value = request.POST.get(field_name, "")
    return huggingface_sync.bool_from_value(raw_value, default)


@require_GET
def backup_trigger_status(request, job_id: str):
    is_valid, error_response = _validate_backup_trigger_token(request)
    if not is_valid:
        return error_response

    job = backup_manager.get_job(job_id)
    if job is not None:
        return JsonResponse(job)

    history_entry = backup_manager.get_history_entry(job_id)
    if history_entry is not None:
        return JsonResponse(history_entry)

    return JsonResponse({"error": "Job introuvable."}, status=404)


# ---------------------------------------------------------------------------
# Téléchargement d'un fichier backup
# ---------------------------------------------------------------------------


@require_superadmin_access
@require_GET
def backup_download(request, filename: str):
    """Sert le fichier SQLite en téléchargement forcé (Content-Disposition: attachment)."""
    if not _SAFE_FILENAME_RE.match(filename):
        return JsonResponse({"error": "Nom de fichier invalide."}, status=400)

    backup_path = backup_manager._backup_dir() / filename
    if not backup_path.exists():
        return JsonResponse({"error": "Fichier introuvable."}, status=404)

    return FileResponse(
        open(backup_path, "rb"),  # noqa: WPS515 – FileResponse closes the file
        as_attachment=True,
        filename=filename,
        content_type="application/x-sqlite3",
    )


# ---------------------------------------------------------------------------
# Suppression d'un fichier backup
# ---------------------------------------------------------------------------


@require_superadmin_access
@require_POST
def backup_delete(request, filename: str):
    """Supprime un fichier SQLite de backup et met à jour l'historique."""
    if not _SAFE_FILENAME_RE.match(filename):
        return JsonResponse({"error": "Nom de fichier invalide."}, status=400)

    backup_path = backup_manager._backup_dir() / filename
    if not backup_path.exists():
        return JsonResponse({"error": "Fichier introuvable."}, status=404)

    backup_path.unlink()
    # Remove entry from history
    history = backup_manager.load_history()
    history = [e for e in history if e.get("backup_file") != filename]
    backup_manager._save_history(history)

    return JsonResponse({"deleted": filename})

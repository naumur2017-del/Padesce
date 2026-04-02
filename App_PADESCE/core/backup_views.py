"""
backup_views.py – Vues Django pour le tableau de bord de backup.

Endpoints:
  GET  /backup/                        → page de backup (superadmin)
  POST /backup/api/start/              → démarre un backup, retourne {job_id}
  GET  /backup/api/status/<job_id>/   → progression JSON
  POST /backup/api/trigger/            → déclenchement automatique (token)
"""

from __future__ import annotations

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from App_PADESCE.core import backup_manager
from App_PADESCE.core.access import require_superadmin_access

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
    job_id = backup_manager.start_backup(triggered_by=triggered_by)
    return JsonResponse({"job_id": job_id})


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
    """
    Endpoint protégé par un token secret.
    Appelé chaque jour à 17h par le workflow GitHub Actions backup-daily.yml.

    Header attendu : X-Backup-Token: <BACKUP_TRIGGER_TOKEN>
    """
    expected_token: str = getattr(settings, "BACKUP_TRIGGER_TOKEN", "")
    if not expected_token:
        return JsonResponse({"error": "BACKUP_TRIGGER_TOKEN non configuré."}, status=503)

    provided_token = request.headers.get("X-Backup-Token", "") or request.POST.get("token", "")

    if not provided_token or provided_token != expected_token:
        return JsonResponse({"error": "Token invalide ou manquant."}, status=403)

    job_id = backup_manager.start_backup(triggered_by="scheduled/github-actions")
    return JsonResponse({"job_id": job_id, "message": "Backup démarré."})

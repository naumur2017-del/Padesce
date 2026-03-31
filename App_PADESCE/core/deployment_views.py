from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from App_PADESCE.core.access import require_superadmin_access
from App_PADESCE.core.deployment_live import live_status_payload
from App_PADESCE.core.gandi_deploy import (
    deployment_config_summary,
    get_active_run,
    iter_recent_runs,
    load_run_state,
    make_run_id,
    save_runtime_config,
)
from App_PADESCE.core.deployment_reporting import load_history, load_history_entry, load_report


def _start_pipeline(mode: str) -> tuple[str, subprocess.Popen[bytes]]:
    run_id = make_run_id()
    base_dir = Path(settings.BASE_DIR)
    command = [
        sys.executable,
        str(base_dir / "manage.py"),
        "gandi_deploy",
        "--run-id",
        run_id,
        "--mode",
        mode,
    ]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        command,
        cwd=str(base_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    return run_id, process


def _recent_runs_summary() -> list[dict]:
    runs: list[dict] = []
    seen_ids: set[str] = set()
    for payload in iter_recent_runs():
        run_id = str(payload.get("id", "") or "").strip()
        if not run_id:
            continue
        seen_ids.add(run_id)
        runs.append(
            {
                "id": run_id,
                "mode": payload.get("mode", ""),
                "status": payload.get("status", ""),
                "started_at": payload.get("started_at", ""),
                "completed_at": payload.get("completed_at", ""),
                "progress_pct": payload.get("progress_pct", 0),
                "summary": payload.get("summary", {}),
                "error": payload.get("error", ""),
            }
        )
    for payload in load_history():
        run_id = str(payload.get("id", "") or "").strip()
        if not run_id or run_id in seen_ids:
            continue
        runs.append(
            {
                "id": run_id,
                "mode": payload.get("mode", ""),
                "status": payload.get("status", ""),
                "started_at": payload.get("started_at", ""),
                "completed_at": payload.get("completed_at", ""),
                "progress_pct": 100 if payload.get("completed_at") else 0,
                "summary": payload.get("summary", {}),
                "error": payload.get("error", ""),
            }
        )
    runs.sort(key=lambda item: item.get("started_at", ""), reverse=True)
    return runs


def _archived_run_payload(run_id: str) -> dict:
    entry = load_history_entry(run_id)
    if entry:
        started_at = entry.get("started_at", "")
        completed_at = entry.get("completed_at", "")
        error = str(entry.get("error", "") or "")
        logs = [
            {
                "at": completed_at or started_at,
                "level": "info",
                "message": "Le fichier detaille du run n'est plus disponible. Affichage du resume archive.",
            }
        ]
        if error:
            logs.append(
                {
                    "at": completed_at or started_at,
                    "level": "error",
                    "message": error,
                }
            )
        verification = {"errors": [error]} if error else {"errors": []}
        live_refresh = entry.get("live_refresh", {}) or {}
        if live_refresh:
            verification["live_refresh"] = live_refresh
        return {
            "id": str(entry.get("id", "") or run_id),
            "mode": entry.get("mode", ""),
            "status": entry.get("status", "archive"),
            "progress_pct": 100 if completed_at else 0,
            "started_at": started_at,
            "updated_at": completed_at or started_at,
            "completed_at": completed_at,
            "current_step": None,
            "summary": entry.get("summary", {}) or {},
            "diff": {
                "additions": [],
                "modifications": [],
                "deletions": [],
                "remote_untracked": [],
            },
            "verification": verification,
            "report": {
                "json_path": entry.get("json_path", ""),
                "markdown_path": entry.get("markdown_path", ""),
                "xlsx_path": entry.get("xlsx_path", ""),
            },
            "error": error,
            "logs": logs,
            "steps": [],
            "archived": True,
            "archived_notice": "Resume archive charge car le detail complet du run n'est plus disponible.",
        }
    return {
        "id": str(run_id or "").strip() or "run-inconnu",
        "mode": "",
        "status": "archive",
        "progress_pct": 0,
        "started_at": "",
        "updated_at": "",
        "completed_at": "",
        "current_step": None,
        "summary": {},
        "diff": {
            "additions": [],
            "modifications": [],
            "deletions": [],
            "remote_untracked": [],
        },
        "verification": {"errors": []},
        "report": {},
        "error": "",
        "logs": [
            {
                "at": "",
                "level": "warning",
                "message": "Ce run n'a pas ete retrouve dans les fichiers actifs ni dans l'historique archive.",
            }
        ],
        "steps": [],
        "archived": True,
        "archived_notice": "Aucun detail complet n'est disponible pour ce run, mais la page reste utilisable.",
    }


@require_superadmin_access
@require_GET
def deployment_dashboard(request):
    config = deployment_config_summary()
    active_run = get_active_run()
    recent_runs = _recent_runs_summary()
    initial_run = active_run or (recent_runs[0] if recent_runs else None)
    context = {
        "config": config,
        "active_run": active_run,
        "recent_runs": recent_runs,
        "initial_run_json": json.dumps(initial_run or {}, ensure_ascii=True),
    }
    return render(request, "core/deployment_dashboard.html", context)


@require_superadmin_access
@require_POST
def deployment_start(request):
    active_run = get_active_run()
    if active_run:
        return JsonResponse(
            {
                "ok": False,
                "error": "Un deploiement est deja en cours.",
                "run_id": active_run.get("id", ""),
            },
            status=409,
        )

    mode = str(request.POST.get("mode") or "deploy").strip().lower()
    if mode not in {"preview", "deploy"}:
        return JsonResponse({"ok": False, "error": "Mode invalide."}, status=400)

    run_id, process = _start_pipeline(mode)
    return JsonResponse(
        {
            "ok": True,
            "run_id": run_id,
            "pid": process.pid,
            "mode": mode,
        }
    )


@require_superadmin_access
@require_GET
def deployment_status(request, run_id: str):
    payload = load_run_state(run_id)
    if not payload:
        payload = load_report(run_id)
    if not payload:
        payload = _archived_run_payload(run_id)
    return JsonResponse({"ok": True, "run": payload})


@require_GET
def deployment_live_status(request):
    response = JsonResponse(live_status_payload(Path(settings.BASE_DIR)))
    response["Cache-Control"] = "no-store, no-cache, max-age=0"
    return response


@require_superadmin_access
@require_POST
def deployment_config_save(request):
    save_runtime_config(
        {
            "GANDI_SFTP_HOST": request.POST.get("host", ""),
            "GANDI_SFTP_PORT": request.POST.get("port", ""),
            "GANDI_SFTP_DOMAIN": request.POST.get("domain", ""),
            "GANDI_SFTP_USERNAME": request.POST.get("username", ""),
            "GANDI_SFTP_TOKEN": request.POST.get("token", ""),
            "GANDI_SFTP_REMOTE_PATH": request.POST.get("remote_path", ""),
            "GANDI_DEPLOY_VERIFY_URL": request.POST.get("verify_url", ""),
            "GANDI_DEPLOY_LOCAL_ROOT": request.POST.get("local_root", ""),
            "GANDI_DEPLOY_INCLUDE_PATHS": request.POST.get("include_paths", ""),
        }
    )
    return JsonResponse(
        {
            "ok": True,
            "config": deployment_config_summary(),
        }
    )

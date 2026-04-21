from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import requests
from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

CHAT_HISTORY_SESSION_KEY = "padesce_chat_history"
CHAT_HISTORY_LIMIT = 24
DEFAULT_RAG_API_URL = "https://koulou-chatnaumur.hf.space/agent/run"
DEFAULT_RAG_TIMEOUT_SECONDS = 120.0


class RemoteRagError(Exception):
    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


def _rag_api_url() -> str:
    configured_url = str(os.getenv("PADESCE_RAG_API_URL", DEFAULT_RAG_API_URL) or "").strip()
    return configured_url.rstrip("/") or DEFAULT_RAG_API_URL


def _rag_timeout_seconds() -> float:
    raw_timeout = str(os.getenv("PADESCE_RAG_API_TIMEOUT", DEFAULT_RAG_TIMEOUT_SECONDS)).strip()
    try:
        timeout = float(raw_timeout)
    except ValueError:
        return DEFAULT_RAG_TIMEOUT_SECONDS
    return max(1.0, timeout)


def _remote_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    token = str(os.getenv("PADESCE_RAG_API_TOKEN", "") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_session_history(request) -> list[dict[str, str]]:
    raw_history = request.session.get(CHAT_HISTORY_SESSION_KEY, [])
    history: list[dict[str, str]] = []
    for item in raw_history:
        role = str(item.get("role", "") or "").strip()
        content = str(item.get("content", "") or "").strip()
        if role in {"user", "assistant"} and content:
            history.append({"role": role, "content": content})
    return history[-CHAT_HISTORY_LIMIT:]


def _save_session_history(request, history: list[dict[str, str]]) -> None:
    request.session[CHAT_HISTORY_SESSION_KEY] = history[-CHAT_HISTORY_LIMIT:]
    request.session.modified = True


def _append_history_entry(
    request,
    *,
    user_message: str,
    assistant_message: str,
) -> None:
    history = _get_session_history(request)
    history.extend(
        [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_message},
        ]
    )
    _save_session_history(request, history)


def _remote_filename(payload: dict[str, Any]) -> str | None:
    explicit_filename = str(payload.get("file_name") or payload.get("filename") or "").strip()
    if explicit_filename:
        return os.path.basename(explicit_filename)

    generated_file = str(payload.get("fichier") or payload.get("fichier_genere") or "").strip()
    if generated_file:
        return os.path.basename(generated_file)

    return None


def _response_text(payload: dict[str, Any]) -> str:
    for key in ("reponse", "response", "answer", "message"):
        value = payload.get(key)
        if value:
            return str(value)
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _normalize_remote_payload(payload: dict[str, Any]) -> dict[str, Any]:
    response_text = _response_text(payload)
    return {
        "response": response_text,
        "filename": _remote_filename(payload),
        "download_url": payload.get("download_url") or None,
        "mode": "remote-api",
    }


def _call_remote_rag(message: str) -> dict[str, Any]:
    try:
        response = requests.post(
            _rag_api_url(),
            json={"prompt": message, "verbose": False},
            headers=_remote_headers(),
            timeout=_rag_timeout_seconds(),
        )
    except requests.Timeout as exc:
        raise RemoteRagError(
            "Le service RAG distant ne répond pas dans le délai configuré.",
            status_code=504,
        ) from exc
    except requests.RequestException as exc:
        raise RemoteRagError(
            "Le service RAG distant est indisponible pour le moment.",
            status_code=503,
        ) from exc

    if response.status_code >= 400:
        detail = response.text.strip()
        if len(detail) > 300:
            detail = f"{detail[:300]}..."
        message = f"Le service RAG distant a retourné une erreur HTTP {response.status_code}."
        if detail:
            message = f"{message} {detail}"
        raise RemoteRagError(message, status_code=502)

    try:
        payload = response.json()
    except ValueError as exc:
        raise RemoteRagError(
            "Le service RAG distant a retourné une réponse non JSON.",
            status_code=502,
        ) from exc

    if not isinstance(payload, dict):
        raise RemoteRagError(
            "Le service RAG distant a retourné un format inattendu.",
            status_code=502,
        )

    return payload


def _build_chat_payload(request, message: str) -> dict[str, Any]:
    remote_payload = _call_remote_rag(message)
    payload = _normalize_remote_payload(remote_payload)
    _append_history_entry(
        request,
        user_message=message,
        assistant_message=str(payload["response"]),
    )
    return payload


@csrf_exempt
@require_POST
def chat_query(request):
    """Point d'entrée de l'API REST pour le chat."""
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Charge utile JSON invalide."}, status=400)

    message = str(data.get("message", "") or "").strip()
    if not message:
        return JsonResponse({"error": "Message vide"}, status=400)

    try:
        payload = _build_chat_payload(request, message)
    except RemoteRagError as exc:
        logger.warning("Appel RAG distant impossible: %s", exc)
        return JsonResponse({"error": str(exc), "mode": "remote-api-error"}, status=exc.status_code)

    return JsonResponse(payload)


def download_export(request, filename):
    """Point de téléchargement pour les fichiers générés par l'agent local historique."""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise Http404("Fichier invalide")

    export_dir = Path(settings.BASE_DIR) / "exports"
    if not export_dir.exists():
        export_dir = Path.cwd() / "exports"

    file_path = export_dir / filename
    if not file_path.exists():
        raise Http404(f"Fichier {filename} introuvable")

    return FileResponse(file_path.open("rb"), as_attachment=True, filename=filename)

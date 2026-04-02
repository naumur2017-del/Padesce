from __future__ import annotations

import json
import logging
import os
import threading
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd
from django.conf import settings
from django.core.cache import cache
from django.http import FileResponse, Http404, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

CHAT_HISTORY_SESSION_KEY = "padesce_chat_history"
CHAT_HISTORY_LIMIT = 24
_AGENT_LOCK = threading.Lock()
_AGENT_RUNTIME: dict[str, Any] = {"initialized": False, "available": False, "error": ""}


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_text(value: str) -> str:
    return " ".join(_strip_accents(value).lower().split())


def _workbook_path() -> Path:
    candidates = [
        Path(settings.BASE_DIR) / "Decompte et facturation.xlsm",
        Path.cwd() / "Decompte et facturation.xlsm",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Le fichier Decompte et facturation.xlsm est introuvable.")


def _load_chat_workbook_frames() -> dict[str, pd.DataFrame]:
    workbook_path = _workbook_path()
    cache_key = f"chat-workbook::{workbook_path.stat().st_mtime_ns}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    frames = {
        "consolide": pd.read_excel(
            workbook_path,
            sheet_name="Consolidé",
            engine="openpyxl",
            usecols=[
                "Bénéficiaires",
                "Prestataire",
                "Région",
                "cohorte",
                "Classe",
                "Statut de la prestation",
                "Ville de la formation",
            ],
        ),
        "classes": pd.read_excel(
            workbook_path,
            sheet_name="Classes",
            engine="openpyxl",
            usecols=[
                "Prestation ID",
                "Nom du Prestataire",
                "Nom du beneficiaire",
                "Cohorte",
                "Statut de la prestation",
            ],
        ),
        "apprenants": pd.read_excel(
            workbook_path,
            sheet_name="Apprenants",
            engine="openpyxl",
            usecols=[
                "Nom_Beneficiaire",
                "Cohorte",
                "Statut Apprenant",
                "ID Prestation",
            ],
        ),
    }
    cache.set(cache_key, frames, timeout=60 * 60 * 12)
    return frames


def _format_number(value: int) -> str:
    return f"{int(value):,}".replace(",", " ")


def _format_distribution(title: str, counts: pd.Series, total: int) -> str:
    rows = ["| Valeur | Total |", "| --- | ---: |"]
    for label, count in counts.items():
        rows.append(f"| {label} | {_format_number(int(count))} |")
    table = "\n".join(rows)
    return (
        f"📊 {title}\n\n"
        f"{table}\n\n"
        f"Total analysé : **{_format_number(total)}** enregistrements."
    )


def _series_distribution(frame: pd.DataFrame, column: str) -> pd.Series:
    return (
        frame[column]
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .value_counts()
    )


def _count_unique(frame: pd.DataFrame, column: str) -> int:
    return int(
        frame[column]
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .nunique()
    )


def _local_chat_fallback(message: str) -> dict[str, Any] | None:
    normalized = _normalize_text(message)
    if not normalized:
        return None

    try:
        frames = _load_chat_workbook_frames()
    except Exception as exc:
        logger.exception("Impossible de charger les donnees locales du chat.")
        return {
            "response": (
                "⚠️ Le chat analytique n'a pas pu charger les données locales pour le moment. "
                f"Détail: {exc}"
            ),
            "filename": None,
            "mode": "fallback-error",
        }

    consolide = frames["consolide"]

    if any(token in normalized for token in ("repartition", "distribution", "repartition par")):
        dimension_map = [
            ("statut", "Statut de la prestation", "Répartition par statut de la prestation"),
            ("prestataire", "Prestataire", "Répartition par prestataire"),
            ("beneficiaire", "Bénéficiaires", "Répartition par bénéficiaire"),
            ("beneficiaire", "Bénéficiaires", "Répartition par bénéficiaire"),
            ("region", "Région", "Répartition par région"),
            ("cohorte", "cohorte", "Répartition par cohorte"),
            ("classe", "Classe", "Répartition par classe"),
            ("ville", "Ville de la formation", "Répartition par ville de formation"),
        ]
        for keyword, column, title in dimension_map:
            if keyword in normalized:
                counts = _series_distribution(consolide, column)
                if counts.empty:
                    return {
                        "response": f"🔍 Aucune donnée exploitable trouvée pour {title.lower()}.",
                        "filename": None,
                        "mode": "fallback",
                    }
                return {
                    "response": _format_distribution(title, counts.head(20), int(counts.sum())),
                    "filename": None,
                    "mode": "fallback",
                }

    if "combien" in normalized or "nombre" in normalized or "total" in normalized:
        metric_map = [
            ("prestataire", consolide, "Prestataire", "prestataires"),
            ("beneficiaire", consolide, "Bénéficiaires", "bénéficiaires"),
            ("cohorte", consolide, "cohorte", "cohortes"),
            ("classe", consolide, "Classe", "classes"),
            ("statut", consolide, "Statut de la prestation", "statuts"),
        ]
        for keyword, frame, column, label in metric_map:
            if keyword in normalized:
                total = _count_unique(frame, column)
                return {
                    "response": (
                        f"✅ Le décompte contient **{_format_number(total)} {label}** distincts "
                        f"sur la base de la colonne **{column}**."
                    ),
                    "filename": None,
                    "mode": "fallback",
                }

    if "liste" in normalized and "statut" in normalized:
        counts = _series_distribution(consolide, "Statut de la prestation")
        values = ", ".join(str(item) for item in counts.index.tolist())
        return {
            "response": f"📋 Statuts présents dans le décompte : **{values}**.",
            "filename": None,
            "mode": "fallback",
        }

    return None


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _initialize_agent_runtime() -> bool:
    if _AGENT_RUNTIME["initialized"]:
        return bool(_AGENT_RUNTIME["available"])

    env_candidates = [
        Path(settings.BASE_DIR) / ".env",
        Path(settings.BASE_DIR).parent.parent / ".env",
    ]
    for env_path in env_candidates:
        _load_env_file(env_path)

    if not os.getenv("ANTHROPIC_API_KEY"):
        _AGENT_RUNTIME.update(
            {
                "initialized": True,
                "available": False,
                "error": "ANTHROPIC_API_KEY absent: bascule automatique sur le moteur local.",
            }
        )
        return False

    try:
        from agent_padesceV2 import configure_memory, load_data, register_dataframes

        workbook_path = str(_workbook_path())
        configure_memory(enabled=True, max_conversations=8)
        register_dataframes(load_data(workbook_path))
        _AGENT_RUNTIME.update({"initialized": True, "available": True, "error": ""})
        logger.info("Agent PADESCE initialise avec succes.")
        return True
    except Exception as exc:
        logger.exception("Initialisation de l'agent PADESCE impossible.")
        _AGENT_RUNTIME.update(
            {
                "initialized": True,
                "available": False,
                "error": str(exc),
            }
        )
        return False


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


def _run_agent_with_session_memory(request, message: str) -> dict[str, Any]:
    from agent_padesceV2 import configure_memory, reset_memory, run_agent
    from agent_padesceV2.config import add_to_memory, get_memory

    history = _get_session_history(request)

    with _AGENT_LOCK:
        reset_memory()
        configure_memory(enabled=True, max_conversations=8)
        for item in history[-16:]:
            add_to_memory(item["role"], item["content"])
        result = run_agent(message, verbose=False)
        memory_snapshot = [
            {"role": str(item.get("role", "")), "content": str(item.get("content", ""))}
            for item in get_memory()
            if item.get("role") in {"user", "assistant"} and item.get("content")
        ]

    if memory_snapshot:
        _save_session_history(request, memory_snapshot)

    return result


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


def _build_chat_payload(request, message: str) -> dict[str, Any]:
    local_result = _local_chat_fallback(message)
    if local_result is not None:
        _append_history_entry(
            request,
            user_message=message,
            assistant_message=str(local_result["response"]),
        )
        return local_result

    if _initialize_agent_runtime():
        try:
            result = _run_agent_with_session_memory(request, message)
            response_text = result.get(
                "reponse", "Désolé, je n'ai pas pu formuler de réponse."
            )
            generated_file = result.get("fichier", "")
            if not _get_session_history(request) or _get_session_history(request)[-1]["content"] != response_text:
                _append_history_entry(
                    request,
                    user_message=message,
                    assistant_message=str(response_text),
                )
            return {
                "response": response_text,
                "filename": os.path.basename(generated_file) if generated_file else None,
                "mode": "agent",
            }
        except Exception:
            logger.exception("Execution de l'agent PADESCE impossible, bascule locale.")

    fallback_message = (
        "⚠️ Le moteur avancé du chat est momentanément indisponible. "
        "Je peux toutefois répondre aux questions analytiques courantes sur le décompte "
        "(répartition par statut, nombre de prestataires, cohortes, régions, etc.)."
    )
    if _AGENT_RUNTIME.get("error"):
        fallback_message += f"\n\nDétail technique: `{_AGENT_RUNTIME['error']}`"

    _append_history_entry(
        request,
        user_message=message,
        assistant_message=fallback_message,
    )
    return {"response": fallback_message, "filename": None, "mode": "fallback-unavailable"}


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

    payload = _build_chat_payload(request, message)
    return JsonResponse(payload)


def download_export(request, filename):
    """Point de téléchargement pour les fichiers générés par l'agent."""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise Http404("Fichier invalide")

    export_dir = Path(settings.BASE_DIR) / "exports"
    if not export_dir.exists():
        export_dir = Path.cwd() / "exports"

    file_path = export_dir / filename
    if not file_path.exists():
        raise Http404(f"Fichier {filename} introuvable")

    return FileResponse(file_path.open("rb"), as_attachment=True, filename=filename)

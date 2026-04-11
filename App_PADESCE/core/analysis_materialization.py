"""
Snapshots d'analyse persistés en base : évite de recalculer les agrégations
lourdes à chaque requête HTTP lorsque les données sources n'ont pas changé.
"""

from __future__ import annotations

import datetime
import hashlib
import logging
import os
from decimal import Decimal
from typing import Any

from django.db.models import Count, Max, Sum
from django.utils import timezone

from App_PADESCE.core.models import AppelOptimizationSnapshot, MaterializedDashboardPayload

logger = logging.getLogger(__name__)

# Durées de cache (secondes) — réutilise l’env analyse si non spécifié.
def _analysis_cache_timeout_seconds() -> int:
    return int(str(os.environ.get("PADESCE_ANALYSIS_CACHE_TIMEOUT", "300") or "300"))


def _appels_list_metrics_timeout_seconds() -> int:
    raw = os.environ.get("PADESCE_APPELS_LIST_METRICS_CACHE_TIMEOUT", "").strip()
    if raw:
        return int(str(raw or "300"))
    return _analysis_cache_timeout_seconds()


def appels_list_metrics_cache_timeout_seconds() -> int:
    return _appels_list_metrics_timeout_seconds()


def analysis_dashboard_cache_timeout_seconds() -> int:
    """Même fenêtre que le dashboard satisfaction (PADESCE_ANALYSIS_CACHE_TIMEOUT)."""
    return _analysis_cache_timeout_seconds()


APPELS_LIST_FILTER_QUERY_KEYS = (
    "status",
    "prestataire",
    "beneficiaire",
    "classe",
    "fenetre",
    "agent",
    "formulaire",
    "modified_by",
    "tracking_termine",
    "tracking_user",
    "taux_min",
    "date_from",
    "date_to",
    "q",
)


def _source_workbook_fingerprint(source_bundle: dict | None) -> str:
    if not source_bundle:
        return "none"
    src = source_bundle.get("source") or {}
    counts = source_bundle.get("counts") or {}
    parts = [
        str(src.get("path") or ""),
        str(src.get("modified_at") or ""),
        str(counts.get("apprenants") or ""),
        str(counts.get("classes") or ""),
    ]
    return "|".join(parts)


def _active_appels_fingerprint() -> str:
    from App_PADESCE.appels.models import Appel

    agg = Appel.objects.filter(is_active=True).aggregate(
        c=Count("id"),
        m=Max("updated_at"),
        s=Sum("id"),
    )
    m = agg["m"]
    m_str = m.isoformat() if m else ""
    return f"{agg['c'] or 0}:{m_str}:{agg['s'] or 0}"


def active_appels_fingerprint() -> str:
    """Empreinte des appels PADESCE actifs (invalidation liste / métriques)."""
    return _active_appels_fingerprint()


def workbook_source_fingerprint(source_bundle: dict | None) -> str:
    """Empreinte légère du classeur réseau (métadonnées)."""
    return _source_workbook_fingerprint(source_bundle)


def active_appel_formateur_fingerprint() -> str:
    from App_PADESCE.appels.models import AppelFormateur

    agg = AppelFormateur.objects.filter(is_active=True).aggregate(
        c=Count("id"),
        m=Max("updated_at"),
        s=Sum("id"),
    )
    m = agg["m"]
    m_str = m.isoformat() if m else ""
    return f"{agg['c'] or 0}:{m_str}:{agg['s'] or 0}"


def appels_list_metrics_cache_key(
    request,
    *,
    appels_data_fingerprint: str,
    source_workbook_fingerprint: str,
    hidden_class_labels: list[str],
) -> str:
    """Clé stable pour agrégats liste appels (hors pagination)."""
    hidden_blob = ",".join(sorted(str(x) for x in (hidden_class_labels or []) if str(x).strip()))
    hidden_h = hashlib.sha1(hidden_blob.encode("utf-8")).hexdigest()[:16]
    parts: list[str] = []
    for key in APPELS_LIST_FILTER_QUERY_KEYS:
        value = (request.GET.get(key) or "").strip()
        if value:
            parts.append(f"{key}={value}")
    filter_sig = "&".join(parts)
    return (
        f"padesce-appels-list-metrics:{appels_data_fingerprint}:"
        f"{source_workbook_fingerprint}:{hidden_h}:{filter_sig}"
    )


def formateurs_dashboard_cache_key(request) -> str:
    fp = active_appel_formateur_fingerprint()
    query = (request.GET.get("prestataire") or "").strip()
    query_b = (request.GET.get("beneficiaire") or "").strip()
    query_c = (request.GET.get("cohorte") or "").strip()
    return f"formateurs-dashboard:{fp}:p={query}:b={query_b}:c={query_c}"


def _optimization_snapshot_for_storage(snapshot: dict) -> dict:
    return {k: v for k, v in snapshot.items() if k != "source_bundle"}


def _merge_optimization_snapshot(stored: dict, source_bundle: dict | None) -> dict:
    return {**stored, "source_bundle": source_bundle}


def get_or_build_appel_optimization_snapshot() -> dict:
    """
    Retourne le snapshot de progression (page appels PADESCE), depuis la ligne
    singleton si empreintes appels + classeur inchangées, sinon recalcule et enregistre.
    """
    from App_PADESCE.appels.views import (
        _build_appel_class_progress_snapshot,
        _safe_build_padesce_source_index,
    )

    source_bundle = _safe_build_padesce_source_index()
    app_fp = _active_appels_fingerprint()
    src_fp = _source_workbook_fingerprint(source_bundle)

    row = AppelOptimizationSnapshot.get_singleton()
    if (
        row.appels_fingerprint == app_fp
        and row.source_fingerprint == src_fp
        and row.payload
    ):
        return _merge_optimization_snapshot(row.payload, source_bundle)

    snapshot = _build_appel_class_progress_snapshot(source_bundle)
    row.appels_fingerprint = app_fp
    row.source_fingerprint = src_fp
    row.payload = _optimization_snapshot_for_storage(snapshot)
    row.save(
        update_fields=["appels_fingerprint", "source_fingerprint", "payload", "updated_at"]
    )
    return snapshot


def materialized_dashboard_cache_key_hash(cache_key: str) -> str:
    return hashlib.sha256(cache_key.encode("utf-8")).hexdigest()


def _json_safe_value(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_safe_value(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_json_safe_value(v) for v in obj]
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    if isinstance(obj, datetime.time):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    return obj


def json_safe_materialized_payload(payload: dict) -> dict:
    return _json_safe_value(payload)


def load_materialized_dashboard_payload(cache_key: str) -> dict | None:
    digest = materialized_dashboard_cache_key_hash(cache_key)
    now = timezone.now()
    try:
        row = MaterializedDashboardPayload.objects.get(cache_key_hash=digest)
    except MaterializedDashboardPayload.DoesNotExist:
        return None
    if row.valid_until < now:
        row.delete()
        return None
    return row.payload


def save_materialized_dashboard_payload(
    cache_key: str, payload: dict, timeout_seconds: int
) -> None:
    digest = materialized_dashboard_cache_key_hash(cache_key)
    try:
        safe = json_safe_materialized_payload(payload)
    except (TypeError, ValueError) as exc:
        logger.warning("Payload dashboard non serialisable JSON, skip materialisation: %s", exc)
        return
    valid_until = timezone.now() + datetime.timedelta(seconds=max(1, int(timeout_seconds)))
    try:
        MaterializedDashboardPayload.objects.update_or_create(
            cache_key_hash=digest,
            defaults={"payload": safe, "valid_until": valid_until},
        )
        MaterializedDashboardPayload.objects.filter(valid_until__lt=timezone.now()).delete()
    except Exception as exc:
        logger.warning("Enregistrement payload dashboard matérialisé échoué: %s", exc)

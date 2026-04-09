import hashlib
from typing import Iterable

from django.core.cache import cache

PRESENCE_CONTROLS_CACHE_KEY = "presence_controls_v1"
VALID_MARKERS = {"PR", "AB"}


def _normalize_identifier(value: str) -> str:
    return str(value or "").strip().upper()


def _normalized_marker(value: str) -> str:
    marker = _normalize_identifier(value)
    return marker if marker in VALID_MARKERS else "AB"


def _simulate_controls(seed_value: str) -> dict:
    seed = _normalize_identifier(seed_value) or "UNKNOWN"
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    controls = []
    for index in range(4):
        controls.append("PR" if digest[index] % 5 else "AB")
    present_count = sum(1 for marker in controls if marker == "PR")
    taux = round((present_count / 4) * 100, 2)
    return {
        "c1": controls[0],
        "c2": controls[1],
        "c3": controls[2],
        "c4": controls[3],
        "taux_presence": taux,
    }


def get_presence_controls(apprenant_id: str, fallback_seed: str = "") -> dict:
    key = _normalize_identifier(apprenant_id)
    payload = cache.get(PRESENCE_CONTROLS_CACHE_KEY) or {}
    if key and key in payload:
        data = payload[key]
        return {
            "c1": _normalized_marker(data.get("c1")),
            "c2": _normalized_marker(data.get("c2")),
            "c3": _normalized_marker(data.get("c3")),
            "c4": _normalized_marker(data.get("c4")),
            "taux_presence": float(data.get("taux_presence") or 0),
        }
    return _simulate_controls(key or fallback_seed)


def upsert_presence_controls(entries: Iterable[dict]) -> int:
    payload = cache.get(PRESENCE_CONTROLS_CACHE_KEY) or {}
    updated = 0
    for entry in entries:
        key = _normalize_identifier(entry.get("apprenant_id"))
        if not key:
            continue
        c1 = _normalized_marker(entry.get("c1"))
        c2 = _normalized_marker(entry.get("c2"))
        c3 = _normalized_marker(entry.get("c3"))
        c4 = _normalized_marker(entry.get("c4"))
        taux_raw = entry.get("taux_presence")
        try:
            taux_value = float(taux_raw)
        except (TypeError, ValueError):
            taux_value = round((sum(1 for m in [c1, c2, c3, c4] if m == "PR") / 4) * 100, 2)
        payload[key] = {
            "c1": c1,
            "c2": c2,
            "c3": c3,
            "c4": c4,
            "taux_presence": taux_value,
        }
        updated += 1
    cache.set(PRESENCE_CONTROLS_CACHE_KEY, payload, timeout=None)
    return updated

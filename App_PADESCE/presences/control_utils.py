import hashlib
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from django.conf import settings
from django.core.cache import cache

try:
    from openpyxl import load_workbook
except Exception:  # pragma: no cover
    load_workbook = None

PRESENCE_CONTROLS_CACHE_KEY = "presence_controls_v1"
VALID_MARKERS = {"PR", "AB"}
CONTROL_KEYS = ("c1", "c2", "c3", "c4")
EXCEL_CONTROLS_XLSX = "fichier_concatene (1) 1 (1).xlsx"
EXCEL_CONTROLS_SHEET = "Donnees"


def _normalize_identifier(value: str) -> str:
    return str(value or "").strip().upper()


def _normalized_marker(value: str) -> str:
    marker = _normalize_identifier(value)
    return marker if marker in VALID_MARKERS else "AB"


def _normalize_control_type(value: str) -> str:
    normalized = _normalize_identifier(value)
    match = re.search(r"C([1-4])", normalized)
    if not match:
        return ""
    return f"c{match.group(1)}"


def _controls_xlsx_path() -> Path:
    return Path(settings.BASE_DIR) / "data" / EXCEL_CONTROLS_XLSX


def _excel_cache_token() -> tuple[str, float]:
    path = _controls_xlsx_path()
    if not path.exists():
        return (str(path), 0.0)
    return (str(path), path.stat().st_mtime)


@lru_cache(maxsize=2)
def _load_excel_presence_payload(_token: tuple[str, float]) -> dict[str, dict]:
    if load_workbook is None:
        return {}
    path = Path(_token[0])
    if not path.exists():
        return {}
    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except Exception:
        return {}
    try:
        ws = wb[EXCEL_CONTROLS_SHEET] if EXCEL_CONTROLS_SHEET in wb.sheetnames else wb.active
        payload: dict[str, dict] = {}
        for row in ws.iter_rows(min_row=2, values_only=True):
            apprenant_id = _normalize_identifier(row[1] if len(row) > 1 else "")
            if not apprenant_id:
                continue
            presence_marker = _normalized_marker(row[11] if len(row) > 11 else "")
            control_type = _normalize_control_type(row[39] if len(row) > 39 else "")
            if not control_type:
                continue
            current = payload.setdefault(apprenant_id, {})
            current[control_type] = presence_marker
        return payload
    except Exception:
        return {}
    finally:
        wb.close()


def _excel_controls_for(apprenant_id: str) -> dict:
    key = _normalize_identifier(apprenant_id)
    if not key:
        return {}
    payload = _load_excel_presence_payload(_excel_cache_token())
    return payload.get(key, {})


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
    excel_controls = _excel_controls_for(key)

    def _with_presence_meta(base_controls: dict, source: str) -> dict:
        merged = {
            "c1": _normalized_marker(base_controls.get("c1")),
            "c2": _normalized_marker(base_controls.get("c2")),
            "c3": _normalized_marker(base_controls.get("c3")),
            "c4": _normalized_marker(base_controls.get("c4")),
        }
        controls_found = []
        for control_key, control_value in excel_controls.items():
            if control_key not in CONTROL_KEYS:
                continue
            merged[control_key] = _normalized_marker(control_value)
            controls_found.append(control_key)
        present_count = sum(1 for control_key in CONTROL_KEYS if merged[control_key] == "PR")
        taux = round((present_count / 4) * 100, 2)
        found_set = set(controls_found)
        missing_set = [control_key for control_key in CONTROL_KEYS if control_key not in found_set]
        merged["taux_presence"] = taux
        merged["source"] = "excel" if found_set else source
        merged["excel_found"] = bool(found_set)
        merged["excel_complete"] = len(found_set) == 4
        merged["excel_controls_found"] = sorted(found_set)
        merged["excel_missing_controls"] = missing_set
        for control_key in CONTROL_KEYS:
            merged[f"{control_key}_from_excel"] = control_key in found_set
        return merged

    if key and key in payload:
        data = payload[key]
        return _with_presence_meta(
            {
                "c1": data.get("c1"),
                "c2": data.get("c2"),
                "c3": data.get("c3"),
                "c4": data.get("c4"),
            },
            source="cache",
        )
    return _with_presence_meta(_simulate_controls(key or fallback_seed), source="simulated")


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

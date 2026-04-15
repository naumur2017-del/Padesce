import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from django.conf import settings
from django.core.cache import cache
from django.db import OperationalError, ProgrammingError

from App_PADESCE.apprenants.models import Apprenant

try:
    from openpyxl import load_workbook
except Exception:  # pragma: no cover
    load_workbook = None

PRESENCE_CONTROLS_CACHE_KEY = "presence_controls_v1"
PRESENCE_CONTROLS_DB_SYNC_TOKEN_KEY = "presence_controls_db_sync_token_v1"
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


def _presence_from_controls(controls: dict | None) -> dict:
    controls = controls or {}
    values = {key: _normalized_marker(controls.get(key)) for key in CONTROL_KEYS}
    present_count = sum(1 for key in CONTROL_KEYS if values[key] == "PR")
    values["taux_presence"] = round((present_count / 4) * 100, 2)
    return values


def _default_presence() -> dict:
    return _presence_from_controls({"c1": "AB", "c2": "AB", "c3": "AB", "c4": "AB"})


def _sync_controls_from_excel_to_db(force: bool = False) -> None:
    token = _excel_cache_token()
    token_key = f"{token[0]}::{token[1]}"
    if not force and cache.get(PRESENCE_CONTROLS_DB_SYNC_TOKEN_KEY) == token_key:
        return

    payload = _load_excel_presence_payload(token)
    try:
        apprenants = list(Apprenant.objects.only("id", "code", "c1", "c2", "c3", "c4"))
    except (OperationalError, ProgrammingError):
        return

    to_update = []
    for apprenant in apprenants:
        controls = payload.get(_normalize_identifier(apprenant.code), {})
        normalized = _presence_from_controls(controls)
        has_changed = any(getattr(apprenant, key) != normalized[key] for key in CONTROL_KEYS)
        if not has_changed:
            continue
        for key in CONTROL_KEYS:
            setattr(apprenant, key, normalized[key])
        to_update.append(apprenant)

    if to_update:
        Apprenant.objects.bulk_update(to_update, list(CONTROL_KEYS), batch_size=1000)
    cache.set(PRESENCE_CONTROLS_DB_SYNC_TOKEN_KEY, token_key, timeout=None)


def get_presence_controls(apprenant_id: str, fallback_seed: str = "") -> dict:
    del fallback_seed
    _sync_controls_from_excel_to_db(force=False)
    key = _normalize_identifier(apprenant_id)

    if key:
        try:
            apprenant = (
                Apprenant.objects.only("c1", "c2", "c3", "c4").filter(code__iexact=key).first()
            )
        except (OperationalError, ProgrammingError):
            apprenant = None
        if apprenant is not None:
            from_db = _presence_from_controls(
                {
                    "c1": apprenant.c1,
                    "c2": apprenant.c2,
                    "c3": apprenant.c3,
                    "c4": apprenant.c4,
                }
            )
            from_db.update(
                {
                    "source": "database",
                    "excel_found": False,
                    "excel_complete": False,
                    "excel_controls_found": [],
                    "excel_missing_controls": list(CONTROL_KEYS),
                    "c1_from_excel": False,
                    "c2_from_excel": False,
                    "c3_from_excel": False,
                    "c4_from_excel": False,
                }
            )
            return from_db

    payload = cache.get(PRESENCE_CONTROLS_CACHE_KEY) or {}
    if key and key in payload:
        cached = _presence_from_controls(payload[key])
        cached.update(
            {
                "source": "cache",
                "excel_found": False,
                "excel_complete": False,
                "excel_controls_found": [],
                "excel_missing_controls": list(CONTROL_KEYS),
                "c1_from_excel": False,
                "c2_from_excel": False,
                "c3_from_excel": False,
                "c4_from_excel": False,
            }
        )
        return cached

    default_presence = _default_presence()
    default_presence.update(
        {
            "source": "default_ab",
            "excel_found": False,
            "excel_complete": False,
            "excel_controls_found": [],
            "excel_missing_controls": list(CONTROL_KEYS),
            "c1_from_excel": False,
            "c2_from_excel": False,
            "c3_from_excel": False,
            "c4_from_excel": False,
        }
    )
    return default_presence


def upsert_presence_controls(entries: Iterable[dict]) -> int:
    payload = cache.get(PRESENCE_CONTROLS_CACHE_KEY) or {}
    normalized_entries: dict[str, dict] = {}
    updated = 0
    for entry in entries:
        key = _normalize_identifier(entry.get("apprenant_id"))
        if not key:
            continue
        normalized = _presence_from_controls(
            {
                "c1": entry.get("c1"),
                "c2": entry.get("c2"),
                "c3": entry.get("c3"),
                "c4": entry.get("c4"),
            }
        )
        payload[key] = normalized
        normalized_entries[key] = normalized
        updated += 1
    cache.set(PRESENCE_CONTROLS_CACHE_KEY, payload, timeout=None)

    if normalized_entries:
        try:
            apprenants = list(Apprenant.objects.only("id", "code", "c1", "c2", "c3", "c4"))
            to_update = []
            for apprenant in apprenants:
                key = _normalize_identifier(apprenant.code)
                entry = normalized_entries.get(key)
                if not entry:
                    continue
                has_changed = any(
                    getattr(apprenant, field) != entry[field] for field in CONTROL_KEYS
                )
                if not has_changed:
                    continue
                for field in CONTROL_KEYS:
                    setattr(apprenant, field, entry[field])
                to_update.append(apprenant)
            if to_update:
                Apprenant.objects.bulk_update(to_update, list(CONTROL_KEYS), batch_size=1000)
        except (OperationalError, ProgrammingError):
            pass

    return updated

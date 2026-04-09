from __future__ import annotations

import logging
import unicodedata
from functools import lru_cache
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


def _clean(value) -> str:
    return str(value or "").strip()


def _norm_key(value) -> str:
    return _clean(value).casefold()


def _norm_name(value) -> str:
    text = _clean(value).casefold()
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    return " ".join("".join(ch for ch in normalized if not unicodedata.combining(ch)).split())


def _workbook_path() -> Path:
    relative = Path("data") / "rapport presence" / "rapport presence.xlsx"
    candidates = [
        Path(settings.BASE_DIR) / relative,
        Path(settings.BASE_DIR).parent / relative,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


@lru_cache(maxsize=1)
def _load_registry_cached(mtime: float):
    del mtime  # mtime is only used to invalidate cache entries.
    by_name: dict[str, str] = {}
    by_class_name: dict[tuple[str, str], str] = {}
    workbook = _workbook_path()
    try:
        import pandas as pd

        frame = pd.read_excel(workbook)
    except Exception:
        logger.exception("Unable to load apprenant registry workbook: %s", workbook)
        return {"by_name": by_name, "by_class_name": by_class_name}

    for _, row in frame.iterrows():
        apprenant_id = _clean(row.get("ApprenantID"))
        apprenant_name = _clean(row.get("Nom_Individu"))
        classe_id = _clean(row.get("Classe ID"))
        if not apprenant_id or not apprenant_name:
            continue
        name_key = _norm_name(apprenant_name)
        if not name_key:
            continue
        by_name.setdefault(name_key, apprenant_id)
        if classe_id:
            by_class_name.setdefault((_norm_key(classe_id), name_key), apprenant_id)

    return {"by_name": by_name, "by_class_name": by_class_name}


def get_apprenant_id_from_presence_report(apprenant_name: str = "", classe_code: str = "") -> str:
    workbook = _workbook_path()
    try:
        mtime = workbook.stat().st_mtime
    except OSError:
        logger.warning("Apprenant workbook not found: %s", workbook)
        return ""

    payload = _load_registry_cached(mtime)
    name_key = _norm_name(apprenant_name)
    if not name_key:
        return ""

    classe_key = _norm_key(classe_code)
    if classe_key:
        value = payload["by_class_name"].get((classe_key, name_key), "")
        if value:
            return value
    return payload["by_name"].get(name_key, "")

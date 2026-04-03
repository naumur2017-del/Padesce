from __future__ import annotations

import json
import math
import os
from pathlib import Path
from threading import Lock

from django.conf import settings

from App_PADESCE.appels.models import APPEL_ANSWER_QUESTION_FIELDS
from App_PADESCE.core.call_metrics import has_usable_phone

ANALYSIS_THRESHOLD_PERCENT = 25
ANALYSIS_EXCLUDED_USERNAMES = frozenset({"yanava"})
_MANUAL_EXCLUSIONS_LOCK = Lock()


def analysis_threshold_target(total: int) -> int:
    total = int(total or 0)
    if total <= 0:
        return 0
    return max(1, math.ceil(total * ANALYSIS_THRESHOLD_PERCENT / 100.0))


def analysis_threshold_label() -> str:
    return f"{ANALYSIS_THRESHOLD_PERCENT}%"


def normalize_analysis_username(value: object) -> str:
    return str(value or "").strip().casefold()


def is_excluded_analysis_username(value: object) -> bool:
    return normalize_analysis_username(value) in ANALYSIS_EXCLUDED_USERNAMES


def answer_done_by_excluded_user(*, answer=None, survey=None) -> bool:
    answer_user = getattr(getattr(answer, "modified_by", None), "username", "")
    survey_user = getattr(getattr(survey, "enqueteur", None), "username", "")
    return is_excluded_analysis_username(answer_user) or is_excluded_analysis_username(
        survey_user
    )


def appel_has_analysis_phone(appel) -> bool:
    return has_usable_phone(
        getattr(appel, "telephone1", ""),
        getattr(appel, "telephone2", ""),
    )


def _manual_exclusions_path() -> Path:
    configured_path = str(
        getattr(settings, "ANALYSIS_MANUAL_EXCLUSIONS_FILE", "") or ""
    ).strip()
    path = Path(configured_path or "logs/analysis/manual_exclusions.json")
    if not path.is_absolute():
        path = Path(settings.BASE_DIR) / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _normalize_manual_exclusions_payload(payload: object) -> dict[str, dict[str, bool]]:
    if not isinstance(payload, dict):
        return {"ids": {}, "codes": {}}
    ids_payload = payload.get("ids", {})
    codes_payload = payload.get("codes", {})
    ids = {
        str(key).strip(): bool(value)
        for key, value in dict(ids_payload or {}).items()
        if str(key).strip() and bool(value)
    }
    codes = {
        str(key).strip().casefold(): bool(value)
        for key, value in dict(codes_payload or {}).items()
        if str(key).strip() and bool(value)
    }
    return {"ids": ids, "codes": codes}


def _load_manual_exclusions() -> dict[str, dict[str, bool]]:
    path = _manual_exclusions_path()
    if not path.exists():
        return {"ids": {}, "codes": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"ids": {}, "codes": {}}
    return _normalize_manual_exclusions_payload(payload)


def _save_manual_exclusions(payload: dict[str, dict[str, bool]]) -> None:
    path = _manual_exclusions_path()
    normalized_payload = _normalize_manual_exclusions_payload(payload)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(normalized_payload, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    os.replace(temp_path, path)


def _appel_manual_exclusion_id(appel) -> str:
    return str(getattr(appel, "pk", "") or "").strip()


def _appel_manual_exclusion_code(appel) -> str:
    return str(getattr(appel, "code", "") or "").strip().casefold()


def appel_is_manually_excluded(appel) -> bool:
    appel_id = _appel_manual_exclusion_id(appel)
    appel_code = _appel_manual_exclusion_code(appel)
    with _MANUAL_EXCLUSIONS_LOCK:
        payload = _load_manual_exclusions()
    return bool(
        (appel_id and payload["ids"].get(appel_id))
        or (appel_code and payload["codes"].get(appel_code))
    )


def set_appel_manual_exclusion(appel, excluded: bool) -> bool:
    appel_id = _appel_manual_exclusion_id(appel)
    appel_code = _appel_manual_exclusion_code(appel)
    with _MANUAL_EXCLUSIONS_LOCK:
        payload = _load_manual_exclusions()
        if excluded:
            if appel_id:
                payload["ids"][appel_id] = True
            if appel_code:
                payload["codes"][appel_code] = True
        else:
            if appel_id:
                payload["ids"].pop(appel_id, None)
            if appel_code:
                payload["codes"].pop(appel_code, None)
        _save_manual_exclusions(payload)
    return bool(excluded)


def toggle_appel_manual_exclusion(appel) -> bool:
    return set_appel_manual_exclusion(
        appel,
        excluded=not appel_is_manually_excluded(appel),
    )


def appel_analysis_exclusion_reason(appel, *, answer=None, survey=None) -> str:
    if appel_is_manually_excluded(appel):
        return "Exclu manuellement"
    if not appel_has_analysis_phone(appel):
        return "Sans numero"
    if answer_done_by_excluded_user(answer=answer, survey=survey):
        return "Utilisateur yanava"
    return ""


def appel_is_analysis_eligible(appel, *, answer=None, survey=None) -> bool:
    return not appel_analysis_exclusion_reason(appel, answer=answer, survey=survey)


def answer_has_all_three_scores(answer) -> bool:
    if not answer:
        return False
    return all(getattr(answer, field, None) == 3 for field in APPEL_ANSWER_QUESTION_FIELDS)

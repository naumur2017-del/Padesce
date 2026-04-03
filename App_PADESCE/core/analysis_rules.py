from __future__ import annotations

import math

from App_PADESCE.appels.models import APPEL_ANSWER_QUESTION_FIELDS
from App_PADESCE.core.call_metrics import has_usable_phone

ANALYSIS_THRESHOLD_PERCENT = 25
ANALYSIS_EXCLUDED_USERNAMES = frozenset({"yanava"})


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


def appel_is_manually_excluded(appel) -> bool:
    return bool(getattr(appel, "exclude_from_analysis", False))


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

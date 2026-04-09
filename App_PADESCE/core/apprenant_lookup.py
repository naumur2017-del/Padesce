from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

from django.db.models import Q

from App_PADESCE.apprenants.models import Apprenant


def _clean(value) -> str:
    return str(value or "").strip()


def _normalize_key(value) -> str:
    return _clean(value).casefold()


def _normalize_name(value) -> str:
    text = _clean(value).casefold()
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    plain = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(plain.split())


def _normalize_phone(value) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _name_tokens(value) -> list[str]:
    return [token for token in re.split(r"\s+", _normalize_name(value)) if len(token) >= 3]


def _raw_class_codes_for_appel(appel) -> list[str]:
    try:
        survey = appel.satisfaction_apprenant
    except Exception:
        survey = None

    raw_candidates = [
        getattr(getattr(appel, "classe", None), "code", ""),
        getattr(appel, "classe_label", ""),
        getattr(getattr(survey, "classe", None), "code", ""),
    ]
    codes: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_candidates:
        code = _clean(raw_value)
        if not code or code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def _class_codes_for_appel(appel) -> list[str]:
    return [_normalize_key(code) for code in _raw_class_codes_for_appel(appel)]


def _apprenant_queryset_for_appels(appels) -> list[Apprenant]:
    code_values: set[str] = set()
    class_ids: set[int] = set()
    class_codes: set[str] = set()
    survey_apprenant_ids: set[int] = set()

    for appel in appels:
        code = _clean(getattr(appel, "code", ""))
        if code:
            code_values.add(code)
        if getattr(appel, "classe_id", None):
            class_ids.add(int(appel.classe_id))
        class_codes.update(_raw_class_codes_for_appel(appel))

        try:
            survey = appel.satisfaction_apprenant
        except Exception:
            survey = None
        if getattr(survey, "apprenant_id", None):
            survey_apprenant_ids.add(int(survey.apprenant_id))

    query = Q()
    if code_values:
        query |= Q(code__in=code_values)
    if class_ids:
        query |= Q(classe_id__in=class_ids)
    if class_codes:
        query |= Q(classe__code__in=class_codes)
    if survey_apprenant_ids:
        query |= Q(pk__in=survey_apprenant_ids)
    if not query:
        return []

    return list(
        Apprenant.objects.select_related("classe", "classe__prestation", "formation")
        .filter(query)
        .order_by("id")
    )


def _pick_by_class(candidates: list[Apprenant], class_codes: list[str]) -> Apprenant | None:
    if not candidates:
        return None
    if class_codes:
        for class_code in class_codes:
            for candidate in candidates:
                if _normalize_key(getattr(getattr(candidate, "classe", None), "code", "")) == class_code:
                    return candidate
    return candidates[0]


def _pick_partial_code(
    candidates: list[Apprenant],
    appel_code: str,
    class_codes: list[str],
) -> Apprenant | None:
    code_key = _normalize_key(appel_code)
    if not code_key or not candidates:
        return None
    partial_matches = [
        candidate
        for candidate in candidates
        if code_key in _normalize_key(getattr(candidate, "code", ""))
        or _normalize_key(getattr(candidate, "code", "")) in code_key
    ]
    return _pick_by_class(partial_matches, class_codes)


def _pick_flexible_name(
    candidates: list[Apprenant],
    appel_name: str,
    class_codes: list[str],
) -> Apprenant | None:
    tokens = _name_tokens(appel_name)
    if not tokens or not candidates:
        return None

    best_candidate: Apprenant | None = None
    best_score = 0
    best_has_class = False
    for candidate in candidates:
        candidate_name = _normalize_name(getattr(candidate, "nom_complet", ""))
        if not candidate_name:
            continue
        score = sum(1 for token in tokens if token in candidate_name)
        if score <= 0:
            continue
        has_class_match = (
            _normalize_key(getattr(getattr(candidate, "classe", None), "code", "")) in class_codes
            if class_codes
            else False
        )
        if score > best_score or (score == best_score and has_class_match and not best_has_class):
            best_candidate = candidate
            best_score = score
            best_has_class = has_class_match
    return best_candidate


def match_apprenants_to_appels(appels) -> dict[int, Apprenant | None]:
    appels_list = [appel for appel in appels if getattr(appel, "pk", None)]
    if not appels_list:
        return {}

    matched: dict[int, Apprenant | None] = {}
    unresolved = []
    for appel in appels_list:
        try:
            survey = appel.satisfaction_apprenant
        except Exception:
            survey = None
        apprenant = getattr(survey, "apprenant", None)
        if apprenant is not None:
            matched[appel.pk] = apprenant
            continue
        unresolved.append(appel)

    candidates = _apprenant_queryset_for_appels(unresolved)
    candidates_by_code: dict[str, list[Apprenant]] = defaultdict(list)
    candidates_by_phone: dict[str, list[Apprenant]] = defaultdict(list)
    candidates_by_name: dict[str, list[Apprenant]] = defaultdict(list)

    for candidate in candidates:
        code_key = _normalize_key(getattr(candidate, "code", ""))
        if code_key:
            candidates_by_code[code_key].append(candidate)

        for phone in {
            _normalize_phone(getattr(candidate, "telephone1", "")),
            _normalize_phone(getattr(candidate, "telephone2", "")),
        }:
            if phone:
                candidates_by_phone[phone].append(candidate)

        name_key = _normalize_name(getattr(candidate, "nom_complet", ""))
        if name_key:
            candidates_by_name[name_key].append(candidate)

    for appel in unresolved:
        class_codes = _class_codes_for_appel(appel)
        phone_candidates = [
            phone
            for phone in {
                _normalize_phone(getattr(appel, "telephone1", "")),
                _normalize_phone(getattr(appel, "telephone2", "")),
            }
            if phone
        ]
        name_key = _normalize_name(getattr(appel, "nom", ""))
        scoped_candidates = candidates
        if class_codes:
            scoped_candidates = [
                candidate
                for candidate in candidates
                if _normalize_key(getattr(getattr(candidate, "classe", None), "code", "")) in class_codes
            ] or candidates

        apprenant = _pick_by_class(
            candidates_by_code.get(_normalize_key(getattr(appel, "code", "")), []),
            class_codes,
        )
        if apprenant is None:
            apprenant = _pick_partial_code(scoped_candidates, getattr(appel, "code", ""), class_codes)
        if apprenant is None:
            for phone in phone_candidates:
                apprenant = _pick_by_class(candidates_by_phone.get(phone, []), class_codes)
                if apprenant is not None:
                    break
        if apprenant is None and name_key:
            apprenant = _pick_by_class(candidates_by_name.get(name_key, []), class_codes)
        if apprenant is None:
            apprenant = _pick_flexible_name(scoped_candidates, getattr(appel, "nom", ""), class_codes)

        matched[appel.pk] = apprenant

    return matched


def resolve_apprenant_for_appel(appel) -> Apprenant | None:
    if not getattr(appel, "pk", None):
        return None
    return match_apprenants_to_appels([appel]).get(appel.pk)


def get_local_apprenant_identifier(apprenant: Apprenant | None) -> str:
    if apprenant is None:
        return ""
    return _clean(getattr(apprenant, "code", "")) or f"#{apprenant.pk}"


def get_local_apprenant_db_label(apprenant: Apprenant | None) -> str:
    if apprenant is None:
        return ""
    return f"DB #{apprenant.pk}"

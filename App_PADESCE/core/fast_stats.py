from __future__ import annotations

import re
import unicodedata
from copy import copy
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.db.models import Prefetch
from django.http import HttpResponse, JsonResponse, QueryDict
from django.urls import reverse
from django.utils import timezone
from openpyxl.cell.cell import MergedCell
from openpyxl import Workbook, load_workbook

from App_PADESCE.appels.models import Appel, AppelAnswers, AppelFormateur
from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.formations.models import Classe, Formateur
from App_PADESCE.reporting.network_excel import (
    build_padesce_source_index,
    normalize_network_lookup,
    normalize_workbook_source_key,
)
from App_PADESCE.satisfaction_apprenants.models import SatisfactionApprenant

FAST_STATS_TEMPLATE_PATH = Path(settings.BASE_DIR) / "data" / "templates" / "fast_stats_template.xlsx"
FAST_STATS_FILTER_KEYS = (
    "prestation",
    "classe",
    "prestataire",
    "beneficiaire",
    "cohorte",
    "fenetre",
    "ville",
    "source",
)
FAST_STATS_TEMPLATE_ROW_START = 4
FAST_STATS_TEMPLATE_SHEET_HINTS = {
    "apprenant": ("enquete", "satisfaction"),
    "formateur": ("enquete", "formateur"),
}


def _safe_text(value) -> str:
    return str(value or "").strip()


def _normalize_text(value) -> str:
    normalized = unicodedata.normalize("NFKD", _safe_text(value).lower())
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", without_accents)


def _phone_digits(value) -> str:
    return "".join(ch for ch in _safe_text(value) if ch.isdigit())


def _cohorte_matches(raw_value: str, target_value: str) -> bool:
    target = _safe_text(target_value)
    if not target:
        return True
    raw_text = _safe_text(raw_value)
    if not raw_text:
        return True
    if raw_text == target:
        return True
    digits = set(re.findall(r"\d+", raw_text))
    return target in digits


def _formation_matches(expected_value: str, current_value: str) -> bool:
    expected = _normalize_text(expected_value)
    current = _normalize_text(current_value)
    if not expected or not current:
        return False
    return expected == current or expected in current or current in expected


def _location_matches(classe: Classe, raw_location: str) -> bool:
    current = _normalize_text(raw_location)
    if not current:
        return False
    candidates = [
        getattr(getattr(classe, "lieu", None), "nom_lieu", ""),
        getattr(getattr(classe, "lieu", None), "ville", ""),
        getattr(getattr(classe, "lieu", None), "arrondissement", ""),
    ]
    normalized_candidates = [_normalize_text(item) for item in candidates if _safe_text(item)]
    return any(candidate and (candidate in current or current in candidate) for candidate in normalized_candidates)


def _percentage(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _percentage_label(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.2f}%"


def _status_label(classe: Classe) -> str:
    mapping = {
        "termine": "TERMINÉ",
        "en_cours": "EN COURS",
        "non_demarre": "NON DÉMARRÉ",
    }
    return mapping.get(_safe_text(classe.statut), _safe_text(getattr(classe, "get_statut_display", lambda: "")()) or "—")


def _extract_fast_stats_filters(request) -> dict[str, str]:
    source = getattr(request, "GET", QueryDict("", mutable=True))
    return {key: _safe_text(source.get(key, "")) for key in FAST_STATS_FILTER_KEYS}


def _filtered_classes_queryset(filters: dict[str, str]):
    appels_qs = Appel.objects.filter(is_active=True).select_related("answers", "satisfaction_apprenant").order_by("code", "nom", "pk")
    apprenants_qs = Apprenant.objects.order_by("code", "nom_complet", "pk")
    return (
        Classe.objects
        .select_related(
            "prestation",
            "prestation__prestataire",
            "prestation__beneficiaire",
            "formation",
            "lieu",
            "formateur",
        )
        .prefetch_related(
            Prefetch("apprenants", queryset=apprenants_qs),
            Prefetch("appels", queryset=appels_qs),
        )
        .order_by("prestation__code", "code")
    )

 
def _get_completed_satisfaction(appel: Appel):
    try:
        satisfaction = appel.satisfaction_apprenant
    except SatisfactionApprenant.DoesNotExist:
        return None
    return satisfaction


def _text_filter_matches(candidate: str, selected: str) -> bool:
    selected_normalized = _normalize_text(selected)
    if not selected_normalized:
        return True
    candidate_normalized = _normalize_text(candidate)
    if not candidate_normalized:
        return False
    return (
        candidate_normalized == selected_normalized
        or selected_normalized in candidate_normalized
        or candidate_normalized in selected_normalized
    )


def _class_matches_filters(classe: Classe, filters: dict[str, str]) -> bool:
    prestation = getattr(classe, "prestation", None)
    if filters["prestation"] and not _text_filter_matches(getattr(prestation, "code", ""), filters["prestation"]):
        return False
    if filters["classe"] and not _text_filter_matches(classe.code, filters["classe"]):
        return False
    if filters["prestataire"] and not _text_filter_matches(
        getattr(getattr(prestation, "prestataire", None), "raison_sociale", ""),
        filters["prestataire"],
    ):
        return False
    if filters["beneficiaire"] and not _text_filter_matches(
        getattr(getattr(prestation, "beneficiaire", None), "nom_structure", ""),
        filters["beneficiaire"],
    ):
        return False
    if filters["cohorte"] and not _cohorte_matches(str(classe.cohorte), filters["cohorte"]):
        return False
    if filters["fenetre"] and not _text_filter_matches(getattr(classe, "fenetre", ""), filters["fenetre"]):
        return False
    if filters["ville"] and not _text_filter_matches(getattr(getattr(classe, "lieu", None), "ville", ""), filters["ville"]):
        return False
    return True


def _resolve_fast_stats_classes(filters: dict[str, str]) -> tuple[list[Classe], dict]:
    all_classes = list(_filtered_classes_queryset(filters))
    filtered = [classe for classe in all_classes if _class_matches_filters(classe, filters)]

    scopes = [
        (
            "terminees_actives",
            [classe for classe in filtered if getattr(classe, "actif", True) and _safe_text(classe.statut) == "termine"],
            True,
            "Classes actives terminées",
        ),
        (
            "actives",
            [classe for classe in filtered if getattr(classe, "actif", True)],
            False,
            "Classes actives",
        ),
        (
            "toutes",
            filtered,
            False,
            "Toutes les classes",
        ),
    ]
    for scope_key, classes, terminated_only, scope_label in scopes:
        if classes:
            return classes, {
                "scope_key": scope_key,
                "scope_label": scope_label,
                "terminated_only": terminated_only,
            }
    return [], {
        "scope_key": "vide",
        "scope_label": "Aucune classe",
        "terminated_only": False,
    }


def _has_appel_answers(appel: Appel) -> bool:
    try:
        return bool(appel.answers)
    except AppelAnswers.DoesNotExist:
        return False


def _has_completed_apprenant_survey(appel: Appel) -> bool:
    return _has_appel_answers(appel) or bool(_get_completed_satisfaction(appel))


def _has_appel_audio(appel: Appel) -> bool:
    audio = getattr(appel, "audio_file", None)
    return bool(audio and getattr(audio, "name", ""))


def _apprenant_call_effectue(appel: Appel) -> bool:
    status = _safe_text(getattr(appel, "status", ""))
    return bool(
        (status and status != "en_attente")
        or _has_completed_apprenant_survey(appel)
        or _has_appel_audio(appel)
        or getattr(appel, "locked_at", None)
        or getattr(appel, "rappel_at", None)
    )


def _apprenant_call_termine(appel: Appel) -> bool:
    return _has_completed_apprenant_survey(appel)


def _apprenant_person_key(appel: Appel) -> str:
    phone = _phone_digits(getattr(appel, "telephone1", "") or getattr(appel, "telephone2", ""))
    if phone:
        return phone
    code = _safe_text(getattr(appel, "code", ""))
    if code:
        return _normalize_text(code)
    nom = _safe_text(getattr(appel, "nom", ""))
    if nom:
        return _normalize_text(nom)
    return f"appel-{getattr(appel, 'pk', '0')}"


def _source_class_apprenant_totals(source_bundle: dict | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in (source_bundle or {}).get("records", {}).values():
        classe_code = _safe_text(record.get("classe_id") or record.get("classe_label"))
        normalized_code = normalize_network_lookup(classe_code)
        if not normalized_code:
            continue
        counts[normalized_code] = counts.get(normalized_code, 0) + 1
    return counts


def _load_source_class_apprenant_totals(filters: dict[str, str]) -> dict[str, int]:
    source_key = normalize_workbook_source_key(filters.get("source", ""))
    try:
        source_bundle = build_padesce_source_index(source_key=source_key)
    except Exception:
        return {}
    return _source_class_apprenant_totals(source_bundle)


def _build_apprenant_row(
    index: int,
    classe: Classe,
    *,
    source_class_counts: dict[str, int] | None = None,
) -> dict:
    local_apprenant_count = len(list(classe.apprenants.all()))
    classe_key = normalize_network_lookup(classe.code)
    apprenant_count = int((source_class_counts or {}).get(classe_key, local_apprenant_count) or 0)
    appels = list(classe.appels.all())
    people: dict[str, dict[str, bool]] = {}
    for appel in appels:
        key = _apprenant_person_key(appel)
        person_flags = people.setdefault(key, {"effectue": False, "termine": False})
        person_flags["effectue"] = person_flags["effectue"] or _apprenant_call_effectue(appel)
        person_flags["termine"] = person_flags["termine"] or _apprenant_call_termine(appel)

    calls_effectues = min(apprenant_count, sum(1 for flags in people.values() if flags["effectue"]))
    calls_termines = min(apprenant_count, sum(1 for flags in people.values() if flags["termine"]), calls_effectues)
    pct_appel_effectue = _percentage(calls_effectues, apprenant_count)
    pct_appel_termine = _percentage(calls_termines, calls_effectues)
    pct_enquetes = _percentage(calls_termines, apprenant_count)
    return {
        "index": index,
        "prestation_id": _safe_text(getattr(getattr(classe, "prestation", None), "code", "")) or "—",
        "classe_id": _safe_text(classe.code) or "—",
        "apprenant_count": apprenant_count,
        "calls_effectues": calls_effectues,
        "calls_termines": calls_termines,
        "pct_appel_effectue": pct_appel_effectue,
        "pct_appel_effectue_label": _percentage_label(pct_appel_effectue),
        "pct_appel_termine": pct_appel_termine,
        "pct_appel_termine_label": _percentage_label(pct_appel_termine),
        "pct_enquetes": pct_enquetes,
        "pct_enquetes_label": _percentage_label(pct_enquetes),
        "status_label": _status_label(classe),
    }


def _formateur_directory_by_phone() -> dict[str, str]:
    directory: dict[str, str] = {}
    for phone, name in Formateur.objects.exclude(telephone="").values_list("telephone", "nom_complet"):
        digits = _phone_digits(phone)
        if digits and digits not in directory:
            directory[digits] = _safe_text(name)
    return directory


def _build_contact(name: str, phone: str) -> dict:
    return {
        "name": _safe_text(name),
        "phone": _phone_digits(phone),
    }


def _pad_contacts(contacts: list[dict], *, limit: int) -> list[dict]:
    padded = contacts[:limit]
    while len(padded) < limit:
        padded.append({"name": "", "phone": ""})
    return padded


def _build_calendar_contacts(
    classe: Classe,
    *,
    formateur_directory: dict[str, str],
    limit: int = 2,
) -> tuple[list[dict], int]:
    contacts: list[dict] = []
    seen_phones: set[str] = set()

    if getattr(classe, "formateur", None):
        phone = _phone_digits(classe.formateur.telephone)
        if phone or _safe_text(classe.formateur.nom_complet):
            contacts.append(_build_contact(classe.formateur.nom_complet or classe.formateur.code, phone))
            if phone:
                seen_phones.add(phone)

    for apprenant in classe.apprenants.all():
        phone = _phone_digits(apprenant.tel_formateur)
        if not phone or phone in seen_phones:
            continue
        seen_phones.add(phone)
        slot_number = len(contacts) + 1
        resolved_name = formateur_directory.get(phone) or f"Contact calendrier N{slot_number}"
        contacts.append(_build_contact(resolved_name, phone))
        if len(contacts) >= limit:
            break

    actual_count = len(contacts)
    return _pad_contacts(contacts, limit=limit), actual_count


def _split_source_contact_phones(value: str) -> list[str]:
    seen: set[str] = set()
    phones: list[str] = []
    for item in re.split(r"[/,;|]", _safe_text(value)):
        digits = _phone_digits(item)
        if not digits or digits in seen:
            continue
        seen.add(digits)
        phones.append(digits)
    return phones


def _call_phone_candidates(call: AppelFormateur) -> list[str]:
    phones = []
    primary = _phone_digits(call.telephone)
    if primary:
        phones.append(primary)
    phones.extend(_split_source_contact_phones(call.source_contact))
    deduped: list[str] = []
    seen: set[str] = set()
    for phone in phones:
        if phone in seen:
            continue
        seen.add(phone)
        deduped.append(phone)
    return deduped


def _prestation_formateur_candidates(classe: Classe, cache: dict[int, list[AppelFormateur]]) -> list[AppelFormateur]:
    prestation = getattr(classe, "prestation", None)
    prestation_id = getattr(prestation, "pk", None)
    if prestation_id is None:
        return []
    if prestation_id in cache:
        return cache[prestation_id]

    rows = list(AppelFormateur.objects.filter(is_active=True).order_by("session_date", "numero_seance", "reference_code"))
    prestataire_name = _safe_text(getattr(getattr(prestation, "prestataire", None), "raison_sociale", ""))
    beneficiaire_name = _safe_text(getattr(getattr(prestation, "beneficiaire", None), "nom_structure", ""))
    if prestataire_name:
        rows = [row for row in rows if _text_filter_matches(row.prestataire, prestataire_name)]
    if beneficiaire_name:
        rows = [row for row in rows if _text_filter_matches(row.beneficiaire, beneficiaire_name)]
    formation_name = _safe_text(getattr(getattr(prestation, "formation", None), "nom", ""))
    if formation_name:
        formation_rows = [row for row in rows if _formation_matches(formation_name, row.formation)]
        if formation_rows:
            rows = formation_rows

    cache[prestation_id] = rows
    return rows


def _build_descente_contacts(
    classe: Classe,
    *,
    calendar_contacts: list[dict],
    formateur_directory: dict[str, str],
    prestation_calls_cache: dict[int, list[AppelFormateur]],
    limit: int = 4,
) -> tuple[list[dict], int, int]:
    class_phone = _phone_digits(getattr(getattr(classe, "formateur", None), "telephone", ""))
    formation_name = _safe_text(classe.intitule_formation or getattr(getattr(classe, "formation", None), "nom", ""))
    candidates = []

    for call in _prestation_formateur_candidates(classe, prestation_calls_cache):
        if not _cohorte_matches(call.cohorte, str(classe.cohorte)):
            continue
        phone_candidates = _call_phone_candidates(call)
        phone_match = bool(class_phone and class_phone in phone_candidates)
        formation_match = _formation_matches(formation_name, call.formation)
        location_match = _location_matches(classe, call.lieu)
        candidates.append(
            {
                "call": call,
                "rank": (
                    0 if phone_match else 1,
                    0 if formation_match else 1,
                    0 if location_match else 1,
                    0 if _safe_text(call.status) == "termine" else 1,
                    0 if call.q1_prerequis_apprenants is not None else 1,
                    call.session_date.isoformat() if getattr(call, "session_date", None) else "9999-12-31",
                    getattr(call, "numero_seance", None) or 9999,
                    _safe_text(call.reference_code),
                ),
            }
        )

    candidates.sort(key=lambda item: item["rank"])

    calendar_names_by_phone = {
        _phone_digits(contact["phone"]): _safe_text(contact["name"])
        for contact in calendar_contacts
        if _phone_digits(contact["phone"])
    }

    contacts: list[dict] = []
    seen_phones: set[str] = set()
    completed_count = 0
    for item in candidates:
        call = item["call"]
        if _safe_text(call.status) == "termine":
            completed_count += 1
        for phone in _call_phone_candidates(call):
            if phone in seen_phones:
                continue
            seen_phones.add(phone)
            slot_number = len(contacts) + 1
            if class_phone and phone == class_phone and getattr(classe, "formateur", None):
                resolved_name = _safe_text(classe.formateur.nom_complet or classe.formateur.code)
            else:
                resolved_name = (
                    calendar_names_by_phone.get(phone)
                    or formateur_directory.get(phone)
                    or f"Contact descente N{slot_number}"
                )
            contacts.append(_build_contact(resolved_name, phone))
            if len(contacts) >= limit:
                break
        if len(contacts) >= limit:
            break

    actual_count = len(contacts)
    return _pad_contacts(contacts, limit=limit), actual_count, completed_count


def _build_class_link(request, classe: Classe) -> tuple[str, str]:
    relative_url = reverse("class_analysis_detail", args=[classe.code])
    build_absolute_uri = getattr(request, "build_absolute_uri", None)
    if callable(build_absolute_uri):
        return build_absolute_uri(relative_url), f"Ouvrir {classe.code}"
    return relative_url, f"Ouvrir {classe.code}"


def _build_formateur_row(
    index: int,
    classe: Classe,
    *,
    request,
    formateur_directory: dict[str, str],
    prestation_calls_cache: dict[int, list[AppelFormateur]],
) -> dict:
    calendar_contacts, calendar_contact_count = _build_calendar_contacts(
        classe,
        formateur_directory=formateur_directory,
        limit=2,
    )
    descente_contacts, descente_contact_count, completed_count = _build_descente_contacts(
        classe,
        calendar_contacts=calendar_contacts,
        formateur_directory=formateur_directory,
        prestation_calls_cache=prestation_calls_cache,
        limit=4,
    )
    class_link_url, class_link_label = _build_class_link(request, classe)
    prestation = getattr(classe, "prestation", None)
    return {
        "index": index,
        "prestation_id": _safe_text(getattr(prestation, "code", "")) or "—",
        "classe_id": _safe_text(classe.code) or "—",
        "class_link_url": class_link_url,
        "class_link_label": class_link_label,
        "beneficiaire_name": _safe_text(getattr(getattr(prestation, "beneficiaire", None), "nom_structure", "")),
        "prestataire_name": _safe_text(getattr(getattr(prestation, "prestataire", None), "raison_sociale", "")),
        "calendar_contacts": calendar_contacts,
        "calendar_contact_count": calendar_contact_count,
        "descente_contacts": descente_contacts,
        "descente_contact_count": descente_contact_count,
        "descente_completed_count": completed_count,
        "status_label": _status_label(classe),
    }


def _apprenant_summary_cards(rows: list[dict]) -> list[dict]:
    return [
        {
            "label": "Classes",
            "value": len(rows),
            "meta": "Classes terminées visibles dans FAST STATS.",
        },
        {
            "label": "Inscrits",
            "value": sum(row["apprenant_count"] for row in rows),
            "meta": "Nombre total d'apprenants inscrits sur les classes retenues.",
        },
        {
            "label": "Appels effectués",
            "value": sum(row["calls_effectues"] for row in rows),
            "meta": "Appels réellement entamés ou traités sur la plateforme.",
        },
        {
            "label": "Appels terminés",
            "value": sum(row["calls_termines"] for row in rows),
            "meta": "Appels clôturés ou avec enquête complétée.",
        },
    ]


def _formateur_summary_cards(rows: list[dict]) -> list[dict]:
    matched_classes = sum(1 for row in rows if row["descente_contact_count"] > 0)
    return [
        {
            "label": "Classes",
            "value": len(rows),
            "meta": "Classes terminées visibles dans FAST STATS.",
        },
        {
            "label": "Calendrier",
            "value": sum(row["calendar_contact_count"] for row in rows),
            "meta": "Contacts formateurs identifiés depuis les classes et les apprenants.",
        },
        {
            "label": "Descente",
            "value": sum(row["descente_contact_count"] for row in rows),
            "meta": "Contacts retrouvés dans les appels formateurs de terrain.",
        },
        {
            "label": "Classes raccordées",
            "value": matched_classes,
            "meta": "Classes ayant au moins un contact côté descente.",
        },
    ]


def _mode_payload(mode_id: str, *, rows: list[dict], summary_cards: list[dict], sheet_name: str, scope: dict) -> dict:
    if mode_id == "apprenant":
        return {
            "id": mode_id,
            "label": "Apprenant",
            "sheet_name": sheet_name,
            "table_variant": "apprenant",
            "row_count": len(rows),
            "class_count": len(rows),
            "summary_cards": summary_cards,
            "metadata": {
                "terminated_only_label": "Total classe de la prestation terminée",
                "terminated_only_value": scope["terminated_only"],
                "scope_label": scope["scope_label"],
            },
            "columns": [
                {"key": "index", "label": "#"},
                {"key": "prestation_id", "label": "Prestation ID"},
                {"key": "classe_id", "label": "Classe ID"},
                {"key": "apprenant_count", "label": "Nombre d'apprenant inscrit"},
                {"key": "calls_effectues", "label": "Nbre d'appels effectués"},
                {"key": "calls_termines", "label": "Nombre d'appels terminé"},
                {"key": "pct_appel_effectue_label", "label": "% appel effectué"},
                {"key": "pct_appel_termine_label", "label": "% appel terminé"},
                {"key": "pct_enquetes_label", "label": "% enquêtes"},
            ],
            "rows": rows,
            "note": "Structure alignée sur la feuille Enquête de satisfaction du fichier FAST STATS.",
        }

    return {
        "id": mode_id,
        "label": "Formateur",
        "sheet_name": sheet_name,
        "table_variant": "formateur",
        "row_count": len(rows),
        "class_count": len(rows),
        "summary_cards": summary_cards,
        "metadata": {
            "terminated_only_label": "Total classe de la prestation terminée",
            "terminated_only_value": scope["terminated_only"],
            "scope_label": scope["scope_label"],
        },
        "column_groups": [
            {"label": "Structure classe", "span": 6},
            {"label": "Selon Calendrier", "span": 4},
            {"label": "Selon Descente", "span": 8},
        ],
        "columns": [
            {"key": "index", "label": "#"},
            {"key": "prestation_id", "label": "Prestation ID"},
            {"key": "classe_id", "label": "Classe ID"},
            {"key": "class_link_label", "label": "Lien de la classe"},
            {"key": "beneficiaire_name", "label": "Nom du bénéficiaire"},
            {"key": "prestataire_name", "label": "Nom du prestataire"},
            {"key": "calendar_contacts.0.name", "label": "Nom Formateur N1"},
            {"key": "calendar_contacts.0.phone", "label": "Numero formateur N1"},
            {"key": "calendar_contacts.1.name", "label": "Nom Formateur N2"},
            {"key": "calendar_contacts.1.phone", "label": "Numero formateur N2"},
            {"key": "descente_contacts.0.name", "label": "Nom Formateur N1"},
            {"key": "descente_contacts.0.phone", "label": "Numero formateur N1"},
            {"key": "descente_contacts.1.name", "label": "Nom Formateur N2"},
            {"key": "descente_contacts.1.phone", "label": "Numero formateur N2"},
            {"key": "descente_contacts.2.name", "label": "Nom Formateur N3"},
            {"key": "descente_contacts.2.phone", "label": "Numero formateur N3"},
            {"key": "descente_contacts.3.name", "label": "Nom Formateur N4"},
            {"key": "descente_contacts.3.phone", "label": "Numero formateur N4"},
        ],
        "rows": rows,
        "note": "Structure alignée sur la feuille Enquête de formateur du fichier FAST STATS.",
    }


def _find_sheet_name(workbook: Workbook, mode_id: str) -> str:
    hints = FAST_STATS_TEMPLATE_SHEET_HINTS[mode_id]
    for sheet_name in workbook.sheetnames:
        normalized_name = _normalize_text(sheet_name)
        if all(hint in normalized_name for hint in hints):
            return sheet_name
    fallback = "Enquête de satisfaction" if mode_id == "apprenant" else "Enquête de formateur"
    if fallback not in workbook.sheetnames:
        workbook.create_sheet(fallback)
    return fallback


def build_fast_stats_bundle(request) -> dict:
    filters = _extract_fast_stats_filters(request)
    classes, scope = _resolve_fast_stats_classes(filters)
    source_class_counts = _load_source_class_apprenant_totals(filters)
    formateur_directory = _formateur_directory_by_phone()
    prestation_calls_cache: dict[int, list[AppelFormateur]] = {}

    apprenant_rows = [
        _build_apprenant_row(
            index,
            classe,
            source_class_counts=source_class_counts,
        )
        for index, classe in enumerate(classes, start=1)
    ]
    formateur_rows = [
        _build_formateur_row(
            index,
            classe,
            request=request,
            formateur_directory=formateur_directory,
            prestation_calls_cache=prestation_calls_cache,
        )
        for index, classe in enumerate(classes, start=1)
    ]

    return {
        "generated_at": timezone.localtime().isoformat(),
        "filters": filters,
        "terminated_only": scope["terminated_only"],
        "scope_label": scope["scope_label"],
        "modes": [
            _mode_payload(
                "apprenant",
                rows=apprenant_rows,
                summary_cards=_apprenant_summary_cards(apprenant_rows),
                sheet_name="Enquête de satisfaction",
                scope=scope,
            ),
            _mode_payload(
                "formateur",
                rows=formateur_rows,
                summary_cards=_formateur_summary_cards(formateur_rows),
                sheet_name="Enquête de formateur",
                scope=scope,
            ),
        ],
    }


def build_fast_stats_api_payload(request) -> dict:
    return build_fast_stats_bundle(request)


def build_fast_stats_api_response(request) -> JsonResponse:
    return JsonResponse(build_fast_stats_api_payload(request))


def _copy_style(source_cell, target_cell) -> None:
    target_cell._style = copy(source_cell._style)
    target_cell.number_format = source_cell.number_format
    target_cell.alignment = copy(source_cell.alignment)
    target_cell.font = copy(source_cell.font)
    target_cell.fill = copy(source_cell.fill)
    target_cell.border = copy(source_cell.border)
    target_cell.protection = copy(source_cell.protection)


def _ensure_sheet_capacity(worksheet, *, last_row: int, max_col: int, template_row: int = FAST_STATS_TEMPLATE_ROW_START) -> None:
    if worksheet.max_row >= last_row:
        return
    template_height = worksheet.row_dimensions[template_row].height
    for target_row in range(worksheet.max_row + 1, last_row + 1):
        for column in range(1, max_col + 1):
            _copy_style(worksheet.cell(template_row, column), worksheet.cell(target_row, column))
        if template_height:
            worksheet.row_dimensions[target_row].height = template_height


def _clear_data_rows(worksheet, *, start_row: int, max_col: int) -> None:
    for row in range(start_row, worksheet.max_row + 1):
        for column in range(1, max_col + 1):
            cell = worksheet.cell(row, column)
            cell.value = None
            cell.hyperlink = None


def _clone_sheet_layout(source_sheet, target_workbook: Workbook):
    target_sheet = target_workbook.create_sheet(source_sheet.title)
    target_sheet.sheet_view.showGridLines = source_sheet.sheet_view.showGridLines
    target_sheet.freeze_panes = source_sheet.freeze_panes
    for column_letter, dimension in source_sheet.column_dimensions.items():
        target_dimension = target_sheet.column_dimensions[column_letter]
        target_dimension.width = dimension.width
        target_dimension.hidden = dimension.hidden
    for row_index, dimension in source_sheet.row_dimensions.items():
        target_dimension = target_sheet.row_dimensions[row_index]
        target_dimension.height = dimension.height
        target_dimension.hidden = dimension.hidden
    for merged_range in source_sheet.merged_cells.ranges:
        target_sheet.merge_cells(str(merged_range))
    for row in source_sheet.iter_rows():
        for source_cell in row:
            if isinstance(source_cell, MergedCell):
                continue
            target_cell = target_sheet[source_cell.coordinate]
            target_cell.value = source_cell.value
            _copy_style(source_cell, target_cell)
            if source_cell.hyperlink:
                target_cell.hyperlink = copy(source_cell.hyperlink)
    return target_sheet


def _write_apprenant_sheet(worksheet, mode_payload: dict) -> None:
    worksheet["B1"] = "Total classe de la prestation termine"
    worksheet["C1"] = "TRUE"
    worksheet["B3"] = "Prestation ID"
    worksheet["C3"] = "Classe ID"
    worksheet["D3"] = "Nombre d'apprenant inscrit"
    worksheet["E3"] = "Nbre d'appels effectués"
    worksheet["F3"] = "Nombre d'appels terminé"
    worksheet["G3"] = "% appel effectué"
    worksheet["H3"] = "% appel terminé"
    worksheet["I3"] = "%enquêtes"

    _clear_data_rows(worksheet, start_row=FAST_STATS_TEMPLATE_ROW_START, max_col=9)
    last_row = max(FAST_STATS_TEMPLATE_ROW_START, FAST_STATS_TEMPLATE_ROW_START + len(mode_payload["rows"]) - 1)
    _ensure_sheet_capacity(worksheet, last_row=last_row, max_col=9)

    for offset, row in enumerate(mode_payload["rows"], start=FAST_STATS_TEMPLATE_ROW_START):
        worksheet[f"A{offset}"] = row["index"]
        worksheet[f"B{offset}"] = row["prestation_id"]
        worksheet[f"C{offset}"] = row["classe_id"]
        worksheet[f"D{offset}"] = row["apprenant_count"]
        worksheet[f"E{offset}"] = row["calls_effectues"]
        worksheet[f"F{offset}"] = row["calls_termines"]
        worksheet[f"G{offset}"] = row["pct_appel_effectue"]
        worksheet[f"H{offset}"] = row["pct_appel_termine"]
        worksheet[f"I{offset}"] = row["pct_enquetes"]
        worksheet[f"G{offset}"].number_format = "0.00%"
        worksheet[f"H{offset}"].number_format = "0.00%"
        worksheet[f"I{offset}"].number_format = "0.00%"


def _write_formateur_sheet(worksheet, mode_payload: dict) -> None:
    worksheet["B1"] = "Total classe de la prestation termine"
    worksheet["C1"] = "TRUE"
    worksheet["G2"] = "Selon Calendrier"
    worksheet["K2"] = "Selon Descente"
    worksheet["B3"] = "Prestation ID"
    worksheet["C3"] = "Classe ID"
    worksheet["D3"] = "Lien de la classe"
    worksheet["E3"] = "Nom du Beneficiaire"
    worksheet["F3"] = "Nom du prestataire"
    worksheet["G3"] = "Nom Formateur N1"
    worksheet["H3"] = "Numero formateur N1"
    worksheet["I3"] = "Nom Formateur N2"
    worksheet["J3"] = "Numero formateur N2"
    worksheet["K3"] = "Nom Formateur N1"
    worksheet["L3"] = "Numero formateur N1"
    worksheet["M3"] = "Nom Formateur N2"
    worksheet["N3"] = "Numero formateur N2"
    worksheet["O3"] = "Nom Formateur N3"
    worksheet["P3"] = "Numero formateur N3"
    worksheet["Q3"] = "Nom Formateur N4"
    worksheet["R3"] = "Numero formateur N4"

    _clear_data_rows(worksheet, start_row=FAST_STATS_TEMPLATE_ROW_START, max_col=18)
    last_row = max(FAST_STATS_TEMPLATE_ROW_START, FAST_STATS_TEMPLATE_ROW_START + len(mode_payload["rows"]) - 1)
    _ensure_sheet_capacity(worksheet, last_row=last_row, max_col=18)

    for offset, row in enumerate(mode_payload["rows"], start=FAST_STATS_TEMPLATE_ROW_START):
        worksheet[f"A{offset}"] = row["index"]
        worksheet[f"B{offset}"] = row["prestation_id"]
        worksheet[f"C{offset}"] = row["classe_id"]
        worksheet[f"D{offset}"] = row["class_link_label"]
        worksheet[f"D{offset}"].hyperlink = row["class_link_url"]
        worksheet[f"E{offset}"] = row["beneficiaire_name"]
        worksheet[f"F{offset}"] = row["prestataire_name"]

        calendar_contacts = row["calendar_contacts"]
        descente_contacts = row["descente_contacts"]
        worksheet[f"G{offset}"] = calendar_contacts[0]["name"]
        worksheet[f"H{offset}"] = calendar_contacts[0]["phone"]
        worksheet[f"I{offset}"] = calendar_contacts[1]["name"]
        worksheet[f"J{offset}"] = calendar_contacts[1]["phone"]
        worksheet[f"K{offset}"] = descente_contacts[0]["name"]
        worksheet[f"L{offset}"] = descente_contacts[0]["phone"]
        worksheet[f"M{offset}"] = descente_contacts[1]["name"]
        worksheet[f"N{offset}"] = descente_contacts[1]["phone"]
        worksheet[f"O{offset}"] = descente_contacts[2]["name"]
        worksheet[f"P{offset}"] = descente_contacts[2]["phone"]
        worksheet[f"Q{offset}"] = descente_contacts[3]["name"]
        worksheet[f"R{offset}"] = descente_contacts[3]["phone"]


def build_fast_stats_workbook(request, *, active_mode: str = "apprenant") -> Workbook:
    if FAST_STATS_TEMPLATE_PATH.exists():
        template_workbook = load_workbook(FAST_STATS_TEMPLATE_PATH)
        source_apprenant_sheet = template_workbook[_find_sheet_name(template_workbook, "apprenant")]
        source_formateur_sheet = template_workbook[_find_sheet_name(template_workbook, "formateur")]
        workbook = Workbook()
        workbook.remove(workbook.active)
        apprenant_sheet = _clone_sheet_layout(source_apprenant_sheet, workbook)
        formateur_sheet = _clone_sheet_layout(source_formateur_sheet, workbook)
    else:
        workbook = Workbook()
        workbook.active.title = "Enquête de satisfaction"
        apprenant_sheet = workbook.active
        formateur_sheet = workbook.create_sheet("Enquête de formateur")

    modes = {mode["id"]: mode for mode in build_fast_stats_bundle(request)["modes"]}
    _write_apprenant_sheet(apprenant_sheet, modes["apprenant"])
    _write_formateur_sheet(formateur_sheet, modes["formateur"])

    active_sheet_name = formateur_sheet.title if active_mode == "formateur" else apprenant_sheet.title
    workbook.active = workbook.sheetnames.index(active_sheet_name)
    return workbook


def build_fast_stats_export_response(request) -> HttpResponse:
    active_mode = _safe_text(getattr(request, "GET", QueryDict("", mutable=True)).get("fast_stats_mode", "apprenant"))
    workbook = build_fast_stats_workbook(request, active_mode=active_mode)
    timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="fast_stats_satisfaction_{timestamp}.xlsx"'
    workbook.save(response)
    return response


def build_fast_stats_context(request, *, default_mode: str) -> dict:
    return {
        "fast_stats_default_mode": default_mode if default_mode in {"apprenant", "formateur"} else "apprenant",
    }


def request_like_with_query(query_string: str = ""):
    querydict = QueryDict(query_string, mutable=True)

    def _build_absolute_uri(path: str = "/") -> str:
        return f"https://testserver{path}"

    return SimpleNamespace(
        GET=querydict,
        build_absolute_uri=_build_absolute_uri,
    )

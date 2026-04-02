from __future__ import annotations

import re
from copy import copy
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.db.models import Prefetch
from django.http import HttpResponse, QueryDict
from django.utils import timezone
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter

from App_PADESCE.appels.models import Appel, AppelFormateur
from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.formations.models import Classe

FAST_STATS_TEMPLATE_PATH = Path(settings.BASE_DIR) / "data" / "templates" / "fast_stats_template.xlsx"
FAST_STATS_FILTER_KEYS = (
    "prestation",
    "classe",
    "prestataire",
    "beneficiaire",
    "cohorte",
    "fenetre",
    "ville",
)


def _safe_text(value) -> str:
    return str(value or "").strip()


def _normalize_text(value) -> str:
    return re.sub(r"[^a-z0-9]+", "", _safe_text(value).lower())


def _phone_digits(value) -> str:
    return "".join(ch for ch in _safe_text(value) if ch.isdigit())


def _cohorte_matches(raw_value: str, target_value: str) -> bool:
    target = _safe_text(target_value)
    if not target:
        return True
    raw_text = _safe_text(raw_value)
    if not raw_text:
        return False
    if raw_text == target:
        return True
    digits = set(re.findall(r"\d+", raw_text))
    return target in digits


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
    appels_qs = (
        Appel.objects.filter(is_active=True)
        .select_related("answers")
        .order_by("code", "nom", "pk")
    )
    apprenants_qs = Apprenant.objects.order_by("code", "nom_complet", "pk")
    queryset = (
        Classe.objects.select_related(
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

    if filters["prestation"]:
        queryset = queryset.filter(prestation__code=filters["prestation"])
    if filters["classe"]:
        queryset = queryset.filter(code=filters["classe"])
    if filters["prestataire"]:
        queryset = queryset.filter(
            prestation__prestataire__raison_sociale=filters["prestataire"]
        )
    if filters["beneficiaire"]:
        queryset = queryset.filter(
            prestation__beneficiaire__nom_structure=filters["beneficiaire"]
        )
    if filters["cohorte"] and filters["cohorte"].isdigit():
        queryset = queryset.filter(cohorte=int(filters["cohorte"]))
    if filters["fenetre"]:
        queryset = queryset.filter(fenetre=filters["fenetre"])
    if filters["ville"]:
        queryset = queryset.filter(lieu__ville=filters["ville"])
    return queryset


def _dedupe_contacts(candidates: list[dict], *, limit: int = 2, prefix: str = "Contact") -> list[dict]:
    contacts: list[dict] = []
    seen: set[tuple[str, str]] = set()
    fallback_index = 1
    for candidate in candidates:
        name = _safe_text(candidate.get("name"))
        phone = _phone_digits(candidate.get("phone"))
        if not name and not phone:
            continue
        if not name:
            name = f"{prefix} {fallback_index}"
        key = ("phone", phone) if phone else ("name", _normalize_text(name))
        if key in seen:
            continue
        seen.add(key)
        contacts.append({"name": name, "phone": phone})
        fallback_index += 1
        if len(contacts) >= limit:
            break
    while len(contacts) < limit:
        contacts.append({"name": "", "phone": ""})
    return contacts


def _apprenant_source_contacts(classe: Classe) -> tuple[list[dict], int]:
    candidates = [
        {
            "name": apprenant.nom_complet or apprenant.code,
            "phone": apprenant.telephone1 or apprenant.telephone2,
            "rank": (
                0 if _phone_digits(apprenant.telephone1 or apprenant.telephone2) else 1,
                _safe_text(apprenant.code),
                _safe_text(apprenant.nom_complet),
            ),
        }
        for apprenant in classe.apprenants.all()
    ]
    candidates.sort(key=lambda item: item["rank"])
    return _dedupe_contacts(candidates, prefix="Apprenant"), len(candidates)


def _appel_source_contacts(classe: Classe) -> tuple[list[dict], int, int]:
    candidates = []
    answers_count = 0
    for appel in classe.appels.all():
        phone = appel.telephone1 or appel.telephone2
        has_answer = bool(getattr(appel, "answers", None))
        if has_answer:
            answers_count += 1
        candidates.append(
            {
                "name": appel.nom or appel.code,
                "phone": phone,
                "rank": (
                    0 if has_answer else 1,
                    0 if _safe_text(appel.status) == "termine" else 1,
                    0 if _phone_digits(phone) else 1,
                    _safe_text(appel.code),
                ),
            }
        )
    candidates.sort(key=lambda item: item["rank"])
    return _dedupe_contacts(candidates, prefix="Contact appel"), len(candidates), answers_count


def _formateur_class_contacts(classe: Classe) -> tuple[list[dict], int]:
    candidates: list[dict] = []
    seen_phones: set[str] = set()
    contact_index = 1
    if getattr(classe, "formateur", None):
        formateur_phone = _phone_digits(classe.formateur.telephone)
        if formateur_phone:
            seen_phones.add(formateur_phone)
        candidates.append(
            {
                "name": classe.formateur.nom_complet or classe.formateur.code,
                "phone": classe.formateur.telephone,
            }
        )

    for apprenant in classe.apprenants.all():
        phone = _phone_digits(apprenant.tel_formateur)
        if not phone or phone in seen_phones:
            continue
        seen_phones.add(phone)
        candidates.append(
            {
                "name": f"Contact classe {contact_index}",
                "phone": phone,
            }
        )
        contact_index += 1
    return _dedupe_contacts(candidates, prefix="Contact classe"), len(candidates)


def _split_source_contact_phones(value: str) -> list[str]:
    phones = []
    for item in re.split(r"[/,;|]", _safe_text(value)):
        digits = _phone_digits(item)
        if digits:
            phones.append(digits)
    return phones


def _classe_matches_formateur_call(classe: Classe, call: AppelFormateur) -> bool:
    prestation = getattr(classe, "prestation", None)
    if not prestation:
        return False

    class_prestataire = _normalize_text(getattr(getattr(prestation, "prestataire", None), "raison_sociale", ""))
    class_beneficiaire = _normalize_text(getattr(getattr(prestation, "beneficiaire", None), "nom_structure", ""))
    call_prestataire = _normalize_text(call.prestataire)
    call_beneficiaire = _normalize_text(call.beneficiaire)
    if class_prestataire and class_prestataire != call_prestataire:
        return False
    if class_beneficiaire and class_beneficiaire != call_beneficiaire:
        return False

    if not _cohorte_matches(call.cohorte, str(classe.cohorte)):
        return False

    class_formation = _normalize_text(classe.intitule_formation or getattr(classe, "formation", None) and classe.formation.nom)
    call_formation = _normalize_text(call.formation)
    if class_formation and call_formation:
        return class_formation == call_formation or class_formation in call_formation or call_formation in class_formation
    return True


def _formateur_call_contacts(classe: Classe, calls: list[AppelFormateur]) -> tuple[list[dict], int, int]:
    matched_calls = [call for call in calls if _classe_matches_formateur_call(classe, call)]
    candidates: list[dict] = []
    unique_phones: set[str] = set()
    completed_count = 0
    for call in matched_calls:
        if _safe_text(call.status) == "termine":
            completed_count += 1
        phone_values = []
        if call.telephone:
            phone_values.append(call.telephone)
        phone_values.extend(_split_source_contact_phones(call.source_contact))
        for raw_phone in phone_values:
            digits = _phone_digits(raw_phone)
            if not digits or digits in unique_phones:
                continue
            unique_phones.add(digits)
            label_prefix = "Contact terminé" if _safe_text(call.status) == "termine" else "Contact appel"
            candidates.append(
                {
                    "name": f"{label_prefix} {len(unique_phones)}",
                    "phone": digits,
                    "rank": (
                        0 if _safe_text(call.status) == "termine" else 1,
                        0 if call.q1_prerequis_apprenants is not None else 1,
                        _safe_text(call.reference_code),
                    ),
                }
            )
    candidates.sort(key=lambda item: item["rank"])
    return _dedupe_contacts(candidates, prefix="Contact appel"), len(unique_phones), completed_count


def _row_base(classe: Classe) -> dict:
    prestation = getattr(classe, "prestation", None)
    prestataire = getattr(getattr(prestation, "prestataire", None), "raison_sociale", "")
    beneficiaire = getattr(getattr(prestation, "beneficiaire", None), "nom_structure", "")
    return {
        "prestation_label": _safe_text(getattr(prestation, "code", "")) or "Sans prestation",
        "prestation_meta": " | ".join(part for part in [prestataire, beneficiaire] if _safe_text(part)),
        "classe_code": _safe_text(classe.code) or "—",
        "status_label": _status_label(classe),
    }


def _with_prestation_spans(rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    order: list[str] = []
    for row in rows:
        key = row["prestation_label"]
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(row)

    preview_rows: list[dict] = []
    for key in order:
        group = grouped[key]
        for index, row in enumerate(group):
            preview_rows.append(
                {
                    **row,
                    "show_prestation": index == 0,
                    "prestation_rowspan": len(group) if index == 0 else 0,
                }
            )
    return preview_rows


def _build_apprenant_rows(classes: list[Classe]) -> list[dict]:
    rows = []
    for classe in classes:
        left_contacts, apprenant_count = _apprenant_source_contacts(classe)
        right_contacts, appel_count, answer_count = _appel_source_contacts(classe)
        row = _row_base(classe)
        row.update(
            {
                "summary_label": f"{answer_count} réponse(s) · {appel_count} appel(s)",
                "left_primary_name": left_contacts[0]["name"],
                "left_primary_phone": left_contacts[0]["phone"],
                "left_secondary_name": left_contacts[1]["name"],
                "left_secondary_phone": left_contacts[1]["phone"],
                "right_primary_name": right_contacts[0]["name"],
                "right_primary_phone": right_contacts[0]["phone"],
                "right_secondary_name": right_contacts[1]["name"],
                "right_secondary_phone": right_contacts[1]["phone"],
                "apprenant_count": apprenant_count,
                "appel_count": appel_count,
                "answer_count": answer_count,
            }
        )
        rows.append(row)
    return _with_prestation_spans(rows)


def _build_formateur_rows(classes: list[Classe], filters: dict[str, str]) -> list[dict]:
    formateur_calls_qs = AppelFormateur.objects.filter(is_active=True).order_by(
        "session_date", "numero_seance", "reference_code"
    )
    if filters["prestataire"]:
        formateur_calls_qs = formateur_calls_qs.filter(prestataire=filters["prestataire"])
    if filters["beneficiaire"]:
        formateur_calls_qs = formateur_calls_qs.filter(beneficiaire=filters["beneficiaire"])
    if filters["cohorte"]:
        formateur_calls_qs = formateur_calls_qs.filter(cohorte__icontains=filters["cohorte"])
    calls = list(formateur_calls_qs)

    rows = []
    for classe in classes:
        left_contacts, class_contact_count = _formateur_class_contacts(classe)
        right_contacts, matched_phone_count, completed_count = _formateur_call_contacts(classe, calls)
        row = _row_base(classe)
        row.update(
            {
                "summary_label": f"{completed_count} terminé(s) · {matched_phone_count} contact(s)",
                "left_primary_name": left_contacts[0]["name"],
                "left_primary_phone": left_contacts[0]["phone"],
                "left_secondary_name": left_contacts[1]["name"],
                "left_secondary_phone": left_contacts[1]["phone"],
                "right_primary_name": right_contacts[0]["name"],
                "right_primary_phone": right_contacts[0]["phone"],
                "right_secondary_name": right_contacts[1]["name"],
                "right_secondary_phone": right_contacts[1]["phone"],
                "class_contact_count": class_contact_count,
                "matched_phone_count": matched_phone_count,
                "completed_count": completed_count,
            }
        )
        rows.append(row)
    return _with_prestation_spans(rows)


def _mode_payload(mode_id: str, *, rows: list[dict], note: str, left_label: str, right_label: str) -> dict:
    prestation_count = len({row["prestation_label"] for row in rows})
    return {
        "id": mode_id,
        "label": "Apprenant" if mode_id == "apprenant" else "Formateur",
        "sheet_title": "FAST STATS APPRENANTS" if mode_id == "apprenant" else "FAST STATS FORMATEURS",
        "left_group_label": left_label,
        "right_group_label": right_label,
        "note": note,
        "rows": rows,
        "row_count": len(rows),
        "class_count": len(rows),
        "prestation_count": prestation_count,
    }


def build_fast_stats_bundle(request) -> dict:
    filters = _extract_fast_stats_filters(request)
    classes = list(_filtered_classes_queryset(filters))
    apprenant_rows = _build_apprenant_rows(classes)
    formateur_rows = _build_formateur_rows(classes, filters)
    return {
        "filters": filters,
        "modes": [
            _mode_payload(
                "apprenant",
                rows=apprenant_rows,
                note="Comparaison entre les apprenants chargés sur la plateforme et les contacts effectivement présents dans les appels apprenants.",
                left_label="Source plateforme apprenants",
                right_label="Source appels apprenants",
            ),
            _mode_payload(
                "formateur",
                rows=formateur_rows,
                note="Comparaison entre les contacts formateurs visibles dans les classes et ceux rencontrés dans les appels formateurs de la plateforme.",
                left_label="Source classes / apprenants",
                right_label="Source appels formateurs",
            ),
        ],
    }


def _template_styles():
    if FAST_STATS_TEMPLATE_PATH.exists():
        workbook = load_workbook(FAST_STATS_TEMPLATE_PATH)
        worksheet = workbook[workbook.sheetnames[0]]
        return {
            "column_widths": {
                letter: worksheet.column_dimensions[letter].width
                for letter in [get_column_letter(index) for index in range(1, 13)]
                if worksheet.column_dimensions[letter].width is not None
            },
            "group_header": worksheet["E1"],
            "subheader": worksheet["E2"],
            "prestation": worksheet["A2"],
            "class_cell": worksheet["B4"],
            "data_cell": worksheet["E3"],
        }
    return {}


def _apply_style(source_cell, target_cell) -> None:
    if not source_cell:
        return
    target_cell._style = copy(source_cell._style)
    target_cell.number_format = source_cell.number_format
    target_cell.alignment = copy(source_cell.alignment)
    target_cell.font = copy(source_cell.font)
    target_cell.fill = copy(source_cell.fill)
    target_cell.border = copy(source_cell.border)
    target_cell.protection = copy(source_cell.protection)


def _write_fast_stats_sheet(workbook: Workbook, mode_payload: dict, *, template: dict) -> None:
    worksheet = workbook.create_sheet(mode_payload["sheet_title"])
    column_widths = template.get("column_widths", {})
    defaults = {
        "A": 18,
        "B": 14,
        "C": 14,
        "D": 22,
        "E": 18.71,
        "F": 14.57,
        "G": 18.71,
        "H": 14.57,
        "I": 18.71,
        "J": 14.57,
        "K": 18.71,
        "L": 14.57,
    }
    for letter, width in defaults.items():
        worksheet.column_dimensions[letter].width = column_widths.get(letter, width)

    group_header_style = template.get("group_header")
    subheader_style = template.get("subheader")
    prestation_style = template.get("prestation")
    class_style = template.get("class_cell")
    data_style = template.get("data_cell")

    worksheet.merge_cells("E1:H1")
    worksheet.merge_cells("I1:L1")
    worksheet["E1"] = mode_payload["left_group_label"]
    worksheet["I1"] = mode_payload["right_group_label"]
    _apply_style(group_header_style, worksheet["E1"])
    _apply_style(group_header_style, worksheet["I1"])
    worksheet["E1"].alignment = Alignment(horizontal="center", vertical="center")
    worksheet["I1"].alignment = Alignment(horizontal="center", vertical="center")

    headers = {
        "A2": "Prestation",
        "B2": "Classe",
        "C2": "Statut",
        "D2": "Synthèse",
        "E2": "Nom 1",
        "F2": "Tel 1",
        "G2": "Nom 2",
        "H2": "Tel 2",
        "I2": "Nom 1",
        "J2": "Tel 1",
        "K2": "Nom 2",
        "L2": "Tel 2",
    }
    for coordinate, value in headers.items():
        worksheet[coordinate] = value
        _apply_style(subheader_style, worksheet[coordinate])

    current_row = 3
    rows = mode_payload["rows"]
    if not rows:
        worksheet.merge_cells(f"A{current_row}:L{current_row}")
        worksheet[f"A{current_row}"] = "Aucune donnée disponible pour les filtres courants."
        _apply_style(data_style, worksheet[f"A{current_row}"])
        return

    for row in rows:
        if row["show_prestation"]:
            start_row = current_row
            end_row = current_row + row["prestation_rowspan"] - 1
            if end_row > start_row:
                worksheet.merge_cells(f"A{start_row}:A{end_row}")
            worksheet[f"A{start_row}"] = row["prestation_label"]
            _apply_style(prestation_style, worksheet[f"A{start_row}"])
            worksheet[f"A{start_row}"].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            if row.get("prestation_meta"):
                worksheet[f"A{start_row}"].comment = None

        values = {
            f"B{current_row}": row["classe_code"],
            f"C{current_row}": row["status_label"],
            f"D{current_row}": row["summary_label"],
            f"E{current_row}": row["left_primary_name"],
            f"F{current_row}": row["left_primary_phone"],
            f"G{current_row}": row["left_secondary_name"],
            f"H{current_row}": row["left_secondary_phone"],
            f"I{current_row}": row["right_primary_name"],
            f"J{current_row}": row["right_primary_phone"],
            f"K{current_row}": row["right_secondary_name"],
            f"L{current_row}": row["right_secondary_phone"],
        }
        for coordinate, value in values.items():
            worksheet[coordinate] = value
            _apply_style(class_style if coordinate.startswith("B") else data_style, worksheet[coordinate])
            worksheet[coordinate].alignment = Alignment(
                vertical="center",
                wrap_text=True,
                horizontal="left" if coordinate[0] not in {"F", "J"} else "center",
            )
        current_row += 1

    worksheet.freeze_panes = "A3"
    worksheet.sheet_view.showGridLines = True


def build_fast_stats_workbook(request, *, active_mode: str = "apprenant") -> Workbook:
    bundle = build_fast_stats_bundle(request)
    template = _template_styles()
    workbook = Workbook()
    workbook.remove(workbook.active)
    for mode in bundle["modes"]:
        _write_fast_stats_sheet(workbook, mode, template=template)
    titles = [sheet.title for sheet in workbook.worksheets]
    target_title = "FAST STATS FORMATEURS" if active_mode == "formateur" else "FAST STATS APPRENANTS"
    if target_title in titles:
        workbook.active = titles.index(target_title)
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
    bundle = build_fast_stats_bundle(request)
    return {
        "fast_stats": bundle,
        "fast_stats_default_mode": default_mode if default_mode in {"apprenant", "formateur"} else "apprenant",
    }


def request_like_with_query(query_string: str = ""):
    return SimpleNamespace(GET=QueryDict(query_string, mutable=True))

from __future__ import annotations

import re
from collections import defaultdict
from types import SimpleNamespace
from urllib.parse import urlencode

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import render
from django.urls import reverse

from App_PADESCE.appels.formateur_names import resolve_formateur_db_name_from_values
from App_PADESCE.appels.formateurs_views import (
    _build_filtered_formateurs_queryset,
)
from App_PADESCE.appels.models import (
    FORMATEUR_SCORE_FIELDS,
    formateur_has_any_audio,
    formateur_has_any_form_data,
)
from App_PADESCE.core.views import _build_consultant_dashboard_context
from App_PADESCE.formations.views import _resolve_classe_for_formateur_analysis
from App_PADESCE.satisfaction_apprenants.services import get_prestations_ranking
from App_PADESCE.satisfaction_apprenants.views import _build_satisfaction_dashboard_data
from App_PADESCE.satisfaction_formateurs.views import (
    _average_displayed_scores,
    _build_satisfaction_formateurs_dashboard_context,
)

PUBLIC_SCOPE_CHOICES = ("apprenant", "formateur")
PUBLIC_SECTION_CHOICES = ("principal", "apercu", "stats")


def _public_scope(request) -> str:
    scope = str(request.GET.get("scope") or "").strip().lower()
    return scope if scope in PUBLIC_SCOPE_CHOICES else "apprenant"


def _public_section(request) -> str:
    section = str(request.GET.get("section") or "").strip().lower()
    return section if section in PUBLIC_SECTION_CHOICES else "principal"


def _public_space_url(*, section: str, scope: str) -> str:
    return f"{reverse('public_space')}?scope={scope}&section={section}"


def _login_url_for(request) -> str:
    path = request.get_full_path() or reverse("public_space")
    return f"{reverse('login')}?{urlencode({'next': path})}"


def _region_map_from_rankings(rankings: list[dict]) -> dict[str, list[dict]]:
    region_data: dict[str, list[dict]] = defaultdict(list)
    for item in rankings:
        region = str(item.get("region") or "").strip() or "Inconnu"
        if len(region_data[region]) >= 5:
            continue
        region_data[region].append(
            {
                "code": item.get("code", ""),
                "prestataire": item.get("prestataire", ""),
                "beneficiaire": item.get("beneficiaire", ""),
                "score": item.get("score_global", 0),
            }
        )
    return dict(region_data)


def _build_apprenant_overview(request) -> dict:
    dashboard = _build_satisfaction_dashboard_data(request)
    ctx = dashboard["context"]
    classes = []
    for item in ctx.get("classe_stats", []):
        code = str(item.get("code") or "").strip()
        prestation_code = str(item.get("prestation") or "").strip()
        classes.append(
            {
                "code": code,
                "label": str(item.get("intitule") or "").strip() or "-",
                "cohorte": item.get("cohorte") or "-",
                "fenetre": item.get("fenetre") or "-",
                "prestation_code": prestation_code or "-",
                "url": (
                    f"{reverse('class_analysis_detail', args=[code])}?tab=apprenants"
                    if code
                    else ""
                ),
                "prestation_url": (
                    f"{reverse('prestation_analysis_detail', args=[prestation_code])}"
                    "?tab=apprenants"
                    if prestation_code
                    else ""
                ),
                "nb": item.get("nb", 0),
            }
        )

    prestations = []
    for item in ctx.get("prestation_stats", []):
        code = str(item.get("code") or "").strip()
        prestations.append(
            {
                "code": code,
                "prestataire": item.get("prestataire") or "-",
                "beneficiaire": item.get("beneficiaire") or "-",
                "nb": item.get("nb", 0),
                "avg": item.get("avg", 0),
                "url": (
                    f"{reverse('prestation_analysis_detail', args=[code])}?tab=apprenants"
                    if code
                    else ""
                ),
            }
        )

    def fmt(val):
        return f"{int(val or 0):,}".replace(",", " ")

    return {
        "classes": classes,
        "prestations": prestations,
        "prestataires": ctx.get("analyzed_prestataires", []),
        "beneficiaires": ctx.get("analyzed_beneficiaires", []),
        "summary_cards": [
            ("Prestataires analysés", fmt(ctx.get("analyzed_prestataires_count", 0))),
            ("Bénéficiaires analysés", fmt(ctx.get("analyzed_beneficiaires_count", 0))),
            ("Formations analysées", fmt(ctx.get("analyzed_prestations_count", 0))),
            ("Cohortes analysées", fmt(ctx.get("analyzed_classes_count", 0))),
        ],
    }


def _build_apprenant_stats(request) -> dict:
    dashboard = _build_satisfaction_dashboard_data(request)
    ctx = dashboard["context"]
    best_rankings = get_prestations_ranking(ctx.get("prestation_stats_all", []), order="desc")
    improve_rankings = get_prestations_ranking(ctx.get("prestation_stats_all", []), order="asc")
    return {
        "global_avgs": ctx.get("global_avgs", {}),
        "best_rankings": best_rankings[:10],
        "improve_rankings": improve_rankings[:10],
        "map_data": _region_map_from_rankings(best_rankings),
        "summary_cards": [
            ("Moyenne Q9", ctx.get("global_avgs", {}).get("Satisfaction globale", 0)),
            ("Classes", ctx.get("analyzed_classes_count", 0)),
            ("Prestations", ctx.get("analyzed_prestations_count", 0)),
            ("Réponses", ctx.get("total", 0)),
        ],
    }


def _formateur_record_value(record, field_name: str, default=""):
    if isinstance(record, dict):
        return record.get(field_name, default)
    return getattr(record, field_name, default)


def _resolve_formateur_classe(record, cache: dict[tuple, object]):
    cache_key = (
        str(_formateur_record_value(record, "prestataire") or "").strip().casefold(),
        str(_formateur_record_value(record, "beneficiaire") or "").strip().casefold(),
        str(_formateur_record_value(record, "cohorte") or "").strip().casefold(),
        str(_formateur_record_value(record, "telephone") or "").strip(),
        str(_formateur_record_value(record, "source_contact") or "").strip(),
        str(_formateur_record_value(record, "formation") or "").strip().casefold(),
    )
    if cache_key in cache:
        return cache[cache_key]

    if isinstance(record, dict):
        payload = {"source_contact": "", **record}
        candidate = SimpleNamespace(**payload)
    else:
        candidate = record

    try:
        cache[cache_key] = _resolve_classe_for_formateur_analysis(candidate)
    except Exception:
        cache[cache_key] = None
    return cache[cache_key]


def _build_formateur_principal(request) -> dict:
    from App_PADESCE.formations.models import Formateur

    def _normalize_phone(value: str) -> str:
        return re.sub(r"\D+", "", str(value or ""))

    queryset, filters = _build_filtered_formateurs_queryset(request)

    # 1. Resolve and Enrich ALL rows (small set, safe to list)
    all_rows = list(
        queryset.order_by("-updated_at", "session_date", "prestataire", "reference_code")
    )
    resolution_cache: dict[tuple, object] = {}

    # Enriched stats for cards
    res_formations = set()
    res_cohortes = set()
    res_prestataires = set()
    res_beneficiaires = set()

    # Metrics
    summary_tentes_count = 0
    summary_reussis_count = 0
    summary_form_remplis = 0
    summary_form_audio = 0
    summary_audios_total = 0

    success_statuses = ["formulaire_rempli", "formulaire_avec_audio", "termine", "appel_reussi"]

    # Map telephones -> formateur(s) links configured in the gestion page.
    formateurs = (
        Formateur.objects.filter(actif=True)
        .prefetch_related("prestations__prestataire", "prestations__beneficiaire")
        .all()
    )
    formateur_by_phone: dict[str, Formateur] = {}
    for formateur in formateurs:
        phone_key = _normalize_phone(getattr(formateur, "telephone", ""))
        if phone_key and phone_key not in formateur_by_phone:
            formateur_by_phone[phone_key] = formateur

    for row in all_rows:
        classe = _resolve_formateur_classe(row, resolution_cache)
        prestation = getattr(classe, "prestation", None)
        formation_obj = getattr(classe, "formation", None)
        prest_obj = getattr(prestation, "prestataire", None)
        ben_obj = getattr(prestation, "beneficiaire", None)

        classe_code = str(getattr(classe, "code", "") or "").strip()
        prestation_code = str(getattr(prestation, "code", "") or "").strip()

        raw_phone_candidates = [
            str(getattr(row, "telephone", "") or "").strip(),
            str(getattr(row, "source_contact", "") or "").strip(),
        ]
        linked_formateur = None
        for phone_raw in raw_phone_candidates:
            for phone_match in re.findall(r"\d{8,15}", phone_raw):
                phone_key = _normalize_phone(phone_match)
                if not phone_key:
                    continue
                linked_formateur = formateur_by_phone.get(phone_key)
                if linked_formateur:
                    break
            if linked_formateur:
                break

        linked_prestations = []
        if linked_formateur:
            linked_prestations = sorted(
                list(linked_formateur.prestations.all()), key=lambda item: str(item.code or "")
            )

        # If class resolution does not provide prestation code, fallback to
        # manually toggled prestation(s) from the gestion page.
        if not prestation_code and linked_prestations:
            prestation_code = str(getattr(linked_prestations[0], "code", "") or "").strip()

        # Keep displayed org labels aligned with manually linked prestation
        # when source row has missing values.
        if linked_prestations:
            first_linked = linked_prestations[0]
            if not str(getattr(row, "prestataire", "") or "").strip():
                row.prestataire = str(
                    getattr(getattr(first_linked, "prestataire", None), "raison_sociale", "") or ""
                ).strip()
            if not str(getattr(row, "beneficiaire", "") or "").strip():
                row.beneficiaire = str(
                    getattr(getattr(first_linked, "beneficiaire", None), "nom_structure", "") or ""
                ).strip()

        # Enrichment from Classe Metadata (The user's "complet par téléphone" request)
        if classe:
            row.prestataire = prest_obj.raison_sociale if prest_obj else row.prestataire
            row.beneficiaire = ben_obj.nom_structure if ben_obj else row.beneficiaire
            row.formation = (
                (classe.intitule_formation or formation_obj.nom) if formation_obj else row.formation
            )
            row.cohorte = classe.cohorte or row.cohorte

        row.public_classe_code = classe_code or "-"
        row.public_classe_url = (
            f"{reverse('class_analysis_detail', args=[classe_code])}?tab=formateurs"
            if classe_code
            else ""
        )
        row.public_prestation_code = prestation_code or "-"
        if not prestation_code and linked_prestations:
            linked_codes = [
                str(getattr(item, "code", "") or "").strip() for item in linked_prestations
            ]
            linked_codes = [code for code in linked_codes if code]
            if linked_codes:
                row.public_prestation_code = (
                    linked_codes[0]
                    if len(linked_codes) == 1
                    else f"{linked_codes[0]} (+{len(linked_codes) - 1})"
                )
        row.public_prestation_url = (
            f"{reverse('prestation_analysis_detail', args=[prestation_code])}?tab=formateurs"
            if prestation_code
            else ""
        )
        row.public_formateur_nom = str(
            getattr(linked_formateur, "nom", "") or ""
        ).strip() or resolve_formateur_db_name_from_values(
            getattr(row, "telephone", ""),
            getattr(row, "source_contact", ""),
        )

        # Calculate Metrics and Card counts
        has_form = formateur_has_any_form_data(row)
        has_audio = formateur_has_any_audio(row)
        row.public_has_form = has_form
        row.public_has_audio = has_audio

        row.public_search_blob = " ".join(
            [
                str(row.source_contact or ""),
                str(row.reference_code or ""),
                str(row.telephone or ""),
                str(row.public_formateur_nom or ""),
                str(row.formation or ""),
                str(row.prestataire or ""),
                str(row.beneficiaire or ""),
                str(row.lieu or ""),
                str(row.public_prestation_code or ""),
            ]
        ).lower()

        is_tented = row.status != "en_attente"
        if is_tented:
            summary_tentes_count += 1
            summary_reussis_count += 1  # Any attempt is reussi by rule
            if has_audio:
                summary_audios_total += 1
            if has_form:
                summary_form_remplis += 1
                if has_audio:
                    summary_form_audio += 1

        # Cards (distinct counts for completed records)
        if row.status in success_statuses:
            res_formations.add(formation_obj.pk if formation_obj else row.formation)
            res_cohortes.add(
                classe.pk if classe else f"{row.prestataire}-{row.beneficiaire}-{row.cohorte}"
            )
            res_prestataires.add(prest_obj.pk if prest_obj else row.prestataire)
            res_beneficiaires.add(ben_obj.pk if ben_obj else row.beneficiaire)

    # Apply search filter on Formateur fields + Prestation code
    search = (request.GET.get("q") or "").strip()
    if search:
        search_lower = search.lower()
        filtered_rows = []
        for row in all_rows:
            if search_lower in getattr(row, "public_search_blob", ""):
                filtered_rows.append(row)
        all_rows = filtered_rows

    # 2. Sorting: Prioritize records with both form and audio
    from datetime import date

    all_rows.sort(
        key=lambda x: (
            getattr(x, "public_has_form", False) and getattr(x, "public_has_audio", False),
            getattr(x, "updated_at", None) or getattr(x, "session_date", date.min) or date.min,
        ),
        reverse=True,
    )

    # 3. Pagination
    def fmt(val):
        return f"{int(val or 0):,}".replace(",", " ")

    paginator = Paginator(all_rows, 25)
    page_number = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    filters["status_choices"] = [
        {"value": "", "label": "Statut"},
        {"value": "en_attente", "label": "En attente"},
        {"value": "appel_tente", "label": "Appel tente"},
        {"value": "en_cours", "label": "En cours"},
        {"value": "pause", "label": "Pause"},
        {"value": "a_rappeler", "label": "A rappeler"},
        {"value": "appel_reussi", "label": "Appel reussi"},
        {"value": "formulaire_rempli", "label": "Formulaire rempli"},
        {"value": "formulaire_avec_audio", "label": "Formulaire avec audio"},
        {"value": "completed", "label": "Finalises"},
        {"value": "termine", "label": "Termine"},
    ]

    def _mean_score(rows, field_name):
        values = []
        for item in rows:
            raw_value = getattr(item, field_name, None)
            if raw_value is None:
                continue
            try:
                values.append(float(raw_value))
            except (TypeError, ValueError):
                continue
        return round(sum(values) / len(values), 1) if values else 0

    avg_q1 = _mean_score(all_rows, "q1_prerequis_apprenants")
    avg_q2 = _mean_score(all_rows, "q2_interaction_apprenants")
    avg_q3 = _mean_score(all_rows, "q3_competences_acquises")
    avg_general = round((avg_q1 + avg_q2 + avg_q3) / 3, 1)

    return {
        "rows": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "filters": filters,
        "card_formations_count": fmt(len(res_formations)),
        "card_cohortes_count": fmt(len(res_cohortes)),
        "card_prestataires_count": fmt(len(res_prestataires)),
        "card_beneficiaires_count": fmt(len(res_beneficiaires)),
        "summary_appels_cibles": fmt(len(all_rows)),
        "summary_tentes": fmt(summary_tentes_count),
        "summary_reussis": fmt(summary_reussis_count),
        "summary_form_remplis": fmt(summary_form_remplis),
        "summary_form_sans_audio": fmt(max(summary_form_remplis - summary_form_audio, 0)),
        "summary_form_audio": fmt(summary_form_audio),
        "summary_audios": fmt(summary_audios_total),
        "summary_moyenne_prerequis": avg_q1,
        "summary_moyenne_interaction": avg_q2,
        "summary_moyenne_competences": avg_q3,
        "summary_moyenne_generale": avg_general,
    }


def _build_formateur_overview(request) -> dict:
    ctx = _build_satisfaction_formateurs_dashboard_context(request)
    resolution_cache: dict[tuple, object] = {}
    class_rows: dict[str, dict] = {}
    prestation_rows: dict[str, dict] = {}

    success_statuses = ["formulaire_rempli", "formulaire_avec_audio", "termine", "appel_reussi"]
    res_formations = set()
    res_cohortes = set()
    res_prestataires = set()
    res_beneficiaires = set()

    for record in ctx.get("all_rows", []):
        classe = _resolve_formateur_classe(record, resolution_cache)
        prestation = getattr(classe, "prestation", None)
        formation_obj = getattr(classe, "formation", None)
        prest_obj = getattr(prestation, "prestataire", None)
        ben_obj = getattr(prestation, "beneficiaire", None)

        classe_code = str(getattr(classe, "code", "") or "").strip()
        prestation_code = str(getattr(prestation, "code", "") or "").strip()

        # Update overview tables (logic remains the same, but we could also filter them if needed)
        # However, for the cards, we follow the principal page logic exactly.
        if (
            record.get("status") in success_statuses
            or getattr(record, "status", None) in success_statuses
        ):
            res_formations.add(
                formation_obj.pk if formation_obj else _formateur_record_value(record, "formation")
            )
            res_cohortes.add(
                classe.pk
                if classe
                else (
                    f"{_formateur_record_value(record, 'prestataire')}"
                    f"-{_formateur_record_value(record, 'beneficiaire')}"
                    f"-{_formateur_record_value(record, 'cohorte')}"
                )
            )
            res_prestataires.add(
                prest_obj.pk if prest_obj else _formateur_record_value(record, "prestataire")
            )
            res_beneficiaires.add(
                ben_obj.pk if ben_obj else _formateur_record_value(record, "beneficiaire")
            )

        if classe_code:
            class_rows.setdefault(
                classe_code,
                {
                    "code": classe_code,
                    "label": str(
                        getattr(classe, "intitule_formation", "")
                        or _formateur_record_value(record, "formation")
                        or "-"
                    ).strip(),
                    "cohorte": _formateur_record_value(record, "cohorte") or "-",
                    "prestation_code": prestation_code or "-",
                    "url": f"{reverse('class_analysis_detail', args=[classe_code])}?tab=formateurs",
                    "prestation_url": (
                        f"{reverse('prestation_analysis_detail', args=[prestation_code])}"
                        "?tab=formateurs"
                        if prestation_code
                        else ""
                    ),
                    "nb": 0,
                },
            )
            class_rows[classe_code]["nb"] += 1

        # Build prestation data directly from record, independent of classe matching
        # Use prestation from record if classe resolution failed
        formation_name = str(
            getattr(classe, "intitule_formation", "")
            or _formateur_record_value(record, "formation")
            or "-"
        ).strip()

        # Create a unique prestation key from prestataire/beneficiaire combination
        # Use these directly from record since classe matching may have failed
        prestataire_val = _formateur_record_value(record, "prestataire") or "-"
        beneficiaire_val = _formateur_record_value(record, "beneficiaire") or "-"

        if prestation_code or (prestataire_val != "-" and beneficiaire_val != "-"):
            # Use prestation_code if available, otherwise create composite key
            prest_key = (
                prestation_code if prestation_code else f"{prestataire_val}|{beneficiaire_val}"
            )

            prestation_rows.setdefault(
                prest_key,
                {
                    "code": prestation_code or prest_key,
                    "formation": formation_name,
                    "cohorte": _formateur_record_value(record, "cohorte") or "-",
                    "prestataire": prestataire_val,
                    "beneficiaire": beneficiaire_val,
                    "url": (
                        f"{reverse('prestation_analysis_detail', args=[prestation_code])}"
                        "?tab=formateurs"
                        if prestation_code
                        else ""
                    ),
                    "nb": 0,
                },
            )
            prestation_rows[prest_key]["nb"] += 1

    def fmt(val):
        return f"{int(val or 0):,}".replace(",", " ")

    return {
        "classes": sorted(class_rows.values(), key=lambda item: (item["code"], item["label"])),
        "prestations": sorted(
            prestation_rows.values(), key=lambda item: (item["code"], item["prestataire"])
        ),
        "prestataires": ctx.get("prestataire_stats", []),
        "beneficiaires": ctx.get("beneficiaire_stats", []),
        "summary_cards": [
            ("Prestataires analysés", fmt(len(res_prestataires))),
            ("Bénéficiaires analysés", fmt(len(res_beneficiaires))),
            ("Formations analysées", fmt(len(res_formations))),
            ("Cohortes analysées", fmt(len(res_cohortes))),
        ],
    }


def _build_formateur_stats(request) -> dict:
    ctx = _build_satisfaction_formateurs_dashboard_context(request)
    resolution_cache: dict[tuple, object] = {}
    grouped: dict[str, dict] = {}

    for record in ctx.get("all_rows", []):
        classe = _resolve_formateur_classe(record, resolution_cache)
        prestation = getattr(classe, "prestation", None)
        code = str(getattr(prestation, "code", "") or "").strip()
        if not code:
            continue

        bucket = grouped.setdefault(
            code,
            {
                "code": code,
                "prestataire": _formateur_record_value(record, "prestataire") or "-",
                "beneficiaire": _formateur_record_value(record, "beneficiaire") or "-",
                "effectif": 0,
                "nb": 0,
                "scores": {field_name: [] for field_name in FORMATEUR_SCORE_FIELDS},
            },
        )
        bucket["effectif"] += 1

        values = [
            _formateur_record_value(record, field_name, None)
            for field_name in FORMATEUR_SCORE_FIELDS
        ]
        if not all(value not in (None, "") for value in values):
            continue

        bucket["nb"] += 1
        for field_name, value in zip(FORMATEUR_SCORE_FIELDS, values):
            bucket["scores"][field_name].append(float(value))

    prestation_stats = []
    for item in grouped.values():
        if not item["nb"]:
            continue
        avgs = []
        for field_name in FORMATEUR_SCORE_FIELDS:
            values = item["scores"][field_name]
            avgs.append(round(sum(values) / len(values), 2) if values else 0)
        avg = round(sum(avgs) / len(avgs), 2) if avgs else 0
        prestation_stats.append(
            {
                "code": item["code"],
                "prestataire": item["prestataire"],
                "beneficiaire": item["beneficiaire"],
                "nb": item["nb"],
                "avg": avg,
                "avgs": avgs,
                "effectif": item["effectif"],
            }
        )

    best_rankings = get_prestations_ranking(prestation_stats, order="desc")
    improve_rankings = get_prestations_ranking(prestation_stats, order="asc")
    return {
        "global_avgs": ctx.get("global_avgs", {}),
        "best_rankings": best_rankings[:10],
        "improve_rankings": improve_rankings[:10],
        "map_data": _region_map_from_rankings(best_rankings),
        "summary_cards": [
            ("Moyenne Q1-Q3", _average_displayed_scores((ctx.get("global_avgs", {}) or {}).values())),
            ("Appels", ctx.get("total", 0)),
            ("Appels ciblés", ctx.get("appels_cibles", 0)),
            ("Avec scores", ctx.get("with_scores", 0)),
        ],
    }


def public_space(request):
    scope = _public_scope(request)
    section = _public_section(request)

    context = {
        "scope": scope,
        "section": section,
        "page_tabs": [
            {
                "label": "Page principale",
                "value": "principal",
                "active": section == "principal",
                "url": _public_space_url(section="principal", scope=scope),
            },
            {
                "label": "Apercu",
                "value": "apercu",
                "active": section == "apercu",
                "url": _public_space_url(section="apercu", scope=scope),
            },
            {
                "label": "Stats",
                "value": "stats",
                "active": section == "stats",
                "url": _public_space_url(section="stats", scope=scope),
            },
        ],
        "scope_tabs": [
            {
                "label": "Apprenant",
                "value": "apprenant",
                "active": scope == "apprenant",
                "url": _public_space_url(section=section, scope="apprenant"),
            },
            {
                "label": "Formateur",
                "value": "formateur",
                "active": scope == "formateur",
                "url": _public_space_url(section=section, scope="formateur"),
            },
        ],
        "login_url": _login_url_for(request),
    }

    if scope == "apprenant":
        if section == "principal":
            ctx = _build_consultant_dashboard_context(request)
            # Calculate Average satisfaction for the current filtered set

            # Build queryset from the same logic
            # (simple enough here as we use Appel.objects.filter(is_active=True)).
            # But we should ideally reuse the filtering logic.
            # For simplicity, we can sometimes manually calculate from rows if small,
            # but for 30000 learners, we need a query.
            # Assuming _build_consultant_dashboard_context uses a specific filtering logic,
            # we try to replicate the core filters.

            # Since _build_consultant_dashboard_context is complex, we'll try to get the average
            # from the rows if they were all fetched, but they are paginated.
            # Wait, ctx["rows"] are the ALL rows (unpaginated list) in that function!
            # (checked views.py:1358: "total_rows": len(rows))
            all_rows = ctx.get("rows", [])
            q9_sum = 0
            q9_count = 0
            for r in all_rows:
                # AppelAnswers are reachable via answers__q9
                val = getattr(getattr(r, "answers", None), "q9_satisfaction_globale", None)
                if val is not None:
                    q9_sum += val
                    q9_count += 1
            avg_q9 = round(q9_sum / q9_count, 1) if q9_count else 0
            ctx["summary_moyenne_satisfaction"] = avg_q9
            context["principal"] = ctx
        elif section == "apercu":
            context["overview"] = _build_apprenant_overview(request)
        else:
            context["stats"] = _build_apprenant_stats(request)
    else:
        if section == "principal":
            context["principal"] = _build_formateur_principal(request)
        elif section == "apercu":
            context["overview"] = _build_formateur_overview(request)
        else:
            context["stats"] = _build_formateur_stats(request)

    return render(request, "core/public_space.html", context)

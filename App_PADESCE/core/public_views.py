from __future__ import annotations

from collections import defaultdict
from types import SimpleNamespace
from urllib.parse import urlencode

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import render
from django.urls import reverse

from App_PADESCE.appels.formateurs_views import (
    _build_filtered_formateurs_queryset,
    _build_formateur_progress_metrics,
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
                    f"{reverse('prestation_analysis_detail', args=[prestation_code])}?tab=apprenants"
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

    return {
        "classes": classes,
        "prestations": prestations,
        "prestataires": ctx.get("analyzed_prestataires", []),
        "beneficiaires": ctx.get("analyzed_beneficiaires", []),
        "summary_cards": [
            ("Classes", ctx.get("analyzed_classes_count", 0)),
            ("Prestations", ctx.get("analyzed_prestations_count", 0)),
            ("Prestataires", ctx.get("analyzed_prestataires_count", 0)),
            ("Bénéficiaires", ctx.get("analyzed_beneficiaires_count", 0)),
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
    queryset, filters = _build_filtered_formateurs_queryset(request)
    metrics = _build_formateur_progress_metrics(queryset)
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
    paginator = Paginator(
        queryset.order_by("-updated_at", "session_date", "prestataire", "reference_code"),
        25,
    )
    page_number = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    resolution_cache: dict[tuple, object] = {}
    rows = []
    for row in page_obj.object_list:
        classe = _resolve_formateur_classe(row, resolution_cache)
        prestation = getattr(classe, "prestation", None)
        classe_code = str(getattr(classe, "code", "") or "").strip()
        prestation_code = str(getattr(prestation, "code", "") or "").strip()
        row.public_classe_code = classe_code or "-"
        row.public_classe_url = (
            f"{reverse('class_analysis_detail', args=[classe_code])}?tab=formateurs"
            if classe_code
            else ""
        )
        row.public_prestation_code = prestation_code or "-"
        row.public_prestation_url = (
            f"{reverse('prestation_analysis_detail', args=[prestation_code])}?tab=formateurs"
            if prestation_code
            else ""
        )
        row.public_has_form = formateur_has_any_form_data(row)
        row.public_has_audio = formateur_has_any_audio(row)
        rows.append(row)

    # Logic from internal dashboard: card counts based on completed forms
    def fmt(val):
        return f"{int(val or 0):,}".replace(",", " ")

    completed_qs = queryset.filter(
        status__in=["formulaire_rempli", "formulaire_avec_audio", "termine", "appel_reussi"]
    )
    card_formations = completed_qs.values_list("formation", flat=True).distinct().count()
    card_cohortes = completed_qs.values_list("cohorte", flat=True).distinct().count()
    card_prestataires = completed_qs.values_list("prestataire", flat=True).distinct().count()
    card_beneficiaires = completed_qs.values_list("beneficiaire", flat=True).distinct().count()

    # Dynamic metrics calculation restoring the correct internal dashboard formulas
    tentes_qs = queryset.exclude(status="en_attente")
    tentes_count = tentes_qs.count()
    summary_reussis = tentes_count  # Everything attempted is considered "reussi" in this context

    summary_form_remplis = 0
    summary_form_audio = 0
    summary_audios_total = 0

    for item in list(tentes_qs):
        has_form = formateur_has_any_form_data(item)
        has_audio = formateur_has_any_audio(item)
        if has_audio:
            summary_audios_total += 1

        if has_form:
            summary_form_remplis += 1
            if has_audio:
                summary_form_audio += 1

    summary_form_sans_audio = max(summary_form_remplis - summary_form_audio, 0)

    return {
        "rows": rows,
        "page_obj": page_obj,
        "paginator": paginator,
        "filters": filters,
        "metrics": metrics,
        "card_formations_count": fmt(card_formations),
        "card_cohortes_count": fmt(card_cohortes),
        "card_prestataires_count": fmt(card_prestataires),
        "card_beneficiaires_count": fmt(card_beneficiaires),
        "summary_appels_cibles": fmt(queryset.count()),
        "summary_tentes": fmt(tentes_count),
        "summary_reussis": fmt(summary_reussis),
        "summary_form_remplis": fmt(summary_form_remplis),
        "summary_form_sans_audio": fmt(summary_form_sans_audio),
        "summary_form_audio": fmt(summary_form_audio),
        "summary_audios": fmt(summary_audios_total),
    }


def _build_formateur_overview(request) -> dict:
    ctx = _build_satisfaction_formateurs_dashboard_context(request)
    resolution_cache: dict[tuple, object] = {}
    class_rows: dict[str, dict] = {}
    prestation_rows: dict[str, dict] = {}

    for record in ctx.get("all_rows", []):
        classe = _resolve_formateur_classe(record, resolution_cache)
        prestation = getattr(classe, "prestation", None)
        classe_code = str(getattr(classe, "code", "") or "").strip()
        prestation_code = str(getattr(prestation, "code", "") or "").strip()

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
                        f"{reverse('prestation_analysis_detail', args=[prestation_code])}?tab=formateurs"
                        if prestation_code
                        else ""
                    ),
                    "nb": 0,
                },
            )
            class_rows[classe_code]["nb"] += 1

        if prestation_code:
            prestation_rows.setdefault(
                prestation_code,
                {
                    "code": prestation_code,
                    "prestataire": _formateur_record_value(record, "prestataire") or "-",
                    "beneficiaire": _formateur_record_value(record, "beneficiaire") or "-",
                    "url": (
                        f"{reverse('prestation_analysis_detail', args=[prestation_code])}?tab=formateurs"
                    ),
                    "nb": 0,
                },
            )
            prestation_rows[prestation_code]["nb"] += 1

    return {
        "classes": sorted(class_rows.values(), key=lambda item: (item["code"], item["label"])),
        "prestations": sorted(
            prestation_rows.values(), key=lambda item: (item["code"], item["prestataire"])
        ),
        "prestataires": ctx.get("prestataire_stats", []),
        "beneficiaires": ctx.get("beneficiaire_stats", []),
        "summary_cards": [
            ("Classes", len(class_rows)),
            ("Prestations", len(prestation_rows)),
            ("Prestataires", len(ctx.get("prestataire_stats", []))),
            ("Bénéficiaires", len(ctx.get("beneficiaire_stats", []))),
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
            (
                (
                    "Moyenne Q1-Q3",
                    round(sum(item["avg"] for item in prestation_stats) / len(prestation_stats), 2),
                )
                if prestation_stats
                else ("Moyenne Q1-Q3", 0)
            ),
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
            context["principal"] = _build_consultant_dashboard_context(request)
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

from __future__ import annotations

from collections import Counter
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.http import QueryDict
from django.shortcuts import redirect, render

from App_PADESCE.appels.models import Appel, AppelImportArchive
from App_PADESCE.core.access import require_superadmin_access
from App_PADESCE.formations.models import Classe
from App_PADESCE.reporting.network_excel import (
    build_consolidation_call_candidates,
    normalize_network_lookup,
)

DEFAULT_STATUT_PRESTATION = "TERMINÉ"
PENDING_PAGE_SIZE = 50
FILTER_FIELD_MAP = {
    "classe": "classe_label",
    "prestataire": "prestataire",
    "beneficiaire": "beneficiaire",
    "formation": "formation_padesce",
    "cohorte": "cohorte",
    "fenetre": "fenetre",
    "statut_prestation": "statut_prestation",
}
SEARCH_FIELDS = (
    "code",
    "nom",
    "prestataire",
    "beneficiaire",
    "formation_padesce",
    "classe_label",
    "cohorte",
    "fenetre",
    "telephone1",
    "telephone2",
)


def _consolidation_filters_from_params(params) -> dict:
    statut_value = str(params.get("statut_prestation") or "").strip() or DEFAULT_STATUT_PRESTATION
    return {
        "q": str(params.get("q") or "").strip(),
        "classe": str(params.get("classe") or "").strip(),
        "prestataire": str(params.get("prestataire") or "").strip(),
        "beneficiaire": str(params.get("beneficiaire") or "").strip(),
        "formation": str(params.get("formation") or "").strip(),
        "cohorte": str(params.get("cohorte") or "").strip(),
        "fenetre": str(params.get("fenetre") or "").strip(),
        "statut_prestation": statut_value,
    }


def _candidate_matches_filters(candidate: dict, filters: dict, skip_field: str = "") -> bool:
    search_value = filters.get("q", "")
    if skip_field != "q" and search_value:
        haystack = " ".join(str(candidate.get(field) or "") for field in SEARCH_FIELDS)
        if normalize_network_lookup(search_value) not in normalize_network_lookup(haystack):
            return False

    for filter_name, candidate_field in FILTER_FIELD_MAP.items():
        if filter_name == skip_field:
            continue
        expected = str(filters.get(filter_name) or "").strip()
        if not expected:
            continue
        if normalize_network_lookup(candidate.get(candidate_field, "")) != normalize_network_lookup(
            expected
        ):
            return False
    return True


def _filtered_candidates(candidates: list[dict], filters: dict) -> list[dict]:
    return [candidate for candidate in candidates if _candidate_matches_filters(candidate, filters)]


def _build_filter_options(candidates: list[dict], filters: dict) -> dict:
    options: dict[str, list[dict]] = {}
    for filter_name, candidate_field in FILTER_FIELD_MAP.items():
        related_candidates = [
            candidate
            for candidate in candidates
            if _candidate_matches_filters(candidate, filters, skip_field=filter_name)
        ]
        counts = Counter(
            str(candidate.get(candidate_field) or "").strip()
            for candidate in related_candidates
            if str(candidate.get(candidate_field) or "").strip()
        )
        current_value = str(filters.get(filter_name) or "").strip()
        if current_value and current_value not in counts:
            counts[current_value] = 0
        options[filter_name] = [
            {
                "value": value,
                "label": f"{value} ({counts[value]})" if counts[value] else value,
            }
            for value in sorted(counts.keys(), key=lambda item: normalize_network_lookup(item))
        ]
    return options


def _sorted_candidates(candidates: list[dict]) -> list[dict]:
    return sorted(
        candidates,
        key=lambda candidate: (
            normalize_network_lookup(candidate.get("classe_label", "")),
            normalize_network_lookup(candidate.get("prestataire", "")),
            normalize_network_lookup(candidate.get("beneficiaire", "")),
            normalize_network_lookup(candidate.get("nom", "")),
            normalize_network_lookup(candidate.get("code", "")),
        ),
    )


def _build_pending_dataset(filters: dict, *, force_refresh: bool = False) -> dict:
    bundle = build_consolidation_call_candidates(force_refresh=force_refresh)
    existing_codes = {
        normalize_network_lookup(code)
        for code in Appel.objects.exclude(code="").values_list("code", flat=True)
        if code
    }
    source_candidates = _sorted_candidates(bundle["records"])
    pending_candidates = [
        candidate
        for candidate in source_candidates
        if normalize_network_lookup(candidate.get("code", "")) not in existing_codes
    ]
    filtered = _filtered_candidates(pending_candidates, filters)
    options = _build_filter_options(pending_candidates, filters)
    return {
        "source": bundle["source"],
        "sheet_name": bundle["sheet_name"],
        "source_rows": bundle["source_rows"],
        "source_count": bundle["count"],
        "pending_candidates": pending_candidates,
        "filtered_candidates": filtered,
        "options": options,
        "already_loaded_count": max(bundle["count"] - len(pending_candidates), 0),
        "duplicate_code_count": len(bundle["duplicate_codes"]),
    }


def _candidate_to_appel_defaults(candidate: dict) -> dict:
    return {
        "code": str(candidate.get("code") or "").strip(),
        "nom": str(candidate.get("nom") or "").strip(),
        "prestataire": str(candidate.get("prestataire") or "").strip(),
        "beneficiaire": str(candidate.get("beneficiaire") or "").strip(),
        "lieu": str(candidate.get("lieu") or candidate.get("ville_formation") or "").strip(),
        "classe_label": str(candidate.get("classe_label") or "").strip(),
        "fenetre": str(candidate.get("fenetre") or "").strip(),
        "telephone1": str(candidate.get("telephone1") or "").strip(),
        "telephone2": str(candidate.get("telephone2") or "").strip(),
        "taux_presence": Decimal("0"),
        "status": "en_attente",
        "type_formation_declaree": str(candidate.get("type_formation_declaree") or "").strip(),
        "formation_padesce": str(candidate.get("formation_padesce") or "").strip(),
        "is_active": True,
    }


def _create_appels_from_candidates(candidates: list[dict]) -> tuple[int, int]:
    created = 0
    skipped = 0
    existing_codes = {
        normalize_network_lookup(code)
        for code in Appel.objects.exclude(code="").values_list("code", flat=True)
        if code
    }

    for candidate in candidates:
        code = str(candidate.get("code") or "").strip()
        if not code:
            skipped += 1
            continue

        code_key = normalize_network_lookup(code)
        if code_key in existing_codes or Appel.objects.filter(code__iexact=code).exists():
            skipped += 1
            continue

        defaults = _candidate_to_appel_defaults(candidate)
        classe_obj = None
        if defaults["classe_label"]:
            classe_obj = Classe.objects.filter(code__iexact=defaults["classe_label"]).first()

        appel = Appel.objects.create(**defaults, classe=classe_obj)
        AppelImportArchive.objects.create(
            appel=appel,
            import_mode="network_consolidation",
            source_code=appel.code,
            snapshot=candidate,
        )
        existing_codes.add(code_key)
        created += 1

    return created, skipped


def _redirect_with_query(request):
    return_query = str(request.POST.get("return_query") or "").strip()
    if return_query:
        return redirect(f"{request.path}?{return_query}")
    return redirect(request.path)


@require_superadmin_access
@transaction.atomic
def consolidation_pending_appels(request):
    modal_mode = request.GET.get("modal") == "1"
    if request.method == "POST":
        query_params = QueryDict(str(request.POST.get("return_query") or ""), mutable=False)
        filters = _consolidation_filters_from_params(query_params)
        dataset = _build_pending_dataset(filters)
        action = str(request.POST.get("action") or "").strip()

        if action == "create_one":
            code = str(request.POST.get("code") or "").strip()
            targets = [
                candidate
                for candidate in dataset["pending_candidates"]
                if normalize_network_lookup(candidate.get("code", ""))
                == normalize_network_lookup(code)
            ][:1]
        elif action == "create_batch":
            try:
                batch_size = max(int(str(request.POST.get("batch_size") or "0").strip()), 0)
            except ValueError:
                batch_size = 0
            if batch_size <= 0:
                messages.error(request, "Renseignez un nombre valide pour le chargement par lot.")
                return _redirect_with_query(request)
            targets = dataset["filtered_candidates"][:batch_size]
        elif action == "create_filtered":
            targets = dataset["filtered_candidates"]
        elif action == "create_all_available":
            targets = dataset["pending_candidates"]
        else:
            messages.error(request, "Action de chargement inconnue.")
            return _redirect_with_query(request)

        if not targets:
            messages.warning(request, "Aucun apprenant a charger pour cette selection.")
            return _redirect_with_query(request)

        created, skipped = _create_appels_from_candidates(targets)
        label = {
            "create_one": "Chargement unitaire",
            "create_batch": "Chargement par lot",
            "create_filtered": "Chargement du filtre",
            "create_all_available": "Chargement global",
        }.get(action, "Chargement")
        messages.success(
            request,
            f"{label} termine. {created} appel(s) cree(s), {skipped} deja present(s) ou ignore(s).",
        )
        return _redirect_with_query(request)

    filters = _consolidation_filters_from_params(request.GET)
    dataset = _build_pending_dataset(filters, force_refresh=request.GET.get("refresh") == "1")
    filtered_candidates = dataset["filtered_candidates"]

    paginator = Paginator(filtered_candidates, PENDING_PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    page_items = list(page_obj.object_list)
    page_start = page_obj.start_index() - 1 if page_items else 0
    filter_query = request.GET.copy()
    filter_query.pop("page", None)

    return render(
        request,
        "appels/consolidation_pending.html",
        {
            "base_template": "appels/modal_shell.html" if modal_mode else "base.html",
            "modal_mode": modal_mode,
            "filters": filters,
            "options": dataset["options"],
            "source_name": dataset["source"]["name"],
            "source_modified_label": dataset["source"]["modified_label"],
            "sheet_name": dataset["sheet_name"],
            "source_count": dataset["source_count"],
            "source_rows": dataset["source_rows"],
            "pending_count": len(dataset["pending_candidates"]),
            "filtered_count": len(filtered_candidates),
            "already_loaded_count": dataset["already_loaded_count"],
            "duplicate_code_count": dataset["duplicate_code_count"],
            "page_obj": page_obj,
            "paginator": paginator,
            "candidates": page_items,
            "page_count": len(page_items),
            "page_start": page_start,
            "filter_query_string": filter_query.urlencode(),
        },
    )

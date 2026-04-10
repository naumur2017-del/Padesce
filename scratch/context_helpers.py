import json

from django.core.paginator import Paginator
from django.db.models import Count, Q


# Helper functions for the toggle
def _consultant_dashboard_target(request):
    target = request.GET.get("target") or "apprenants"
    if target not in ["apprenants", "formateurs"]:
        return "apprenants"
    return target


def _consultant_formateur_display_name(row):
    return row.source_contact or row.reference_code or "Formateur inconnu"


def _consultant_formateurs_dashboard_context(request):
    from App_PADESCE.appels.models import (
        AppelFormateur,
        formateur_has_any_audio,
        formateur_has_any_form_data,
    )

    search = (request.GET.get("q") or "").strip()
    cohorte_filter = (request.GET.get("cohorte") or "").strip()
    formation_filter = (request.GET.get("formation") or "").strip()
    status_filter = (request.GET.get("status") or "").strip()

    rows_qs = AppelFormateur.objects.filter(is_active=True).exclude(status="en_attente")

    if search:
        rows_qs = rows_qs.filter(
            Q(source_contact__icontains=search)
            | Q(reference_code__icontains=search)
            | Q(telephone__icontains=search)
            | Q(formation__icontains=search)
        )
    if cohorte_filter:
        rows_qs = rows_qs.filter(cohorte__iexact=cohorte_filter)
    if formation_filter:
        rows_qs = rows_qs.filter(formation__iexact=formation_filter)
    if status_filter:
        rows_qs = rows_qs.filter(status=status_filter)

    rows = list(rows_qs.order_by("source_contact", "reference_code", "pk"))
    for row in rows:
        row.consultant_display_name = _consultant_formateur_display_name(row)
        row.consultant_reference = row.reference_code or "-"
        row.consultant_scope_label = row.formation or "-"
        row.consultant_telephone = row.telephone or "-"
        row.consultant_has_audio = formateur_has_any_audio(row)
        row.consultant_has_form = formateur_has_any_form_data(row)
        # Normalization for template compatibility
        row.nom = row.consultant_display_name
        row.apprenant_id = row.consultant_reference
        row.classe_label = row.consultant_scope_label
        row.telephone1 = row.consultant_telephone
        row.telephone2 = None
        row.consultant_class_display = row.consultant_scope_label
        row.classe = None

    # Stats aggregation
    stats_qs = AppelFormateur.objects.filter(is_active=True).exclude(status="en_attente")
    stats = stats_qs.aggregate(
        appels_cibles=Count("id"),
        tentes=Count("id", filter=~Q(status="en_attente")),
        reussis=Count(
            "id",
            filter=Q(
                status__in=["formulaire_rempli", "formulaire_avec_audio", "termine", "appel_reussi"]
            ),
        ),
        forms=Count("id", filter=Q(status__in=["formulaire_rempli", "formulaire_avec_audio"])),
        audios=Count("id", filter=Q(status="formulaire_avec_audio")),
    )
    form_remplis = stats["forms"] or 0
    form_audio = stats["audios"] or 0

    # Paginator
    paginator = Paginator(rows, 25)
    page_number = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page_number)
    except:
        page_obj = paginator.page(1)

    # Filter Map
    _filter_rows = []
    for row in stats_qs:
        _filter_rows.append(
            {
                "beneficiaire": (row.beneficiaire or "").strip(),
                "prestataire": (row.prestataire or "").strip(),
                "formation": (row.formation or "").strip(),
                "cohorte": (row.cohorte or "").strip(),
            }
        )

    return {
        "rows": list(page_obj.object_list),
        "page_obj": page_obj,
        "paginator": paginator,
        "filters": {
            "q": search,
            "cohorte": cohorte_filter,
            "formation": formation_filter,
            "status": status_filter,
            "formations": sorted(
                list(set(row["formation"] for row in _filter_rows if row["formation"]))
            ),
            "cohortes": sorted(list(set(row["cohorte"] for row in _filter_rows if row["cohorte"]))),
        },
        "filter_map_json": json.dumps(_filter_rows, ensure_ascii=False),
        "total_rows": len(rows),
        "summary_appels_cibles": stats["appels_cibles"] or 0,
        "summary_tentes": stats["tentes"] or 0,
        "summary_reussis": stats["reussis"] or 0,
        "summary_form_remplis": form_remplis,
        "summary_form_sans_audio": max(form_remplis - form_audio, 0),
        "summary_form_audio": form_audio,
        "summary_audios": stats["audios"] or 0,
        "consultant_mode": "formateurs",
        "card_primary_label": "Formations analysées",
        "card_secondary_label": "Cohortes analysées",
        "panel_title": "Appels PADESCE formateurs terminés",
        "panel_subtitle": "Les audios de plus d'une minute remontent en tête. Cliquez sur une ligne pour ouvrir le dossier complet.",
        "search_placeholder": "Recherche formateur.",
        "table_col_name_label": "Nom formateur",
        "table_col_id_label": "Référence",
        "table_col_scope_label": "Formation",
        "table_empty_message": "Aucun appel formateur terminé à consulter.",
        "detail_url_name": "analysis_formateur_call_detail",
    }

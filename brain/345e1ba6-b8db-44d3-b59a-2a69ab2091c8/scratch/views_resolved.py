import json
from datetime import date

from django.core.paginator import Paginator
from django.db.models import Q

from App_PADESCE.appels.models import (
    AppelFormateur,
    formateur_has_any_form_data,
)

# ... (Previous imports and helpers remain)


def _consultant_dashboard_target(request):
    return (request.GET.get("target") or "apprenants").lower()


def _consultant_formateurs_dashboard_context(request):
    search = (request.GET.get("q") or "").strip()
    cohorte_filter = (request.GET.get("cohorte") or "").strip()
    formation_filter = (request.GET.get("formation") or "").strip()
    status_filter = (request.GET.get("status") or "").strip()

    rows_qs = AppelFormateur.objects.filter(is_active=True).exclude(status="en_attente")
    if search:
        rows_qs = rows_qs.filter(
            Q(prestataire__icontains=search)
            | Q(beneficiaire__icontains=search)
            | Q(formation__icontains=search)
            | Q(telephone__icontains=search)
        )
    if cohorte_filter:
        rows_qs = rows_qs.filter(cohorte__iexact=cohorte_filter)
    if formation_filter:
        rows_qs = rows_qs.filter(formation__iexact=formation_filter)
    if status_filter:
        rows_qs = rows_qs.filter(status=status_filter)

    from App_PADESCE.appels.formateurs_views import _resolve_classe_for_formateur_row

    rows = list(rows_qs.order_by("source_contact", "reference_code", "pk"))
    for row in rows:
        classe = _resolve_classe_for_formateur_row(row)
        formateur = classe.formateur if (classe and getattr(classe, "formateur", None)) else None

        if formateur:
            row.consultant_display_name = formateur.nom_complet
            row.consultant_reference = formateur.code
        else:
            row.consultant_display_name = (row.beneficiaire or "").strip() or (
                row.prestataire or "Formateur"
            )
            row.consultant_reference = row.telephone or row.reference_code or "-"

        row.consultant_scope_label = row.formation or "-"
        row.consultant_telephone = row.telephone or "-"

        # Only count audio if file physically exists
        row.consultant_has_audio = False
        if row.audio_file and row.audio_file.name:
            try:
                row.consultant_has_audio = row.audio_file.storage.exists(row.audio_file.name)
            except Exception:
                pass

        row.consultant_has_form = formateur_has_any_form_data(row)
        row.nom = row.consultant_display_name
        row.apprenant_id = row.consultant_reference
        row.classe_label = row.consultant_scope_label
        row.telephone1 = row.consultant_telephone
        row.telephone2 = None
        row.consultant_class_display = row.consultant_scope_label
        row.classe = classe

    stats_qs = AppelFormateur.objects.filter(is_active=True)

    tentes_qs = stats_qs.exclude(status="en_attente")
    tentes_count = tentes_qs.count()
    summary_reussis = tentes_count
    summary_form_remplis = 0
    summary_form_audio = 0
    all_active_tentes = list(tentes_qs)

    for item in all_active_tentes:
        has_form = formateur_has_any_form_data(item)
        if has_form:
            summary_form_remplis += 1
            if item.audio_file and item.audio_file.name:
                try:
                    if item.audio_file.storage.exists(item.audio_file.name):
                        summary_form_audio += 1
                except Exception:
                    pass

    summary_form_sans_audio = summary_form_remplis - summary_form_audio
    stats_counts = {
        "appels_cibles": stats_qs.count(),
        "tentes": tentes_count,
        "reussis": summary_reussis,
        "forms": summary_form_remplis,
        "forms_audio": summary_form_audio,
        "forms_sans_audio": summary_form_sans_audio,
        "audios_total": summary_form_audio,
    }

    completed_qs = stats_qs.filter(
        status__in=["formulaire_rempli", "formulaire_avec_audio", "termine", "appel_reussi"]
    )
    card_formations = completed_qs.values_list("formation", flat=True).distinct().count()
    card_cohortes = completed_qs.values_list("cohorte", flat=True).distinct().count()
    card_prestataires = completed_qs.values_list("prestataire", flat=True).distinct().count()
    card_beneficiaires = completed_qs.values_list("beneficiaire", flat=True).distinct().count()

    rows.sort(
        key=lambda x: (
            getattr(x, "consultant_has_form", False) and getattr(x, "consultant_has_audio", False),
            getattr(x, "session_date", date.min) or date.min,
        ),
        reverse=True,
    )

    paginator = Paginator(rows, 25)
    page_number = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page_number)
    except Exception:
        page_obj = paginator.page(1)

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

    def fmt(val):
        return f"{int(val or 0):,}".replace(",", " ")

    return {
        "rows": list(page_obj.object_list),
        "page_obj": page_obj,
        "paginator": paginator,
        "filters": {
            "q": search,
            "cohorte": cohorte_filter,
            "formation": formation_filter,
            "status": status_filter,
            "formations": sorted(list(set(r["formation"] for r in _filter_rows if r["formation"]))),
            "cohortes": sorted(list(set(r["cohorte"] for r in _filter_rows if r["cohorte"]))),
            "prestataires": sorted(
                list(set(r["prestataire"] for r in _filter_rows if r["prestataire"]))
            ),
            "beneficiaires": sorted(
                list(set(r["beneficiaire"] for r in _filter_rows if r["beneficiaire"]))
            ),
        },
        "filter_map_json": json.dumps(_filter_rows, ensure_ascii=False),
        "total_rows": len(rows),
        "summary_appels_cibles": fmt(stats_counts["appels_cibles"]),
        "summary_tentes": fmt(stats_counts["tentes"]),
        "summary_reussis": fmt(stats_counts["reussis"]),
        "summary_form_remplis": fmt(stats_counts["forms"]),
        "summary_form_audio": fmt(stats_counts["forms_audio"]),
        "summary_form_sans_audio": fmt(stats_counts["forms_sans_audio"]),
        "summary_audios": fmt(stats_counts["audios_total"]),
        "card_prestations_count": fmt(card_formations),
        "card_classes_count": fmt(card_cohortes),
        "card_prestataires_count": fmt(card_prestataires),
        "card_beneficiaires_count": fmt(card_beneficiaires),
        "consultant_mode": "formateurs",
        "card_primary_label": "Formations analysées",
        "card_secondary_label": "Cohortes analysées",
        "panel_title": "Appels PADESCE formateurs terminés",
        "panel_subtitle": "Cliquez sur une ligne pour ouvrir le dossier complet.",
        "search_placeholder": "Recherche formateur.",
        "table_col_name_label": "Nom formateur",
        "table_col_id_label": "ID Formateur",
        "table_col_scope_label": "Formation",
        "table_empty_message": "Aucun appel formateur terminé à consulter.",
        "detail_url_name": "analysis_formateur_call_detail",
    }

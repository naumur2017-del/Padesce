import io
import re
from collections import defaultdict

import openpyxl
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from App_PADESCE.appels.models import AppelPasFormeII
from App_PADESCE.appels.pagination import build_pagination_tokens
from App_PADESCE.appels.thresholds import (
    PAS_FORME_II_THRESHOLD_PERCENT,
    pas_forme_ii_threshold_target,
)


def _header(value):
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def _phone(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[-9:] if len(digits) > 9 else digits


def _number(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _boolean(value):
    return _header(value) in {"1", "oui", "yes", "true", "vrai", "x"}


def _parse(file_obj):
    ws = openpyxl.load_workbook(file_obj, read_only=True, data_only=True)["Feuil1"]
    rows = ws.iter_rows(values_only=True)
    headers = next(rows, None) or []
    lookup = {_header(v): i for i, v in enumerate(headers)}

    def get(row, key):
        i = lookup.get(key)
        return row[i] if i is not None and i < len(row) else ""

    result = []
    for row in rows:
        prestation = str(get(row, "prestation id") or "").strip()
        nom = str(get(row, "apprenants") or "").strip()
        if not prestation or not nom:
            continue
        phone = _phone(get(row, "numero"))
        nom_key = re.sub(r"[^a-z0-9]+", "-", nom.lower()).strip("-")
        ref = f"{prestation}-{phone or 'sans-tel'}-{nom_key}"[:160]
        result.append(
            {
                "reference_code": ref,
                "prestation_id": prestation,
                "nom": nom,
                "telephone": phone,
                "beneficiaire": str(get(row, "beneficiaires") or "").strip(),
                "prestataire": str(get(row, "prestataires") or "").strip(),
                "genre": str(get(row, "genre") or "").strip(),
                "fenetre": str(get(row, "fenetre") or "").strip(),
                "absent_dans_consolide": _boolean(get(row, "absent dans consolide")),
                "total_presence": _number(get(row, "total presence")),
                "total_seances": _number(get(row, "total seance")),
                "seuil_75": _number(get(row, "seuil 75%")),
                "nombre_seances_source": _number(get(row, "nombre seance")),
                "forme_final": str(get(row, "forme final") or "").strip(),
            }
        )
    return result


_SOURCE_FIELDS = (
    "prestation_id",
    "nom",
    "telephone",
    "beneficiaire",
    "prestataire",
    "genre",
    "fenetre",
    "absent_dans_consolide",
    "total_presence",
    "total_seances",
    "seuil_75",
    "nombre_seances_source",
    "forme_final",
)


def _comparison_sync(payload):
    """Synchronize visible rows while preserving every existing call and form field."""
    incoming_by_reference = {}
    duplicates = 0
    for item in payload:
        reference = item["reference_code"]
        if reference in incoming_by_reference:
            duplicates += 1
            continue
        incoming_by_reference[reference] = item

    existing_by_reference = {row.reference_code: row for row in AppelPasFormeII.objects.all()}
    now = timezone.now()
    to_create = []
    to_reactivate = []
    unchanged = 0

    for reference, item in incoming_by_reference.items():
        row = existing_by_reference.get(reference)
        if row is None:
            to_create.append(AppelPasFormeII(**item, is_active=True))
        elif row.is_active:
            # A row present on both sides must remain completely untouched.
            unchanged += 1
        else:
            # Restore the source data without altering the preserved call/form history.
            for field in _SOURCE_FIELDS:
                setattr(row, field, item[field])
            row.is_active = True
            row.updated_at = now
            to_reactivate.append(row)

    incoming_references = set(incoming_by_reference)
    deactivate_ids = [
        row.pk
        for reference, row in existing_by_reference.items()
        if row.is_active and reference not in incoming_references
    ]
    for start in range(0, len(deactivate_ids), 500):
        AppelPasFormeII.objects.filter(
            pk__in=deactivate_ids[start : start + 500]
        ).update(is_active=False, updated_at=now)

    if to_reactivate:
        AppelPasFormeII.objects.bulk_update(
            to_reactivate,
            [*_SOURCE_FIELDS, "is_active", "updated_at"],
            batch_size=500,
        )
    if to_create:
        AppelPasFormeII.objects.bulk_create(to_create, batch_size=500)

    return {
        "created": len(to_create),
        "reactivated": len(to_reactivate),
        "deactivated": len(deactivate_ids),
        "unchanged": unchanged,
        "duplicates": duplicates,
    }


def _thresholds():
    rows = (
        AppelPasFormeII.objects.filter(is_active=True)
        .values("prestation_id")
        .annotate(
            total=Count("id"),
            completed=Count("id", filter=Q(formulaire_rempli_at__isnull=False)),
        )
    )
    return [
        {
            **row,
            "target": pas_forme_ii_threshold_target(row["total"]),
            "pct": round(100 * row["completed"] / row["total"], 1)
            if row["total"]
            else 0,
        }
        for row in rows
    ]


@login_required
@transaction.atomic
def index(request):
    if request.method == "POST" and request.FILES.get("file"):
        if not request.user.is_superuser:
            messages.error(request, "Seul un superadmin peut importer."); return redirect(request.path_info)
        try: payload = _parse(io.BytesIO(request.FILES["file"].read()))
        except Exception as exc: messages.error(request, f"Impossible de lire le fichier : {exc}"); return redirect(request.path_info)
        action_name = request.POST.get("import_action", "add")
        if action_name == "compare_sync":
            if not payload:
                messages.error(
                    request,
                    "Comparaison annulée : le fichier ne contient aucune ligne exploitable.",
                )
                return redirect(request.path_info)
            result = _comparison_sync(payload)
            messages.success(
                request,
                (
                    "Comparaison et mise à jour terminées : "
                    f"{result['unchanged']} inchangés, "
                    f"{result['deactivated']} désactivés, "
                    f"{result['created']} ajoutés, "
                    f"{result['reactivated']} réactivés"
                    f" et {result['duplicates']} doublons du fichier ignorés."
                ),
            )
            return redirect(request.path_info)
        created = updated = duplicates = not_found = 0
        existing_by_reference = {
            row.reference_code: row
            for row in AppelPasFormeII.objects.filter(is_active=True)
        }
        for item in payload:
            row = existing_by_reference.get(item["reference_code"])
            if action_name == "update_segments":
                if not row:
                    not_found += 1
                    continue
                if row.genre != item["genre"] or row.fenetre != item["fenetre"]:
                    row.genre = item["genre"]
                    row.fenetre = item["fenetre"]
                    row.save(update_fields=["genre", "fenetre", "updated_at"])
                    updated += 1
                continue
            if row:
                duplicates += 1; continue
            AppelPasFormeII.objects.create(**item); created += 1
        if action_name == "update_segments":
            messages.success(request, f"Mise à jour terminée : {updated} genre/fenêtre actualisés, {not_found} lignes non trouvées.")
        else:
            messages.success(request, f"Import terminé : {created} ajoutés, {duplicates} doublons ignorés.")
        return redirect(request.path_info)
    rows = AppelPasFormeII.objects.filter(is_active=True)
    filters = {key: request.GET.get(key, "").strip() for key in ("status", "prestation", "prestataire", "beneficiaire", "genre", "fenetre", "q")}
    if filters["status"]: rows = rows.filter(status=filters["status"])
    if filters["prestation"]: rows = rows.filter(prestation_id=filters["prestation"])
    if filters["prestataire"]: rows = rows.filter(prestataire__icontains=filters["prestataire"])
    if filters["beneficiaire"]: rows = rows.filter(beneficiaire__icontains=filters["beneficiaire"])
    if filters["genre"]: rows = rows.filter(genre__iexact=filters["genre"])
    if filters["fenetre"]: rows = rows.filter(fenetre__iexact=filters["fenetre"])
    if filters["q"]: rows = rows.filter(Q(nom__icontains=filters["q"]) | Q(telephone__icontains=filters["q"]))
    all_rows = AppelPasFormeII.objects.filter(is_active=True)
    filters.update({"prestations": list(all_rows.values_list("prestation_id", flat=True).distinct().order_by("prestation_id")), "prestataires": list(all_rows.values_list("prestataire", flat=True).distinct().order_by("prestataire")), "beneficiaires": list(all_rows.values_list("beneficiaire", flat=True).distinct().order_by("beneficiaire")), "genres": list(all_rows.exclude(genre="").values_list("genre", flat=True).distinct().order_by("genre")), "fenetres": list(all_rows.exclude(fenetre="").values_list("fenetre", flat=True).distinct().order_by("fenetre"))})
    campaign_segments = list(all_rows.values("genre", "fenetre").annotate(total=Count("id"), completed=Count("id", filter=Q(formulaire_rempli_at__isnull=False)), successful=Count("id", filter=Q(status__in=["appel_reussi", "formulaire_rempli", "formulaire_avec_audio"]))).order_by("fenetre", "genre"))
    page_obj = Paginator(rows.order_by("prestation_id", "nom"), 50).get_page(request.GET.get("page", 1))
    threshold_map = {item["prestation_id"]: item for item in _thresholds()}
    params = request.GET.copy(); params.pop("page", None)
    return render(
        request,
        "appels/pas_forme_ii.html",
        {
            "rows": page_obj.object_list,
            "page_obj": page_obj,
            "pagination_tokens": build_pagination_tokens(page_obj),
            "querystring_no_page": params.urlencode(),
            "filters": filters,
            "thresholds": list(threshold_map.values()),
            "threshold_map": threshold_map,
            "campaign_segments": campaign_segments,
            "status_choices": AppelPasFormeII.STATUS_CHOICES,
            "pas_forme_ii_threshold_percent": PAS_FORME_II_THRESHOLD_PERCENT,
        },
    )


@login_required
@require_POST
@transaction.atomic
def save_form(request, pk):
    row = get_object_or_404(AppelPasFormeII, pk=pk)
    wants_json = request.headers.get("x-requested-with") == "XMLHttpRequest"

    if request.POST.get("action") == "rappeler":
        row.status = "a_rappeler"
        row.rappel_at = request.POST.get("rappel_at") or None
        row.locked_by = request.user
        row.save(update_fields=["status", "rappel_at", "locked_by", "updated_at"])
        if wants_json:
            return JsonResponse({"ok": True, "status": row.status})
        messages.success(request, "Rappel enregistré.")
        return redirect("pas_forme_ii_index")

    membre_structure = str(request.POST.get("q2", "")).strip().upper()
    nombre_seances = _number(request.POST.get("nombre_seances_declare"))
    if membre_structure not in {"OUI", "NON"} or nombre_seances is None or nombre_seances < 0:
        error = "Répondez par Oui ou Non et indiquez un nombre de séances valide."
        if wants_json:
            return JsonResponse({"ok": False, "error": error}, status=400)
        messages.error(request, error)
        return redirect("pas_forme_ii_index")

    faux_nom = request.POST.get("faux_nom") == "on"
    vrai_nom = str(request.POST.get("vrai_nom", "")).strip()
    if faux_nom and not vrai_nom:
        error = "Indiquez le vrai nom lorsque le nom déclaré est faux."
        if wants_json:
            return JsonResponse({"ok": False, "error": error}, status=400)
        messages.error(request, error)
        return redirect("pas_forme_ii_index")

    row.nombre_seances_declare = nombre_seances
    row.membre_structure = membre_structure
    row.est_forme = request.POST.get("est_forme") == "on"
    row.faux_nom = faux_nom
    row.vrai_nom = vrai_nom if faux_nom else ""
    row.commentaire = str(request.POST.get("commentaire", "")).strip()
    row.formulaire_rempli_at = timezone.now()
    row.status = "formulaire_avec_audio" if request.FILES.get("audio") else "formulaire_rempli"
    row.locked_by = request.user
    row.locked_at = None
    row.rappel_at = None
    if request.FILES.get("audio"):
        row.audio_file = request.FILES["audio"]
    row.save()

    if wants_json:
        return JsonResponse(
            {
                "ok": True,
                "status": row.status,
                "status_label": row.get_status_display(),
                "membre_structure": row.membre_structure,
                "nombre_seances_declare": row.nombre_seances_declare,
                "audio_url": row.audio_file.url if row.audio_file else "",
            }
        )
    messages.success(request, "Formulaire enregistré.")
    return redirect("pas_forme_ii_index")


def _can_edit(request, row):
    return request.user.is_superuser or (row.locked_by_id and row.locked_by_id == request.user.id)


@login_required
@require_POST
@transaction.atomic
def update_form(request, pk):
    row = get_object_or_404(AppelPasFormeII, pk=pk)
    wants_json = request.headers.get("x-requested-with") == "XMLHttpRequest"

    if not _can_edit(request, row):
        error = "Seul l'agent ayant traité cette fiche ou un administrateur peut la modifier."
        if wants_json:
            return JsonResponse({"ok": False, "error": error}, status=403)
        messages.error(request, error)
        return redirect("pas_forme_ii_index")

    telephone = _phone(request.POST.get("telephone", row.telephone))
    prestation_id = str(request.POST.get("prestation_id", "")).strip()
    membre_structure = str(request.POST.get("q2", "")).strip().upper()
    nombre_seances = _number(request.POST.get("nombre_seances_declare"))
    status = str(request.POST.get("status", "")).strip()
    faux_nom = request.POST.get("faux_nom") == "on"
    vrai_nom = str(request.POST.get("vrai_nom", "")).strip()
    remove_audio = request.POST.get("remove_audio") == "on"

    if not prestation_id:
        error = "La prestation est requise."
    elif membre_structure not in {"", "OUI", "NON"}:
        error = "Répondez par Oui ou Non pour l'appartenance à la structure."
    elif nombre_seances is not None and nombre_seances < 0:
        error = "Le nombre de séances déclaré est invalide."
    elif faux_nom and not vrai_nom:
        error = "Indiquez le vrai nom lorsque le nom déclaré est faux."
    elif status and status not in dict(AppelPasFormeII.STATUS_CHOICES):
        error = "Statut invalide."
    else:
        error = None

    if error:
        if wants_json:
            return JsonResponse({"ok": False, "error": error}, status=400)
        messages.error(request, error)
        return redirect("pas_forme_ii_index")

    row.telephone = telephone
    row.prestation_id = prestation_id
    row.membre_structure = membre_structure
    if nombre_seances is not None:
        row.nombre_seances_declare = nombre_seances
    row.faux_nom = faux_nom
    row.vrai_nom = vrai_nom if faux_nom else ""
    if status:
        row.status = status
    if request.FILES.get("audio"):
        row.audio_file = request.FILES["audio"]
    elif remove_audio and row.audio_file:
        row.audio_file.delete(save=False)
        row.audio_file = None
    row.save()

    if wants_json:
        return JsonResponse(
            {
                "ok": True,
                "telephone": row.telephone,
                "prestation_id": row.prestation_id,
                "membre_structure": row.membre_structure,
                "nombre_seances_declare": row.nombre_seances_declare,
                "faux_nom": row.faux_nom,
                "vrai_nom": row.vrai_nom,
                "status": row.status,
                "status_label": row.get_status_display(),
                "audio_url": row.audio_file.url if row.audio_file else "",
            }
        )
    messages.success(request, "Fiche mise à jour.")
    return redirect("pas_forme_ii_index")


@login_required
@require_POST
def action(request, pk):
    row = get_object_or_404(AppelPasFormeII, pk=pk)
    action_name = request.POST.get("action")
    if action_name in {"start", "resume"}: row.status, row.locked_by, row.locked_at = "en_cours", request.user, timezone.now()
    elif action_name == "pause": row.status = "pause"
    elif action_name == "reussi": row.status = "appel_reussi"
    else: return redirect("pas_forme_ii_index")
    row.save(update_fields=["status", "locked_by", "locked_at", "updated_at"])
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "status": row.status})
    return redirect("pas_forme_ii_index")

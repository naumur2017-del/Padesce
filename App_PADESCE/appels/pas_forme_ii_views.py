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


def _parse(file_obj):
    ws = openpyxl.load_workbook(file_obj, read_only=True, data_only=True)["Feuil1"]
    rows = ws.iter_rows(values_only=True); headers = next(rows, None) or []
    lookup = {_header(v): i for i, v in enumerate(headers)}
    def get(row, key):
        i = lookup.get(key); return row[i] if i is not None and i < len(row) else ""
    result = []
    for row in rows:
        prestation = str(get(row, "prestation id") or "").strip(); nom = str(get(row, "apprenants") or "").strip()
        if not prestation or not nom: continue
        phone = _phone(get(row, "numero")); ref = f"{prestation}-{phone or 'sans-tel'}-{re.sub(r'[^a-z0-9]+', '-', nom.lower()).strip('-')}"[:160]
        result.append({"reference_code": ref, "prestation_id": prestation, "nom": nom, "telephone": phone, "beneficiaire": str(get(row, "beneficiaires") or "").strip(), "prestataire": str(get(row, "prestataires") or "").strip(), "genre": str(get(row, "genre") or "").strip(), "absent_dans_consolide": bool(get(row, "absent dans consolide")), "total_presence": _number(get(row, "total presence")), "total_seances": _number(get(row, "total seance")), "seuil_75": _number(get(row, "seuil 75%")), "nombre_seances_source": _number(get(row, "nombre seance")), "forme_final": str(get(row, "forme final") or "").strip()})
    return result


def _thresholds():
    rows = AppelPasFormeII.objects.filter(is_active=True).values("prestation_id").annotate(total=Count("id"), completed=Count("id", filter=Q(formulaire_rempli_at__isnull=False)))
    return [{**row, "target": max(1, (row["total"] * 30 + 99) // 100), "pct": round(100 * row["completed"] / row["total"], 1) if row["total"] else 0} for row in rows]


@login_required
@transaction.atomic
def index(request):
    if request.method == "POST" and request.FILES.get("file"):
        if not request.user.is_superuser:
            messages.error(request, "Seul un superadmin peut importer."); return redirect(request.path_info)
        try: payload = _parse(io.BytesIO(request.FILES["file"].read()))
        except Exception as exc: messages.error(request, f"Impossible de lire le fichier : {exc}"); return redirect(request.path_info)
        created = updated = duplicates = 0
        for item in payload:
            row = AppelPasFormeII.objects.filter(reference_code=item["reference_code"]).first()
            if row:
                duplicates += 1; continue
            AppelPasFormeII.objects.create(**item); created += 1
        messages.success(request, f"Import terminé : {created} ajoutés, {duplicates} doublons ignorés.")
        return redirect(request.path_info)
    rows = AppelPasFormeII.objects.filter(is_active=True)
    filters = {key: request.GET.get(key, "").strip() for key in ("status", "prestation", "prestataire", "beneficiaire", "q")}
    if filters["status"]: rows = rows.filter(status=filters["status"])
    if filters["prestation"]: rows = rows.filter(prestation_id=filters["prestation"])
    if filters["prestataire"]: rows = rows.filter(prestataire__icontains=filters["prestataire"])
    if filters["beneficiaire"]: rows = rows.filter(beneficiaire__icontains=filters["beneficiaire"])
    if filters["q"]: rows = rows.filter(Q(nom__icontains=filters["q"]) | Q(telephone__icontains=filters["q"]))
    all_rows = AppelPasFormeII.objects.filter(is_active=True)
    filters.update({"prestations": list(all_rows.values_list("prestation_id", flat=True).distinct().order_by("prestation_id")), "prestataires": list(all_rows.values_list("prestataire", flat=True).distinct().order_by("prestataire")), "beneficiaires": list(all_rows.values_list("beneficiaire", flat=True).distinct().order_by("beneficiaire"))})
    page_obj = Paginator(rows.order_by("prestation_id", "nom"), 50).get_page(request.GET.get("page", 1))
    threshold_map = {item["prestation_id"]: item for item in _thresholds()}
    params = request.GET.copy(); params.pop("page", None)
    return render(request, "appels/pas_forme_ii.html", {"rows": page_obj.object_list, "page_obj": page_obj, "pagination_tokens": build_pagination_tokens(page_obj), "querystring_no_page": params.urlencode(), "filters": filters, "thresholds": list(threshold_map.values()), "threshold_map": threshold_map})


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

    row.nombre_seances_declare = nombre_seances
    row.membre_structure = membre_structure
    row.est_forme = request.POST.get("est_forme") == "on"
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

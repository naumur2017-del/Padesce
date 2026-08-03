import io
import re
from collections import defaultdict

import openpyxl
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from App_PADESCE.appels.models import AppelPasFormeII


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
    rows = AppelPasFormeII.objects.filter(is_active=True).order_by("prestation_id", "nom")
    return render(request, "appels/pas_forme_ii.html", {"rows": rows, "thresholds": _thresholds()})


@login_required
@require_POST
def save_form(request, pk):
    row = get_object_or_404(AppelPasFormeII, pk=pk)
    row.nombre_seances_declare = _number(request.POST.get("nombre_seances_declare"))
    row.formulaire_rempli_at = timezone.now(); row.status = "formulaire_rempli"; row.locked_by = request.user
    row.save(update_fields=["nombre_seances_declare", "formulaire_rempli_at", "status", "locked_by", "updated_at"])
    messages.success(request, "Formulaire enregistré.")
    return redirect("pas_forme_ii_index")

import csv
import datetime
import io
import unicodedata
import zipfile
from pathlib import Path

import openpyxl
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from App_PADESCE.appels.models import CALL_COMPLETED_STATUSES, AppelCGA
from App_PADESCE.appels.views import (
    _bind_audio_state,
    _build_progress_metrics,
    _cga_duplicate_key,
    _cleanup_stale_locks,
    _deactivate_duplicate_rows,
    _has_audio_file,
    _safe_audio_url,
)

IMPORT_BATCH_SIZE = 2000
PAGE_SIZE_DEFAULT = 100
PAGE_SIZE_MAX = 500


def _normalize_header(value):
    if value is None:
        return ""
    text = " ".join(str(value).strip().lower().split())
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _as_text(value):
    if value in (None, ""):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _iter_cga_excel_rows(file_obj):
    wb = openpyxl.load_workbook(file_obj, read_only=True, data_only=True)
    if "Sheet1" not in wb.sheetnames:
        raise ValueError("Sheet1 introuvable dans le fichier.")
    ws = wb["Sheet1"]
    rows = ws.iter_rows(values_only=True)
    header = next(rows, None)
    if not header:
        return
    header_map = {_normalize_header(col): idx for idx, col in enumerate(header)}

    def get(row, *keys):
        for key in keys:
            idx = header_map.get(_normalize_header(key))
            if idx is None or idx >= len(row):
                continue
            return row[idx]
        return None

    for row_index, row in enumerate(rows, start=2):
        numero_raw = get(row, "N°", "No", "N")
        niu = _as_text(get(row, "NIU"))
        raison = _as_text(get(row, "RAISON_SOCIALE"))
        if not raison:
            continue
        numero = None
        try:
            if numero_raw not in (None, ""):
                numero = int(float(numero_raw))
        except Exception:
            numero = None
        if not niu:
            fallback = numero if numero is not None else row_index
            niu = f"AUTO-{fallback}-{row_index}"
        yield {
            "numero": numero,
            "raison_sociale": raison,
            "sigle": _as_text(get(row, "SIGLE")),
            "niu": niu,
            "activite_principale": _as_text(get(row, "ACTIVITE_PRINCIPALE")),
            "regime": _as_text(get(row, "REGIME")),
            "cri": _as_text(get(row, "CRI")),
            "centre_de_rattachement": _as_text(get(row, "CENTRE_DE_RATTACHEMENT")),
            "ville": _as_text(get(row, "VILLE")),
            "telephone": _as_text(get(row, "TELEPHONE")),
        }


def _parse_bool_flag(value):
    if value is None:
        return None
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _build_filtered_cga_queryset(request):
    qs = AppelCGA.objects.filter(is_active=True).select_related("locked_by")
    status_filter = (request.GET.get("status") or "").strip()
    regime_filter = (request.GET.get("regime") or "").strip()
    cri_filter = (request.GET.get("cri") or "").strip()
    centre_filter = (request.GET.get("centre") or "").strip()
    ville_filter = (request.GET.get("ville") or "").strip()
    agent_filter = (request.GET.get("agent") or "").strip()
    date_from_str = (request.GET.get("date_from") or "").strip()
    date_to_str = (request.GET.get("date_to") or "").strip()
    search = (request.GET.get("q") or "").strip()

    if status_filter:
        if status_filter == "completed":
            qs = qs.filter(status__in=CALL_COMPLETED_STATUSES)
        else:
            qs = qs.filter(status=status_filter)
    if regime_filter:
        qs = qs.filter(regime__iexact=regime_filter)
    if cri_filter:
        qs = qs.filter(cri__iexact=cri_filter)
    if centre_filter:
        qs = qs.filter(centre_de_rattachement__iexact=centre_filter)
    if ville_filter:
        qs = qs.filter(ville__iexact=ville_filter)
    if agent_filter:
        qs = qs.filter(locked_by__username__iexact=agent_filter)
    if search:
        qs = qs.filter(
            Q(raison_sociale__icontains=search)
            | Q(sigle__icontains=search)
            | Q(niu__icontains=search)
            | Q(telephone__icontains=search)
        )
    if date_from_str:
        try:
            qs = qs.filter(created_at__gte=datetime.datetime.fromisoformat(date_from_str))
        except ValueError:
            pass
    if date_to_str:
        try:
            qs = qs.filter(created_at__lte=datetime.datetime.fromisoformat(date_to_str))
        except ValueError:
            pass

    filters = {
        "status": status_filter,
        "regime": regime_filter,
        "cri": cri_filter,
        "centre": centre_filter,
        "ville": ville_filter,
        "agent": agent_filter,
        "q": search,
        "date_from": date_from_str,
        "date_to": date_to_str,
        "regimes": sorted(
            {v.strip() for v in qs.exclude(regime="").values_list("regime", flat=True) if v}
        ),
        "cris": sorted({v.strip() for v in qs.exclude(cri="").values_list("cri", flat=True) if v}),
        "centres": sorted(
            {
                v.strip()
                for v in qs.exclude(centre_de_rattachement="").values_list(
                    "centre_de_rattachement", flat=True
                )
                if v
            }
        ),
        "villes": sorted(
            {v.strip() for v in qs.exclude(ville="").values_list("ville", flat=True) if v}
        ),
        "agents": sorted(
            {
                u.strip()
                for u in qs.exclude(locked_by__isnull=True).values_list(
                    "locked_by__username", flat=True
                )
                if u
            }
        ),
    }
    return qs, filters


def _flush_cga_batch(batch, *, ignore_conflicts=False):
    if not batch:
        return 0
    AppelCGA.objects.bulk_create(
        batch, batch_size=IMPORT_BATCH_SIZE, ignore_conflicts=ignore_conflicts
    )
    n = len(batch)
    batch.clear()
    return n


@login_required
def cga_export_xlsx(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(
        [
            "N°",
            "RAISON_SOCIALE",
            "SIGLE",
            "NIU",
            "ACTIVITE_PRINCIPALE",
            "REGIME",
            "CRI",
            "CENTRE_DE_RATTACHEMENT",
            "VILLE",
            "TELEPHONE",
            "STATUT",
            "RAPPEL_AT",
            "LOCKED_BY",
            "LOCKED_AT",
            "AUDIO_FILE",
            "CREATED_AT",
            "UPDATED_AT",
        ]
    )
    for row in (
        AppelCGA.objects.select_related("locked_by")
        .order_by("raison_sociale")
        .iterator(chunk_size=2000)
    ):
        ws.append(
            [
                row.numero,
                row.raison_sociale,
                row.sigle,
                row.niu,
                row.activite_principale,
                row.regime,
                row.cri,
                row.centre_de_rattachement,
                row.ville,
                row.telephone,
                row.status,
                row.rappel_at.isoformat() if row.rappel_at else "",
                row.locked_by.username if row.locked_by else "",
                row.locked_at.isoformat() if row.locked_at else "",
                _safe_audio_url(row),
                row.created_at.isoformat() if getattr(row, "created_at", None) else "",
                row.updated_at.isoformat() if getattr(row, "updated_at", None) else "",
            ]
        )
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="cga-export.xlsx"'
    wb.save(response)
    return response


@login_required
def cga_export_filtered_csv(request):
    qs, _ = _build_filtered_cga_queryset(request)
    rows = qs.order_by("status", "raison_sociale")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="cga-filtres.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(
        [
            "Numero",
            "Raison sociale",
            "Sigle",
            "NIU",
            "Activite principale",
            "Regime",
            "CRI",
            "Centre de rattachement",
            "Ville",
            "Telephone",
            "Statut",
            "Agent",
            "Rappel at",
            "Audio URL",
            "Created at",
            "Updated at",
        ]
    )
    for row in rows.iterator(chunk_size=2000):
        writer.writerow(
            [
                row.numero or "",
                row.raison_sociale,
                row.sigle,
                row.niu,
                row.activite_principale,
                row.regime,
                row.cri,
                row.centre_de_rattachement,
                row.ville,
                row.telephone,
                row.get_status_display(),
                row.locked_by.username if row.locked_by else "",
                row.rappel_at.isoformat() if row.rappel_at else "",
                _safe_audio_url(row),
                row.created_at.isoformat() if getattr(row, "created_at", None) else "",
                row.updated_at.isoformat() if getattr(row, "updated_at", None) else "",
            ]
        )
    return response


@login_required
def cga_index(request):
    if request.method == "POST" and request.FILES.get("file"):
        if not request.user.is_superuser:
            messages.error(request, "Seul un superadmin peut importer des fichiers CGA.")
            return redirect(request.path_info)
        mode = request.POST.get("update_mode", "replace")
        file_obj = io.BytesIO(request.FILES["file"].read())
        try:
            if mode == "replace":
                AppelCGA.objects.all().delete()
                batch = []
                seen = set()
                created = 0
                skipped = 0
                for item in _iter_cga_excel_rows(file_obj):
                    niu = item["niu"].strip()
                    if niu in seen:
                        skipped += 1
                        continue
                    seen.add(niu)
                    batch.append(AppelCGA(**item, is_active=True))
                    if len(batch) >= IMPORT_BATCH_SIZE:
                        created += _flush_cga_batch(batch)
                created += _flush_cga_batch(batch)
                deduped = _deactivate_duplicate_rows(
                    AppelCGA.objects.filter(is_active=True), _cga_duplicate_key
                )
                messages.success(
                    request,
                    (
                        f"Import CGA termine. {created} ligne(s) chargee(s), "
                        f"{skipped} doublon(s) ignores, {deduped} doublon(s) desactive(s)."
                    ),
                )
            elif mode == "append":
                seen_file = set()
                created = 0
                skipped = 0
                updated = 0
                for item in _iter_cga_excel_rows(file_obj):
                    niu = item["niu"].strip()
                    if niu in seen_file:
                        skipped += 1
                        continue
                    seen_file.add(niu)
                    row = AppelCGA.objects.filter(niu=niu).first()
                    if row:
                        for key, value in item.items():
                            setattr(row, key, value)
                        row.is_active = True
                        row.save()
                        updated += 1
                    else:
                        AppelCGA.objects.create(**item, is_active=True)
                        created += 1
                deduped = _deactivate_duplicate_rows(
                    AppelCGA.objects.filter(is_active=True), _cga_duplicate_key
                )
                messages.success(
                    request,
                    (
                        f"Import CGA termine. {created} nouvelle(s) ligne(s), "
                        f"{updated} mise(s) a jour, {skipped} doublon(s) dans le fichier, "
                        f"{deduped} doublon(s) desactive(s)."
                    ),
                )
            else:
                messages.error(request, "Mode d'import CGA inconnu.")
        except Exception as exc:
            messages.error(request, f"Impossible de lire le fichier CGA : {exc}")
        return redirect(request.path_info)

    qs, filters = _build_filtered_cga_queryset(request)
    total_count = qs.count()
    stats = _build_progress_metrics(qs)

    try:
        page_size = int(request.GET.get("page_size") or PAGE_SIZE_DEFAULT)
    except ValueError:
        page_size = PAGE_SIZE_DEFAULT
    page_size = max(25, min(page_size, PAGE_SIZE_MAX))

    paginator = Paginator(qs.order_by("status", "raison_sociale"), page_size)
    page_obj = paginator.get_page(request.GET.get("page"))
    rows = _bind_audio_state(list(page_obj.object_list))
    page_obj.object_list = rows
    params = request.GET.copy()
    params.pop("page", None)
    querystring_no_page = params.urlencode()

    return render(
        request,
        "appels/cga.html",
        {
            "rows": rows,
            "rows_count": total_count,
            "filters": filters,
            "page_obj": page_obj,
            "page_size": page_size,
            "querystring_no_page": querystring_no_page,
            "stats": stats,
        },
    )


@login_required
@require_POST
def cga_action(request, pk: int):
    # Clean up stale locks that may be blocking access
    _cleanup_stale_locks()

    row = get_object_or_404(AppelCGA, pk=pk)
    action = request.POST.get("action")
    rappel_at = request.POST.get("rappel_at")
    _parse_bool_flag(request.POST.get("deja_forme"))

    now = timezone.now()

    if action == "start":
        row.status = "en_cours"
        row.locked_by = request.user
        row.locked_at = now
    elif action == "pause":
        row.status = "pause"
    elif action == "resume":
        row.status = "en_cours"
        row.locked_by = request.user
        row.locked_at = now
    elif action == "rappeler":
        row.status = "a_rappeler"
        row.locked_by = request.user
        row.locked_at = now
        if rappel_at:
            try:
                row.rappel_at = datetime.datetime.fromisoformat(rappel_at)
            except ValueError:
                row.rappel_at = None
    elif action == "terminer":
        row.status = "termine"
    else:
        return JsonResponse({"ok": False, "error": "Action inconnue."}, status=400)

    row.save(update_fields=["status", "locked_by", "locked_at", "rappel_at", "updated_at"])
    return JsonResponse(
        {
            "ok": True,
            "status": row.status,
            "status_label": row.get_status_display(),
            "locked_by": row.locked_by.username if row.locked_by else "",
            "rappel_at": row.rappel_at.isoformat() if row.rappel_at else "",
        }
    )


@login_required
@require_POST
def cga_upload_audio(request, pk: int):
    row = get_object_or_404(AppelCGA, pk=pk)
    file_obj = request.FILES.get("audio")
    if not file_obj:
        return JsonResponse({"ok": False, "error": "Aucun fichier audio."}, status=400)
    row.audio_file = file_obj
    row.save(update_fields=["audio_file", "updated_at"])
    return JsonResponse({"ok": True, "audio_url": _safe_audio_url(row)})


@login_required
@require_POST
def download_cga_audios(request):
    ids = request.POST.getlist("ids")
    if not ids:
        return JsonResponse({"ok": False, "error": "Aucun appel selectionne."}, status=400)
    try:
        ids = [int(val) for val in ids]
    except ValueError:
        return JsonResponse({"ok": False, "error": "Identifiants invalides."}, status=400)

    rows = list(
        AppelCGA.objects.filter(pk__in=ids, audio_file__isnull=False).order_by("raison_sociale")
    )
    if not rows:
        return JsonResponse(
            {"ok": False, "error": "Aucun audio disponible pour la selection."}, status=404
        )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        written = 0
        for row in rows:
            if not _has_audio_file(row):
                continue
            try:
                with row.audio_file.open("rb") as audio:
                    suffix = Path(row.audio_file.name).suffix or ".mp3"
                    safe_name = (
                        f"{slugify(row.niu) or 'niu'}-"
                        f"{slugify(row.raison_sociale) or 'cga'}{suffix}"
                    )
                    archive.writestr(safe_name, audio.read())
                    written += 1
            except Exception:
                continue
        if written == 0:
            return JsonResponse({"ok": False, "error": "Pas d'audio recuperable."}, status=404)

    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="cga-audios.zip"'
    return response


@login_required
@require_POST
def cga_transcription_detail(request, pk: int):
    row = get_object_or_404(AppelCGA, pk=pk)
    try:
        obj, generated = _ensure_cga_transcription(row)
        return JsonResponse(
            {"ok": True, "generated": generated, "transcription": _transcription_to_payload(obj)}
        )
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)


@login_required
def cga_transcription_download(request, pk: int):
    row = get_object_or_404(AppelCGA, pk=pk)
    try:
        obj, _generated = _ensure_cga_transcription(row)
    except Exception as exc:
        return HttpResponse(str(exc), status=400, content_type="text/plain; charset=utf-8")
    response = HttpResponse(obj.transcription_text or "", content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="transcription-cga-{slugify(row.niu) or row.pk}.txt"'
    )
    return response


@login_required
@require_POST
def start_filtered_cga_transcription(request):
    qs, _ = _build_filtered_cga_queryset(request)
    jobs = _collect_jobs_from_cga(qs)
    ok, payload, status_code = _start_transcription_task(
        CGA_FILTERED_TRANSCRIPTION_TASK_KEY,
        jobs,
        "Transcription du tableau filtre CGA",
    )
    return JsonResponse(payload, status=status_code)


@login_required
def filtered_cga_transcription_status(request):
    return JsonResponse(
        {"ok": True, "status": _transcription_status_response(CGA_FILTERED_TRANSCRIPTION_TASK_KEY)}
    )


@login_required
@require_POST
def stop_filtered_cga_transcription(request):
    ok, payload, status_code = _stop_transcription_task(CGA_FILTERED_TRANSCRIPTION_TASK_KEY)
    return JsonResponse(payload, status=status_code)

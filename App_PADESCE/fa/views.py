import csv
import hashlib
import json
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from App_PADESCE.core.access import has_analysis_access, require_superadmin_access, user_group_names

from .forms import QuestionnaireForm
from .imports import import_records, records_from_file
from .models import CallAttempt, Enterprise, Recording
from .schema import QUESTIONS

OUTCOME_CODES = (
    "appel_tente",
    "appel_reussi",
    "a_rappeler",
    "injoignable",
    "numero_errone",
    "refus",
    "formulaire_avec_audio",
)
OUTCOMES = [(c, label) for c, label in Enterprise.STATUS_CHOICES if c in OUTCOME_CODES]
ACTIVE_CODES = ("en_cours", "pause")
FILTER_NAMES = ("q", "status", "sector", "city", "agent", "date_from", "date_to", "audio")


def _error(message, status=400, **extra):
    return JsonResponse({"ok": False, "error": message, **extra}, status=status)


def _can_analyze(user):
    return has_analysis_access(user) or "manager_fa" in user_group_names(user)


def _can_hear(user, attempt):
    return attempt.agent_id == user.pk or _can_analyze(user)


def _filtered(request):
    filters = {name: str(request.GET.get(name, "")).strip()[:255] for name in FILTER_NAMES}
    rows = Enterprise.objects.all()
    if filters["q"]:
        rows = rows.filter(
            Q(name__icontains=filters["q"])
            | Q(reference__icontains=filters["q"])
            | Q(phone__icontains=filters["q"])
            | Q(phone_raw__icontains=filters["q"])
            | Q(answers__q2_respondent__icontains=filters["q"])
        )
    for field in ("status", "sector", "city"):
        if filters[field]:
            rows = rows.filter(**{field: filters[field]})
    attempt_filter = CallAttempt.objects.filter(enterprise_id=OuterRef("pk"))
    has_attempt_filter = False
    if filters["agent"]:
        if filters["agent"].isdigit():
            attempt_filter = attempt_filter.filter(agent_id=int(filters["agent"]))
        else:
            rows = rows.none()
        has_attempt_filter = True
    for field, lookup in (("date_from", "gte"), ("date_to", "lt")):
        if filters[field]:
            try:
                value = parse_date(filters[field])
            except ValueError:
                value = None
            if value:
                if field == "date_to":
                    value += timedelta(days=1)
                value = timezone.make_aware(datetime.combine(value, time.min))
                attempt_filter = attempt_filter.filter(**{f"started_at__{lookup}": value})
            else:
                rows = rows.none()
            has_attempt_filter = True
    if has_attempt_filter:
        rows = rows.filter(Exists(attempt_filter))
    if filters["audio"] in {"yes", "no", "1", "0"}:
        has_audio = Exists(Recording.objects.filter(attempt__enterprise_id=OuterRef("pk")))
        rows = (
            rows.filter(has_audio) if filters["audio"] in {"yes", "1"} else rows.filter(~has_audio)
        )
    return rows, filters


def _attempt_scope(rows, request=None):
    attempts = CallAttempt.objects.filter(enterprise__in=rows)
    if request is None:
        return attempts
    agent = str(request.GET.get("agent", ""))
    if agent:
        attempts = attempts.filter(agent_id=int(agent)) if agent.isdigit() else attempts.none()
    for field, lookup in (("date_from", "gte"), ("date_to", "lt")):
        raw = request.GET.get(field, "")
        if not raw:
            continue
        try:
            date = parse_date(raw)
        except ValueError:
            date = None
        if not date:
            return attempts.none()
        if field == "date_to":
            date += timedelta(days=1)
        value = timezone.make_aware(datetime.combine(date, time.min))
        attempts = attempts.filter(**{f"started_at__{lookup}": value})
    return attempts


def _metrics(rows, request=None):
    counts = rows.aggregate(
        total=Count("pk"),
        pending=Count("pk", filter=Q(status="en_attente")),
        active=Count("pk", filter=Q(status__in=ACTIVE_CODES)),
        completed=Count("pk", filter=Q(status="formulaire_avec_audio")),
        callbacks=Count("pk", filter=Q(status="a_rappeler")),
        attempted=Count("pk", filter=~Q(status="en_attente")),
    )
    counts["completion_rate"] = (
        round(100 * counts["completed"] / counts["total"], 1) if counts["total"] else 0
    )
    attempts = _attempt_scope(rows, request)
    counts["attempts"] = attempts.count()
    counts["recordings"] = Recording.objects.filter(attempt__in=attempts).count()
    return counts


def _filter_context(request, filters):
    query = request.GET.copy()
    query.pop("page", None)
    return {
        "filters": filters,
        "statuses": Enterprise.STATUS_CHOICES,
        "sectors": list(
            Enterprise.objects.exclude(sector="")
            .order_by("sector")
            .values_list("sector", flat=True)
            .distinct()
        ),
        "cities": list(
            Enterprise.objects.exclude(city="")
            .order_by("city")
            .values_list("city", flat=True)
            .distinct()
        ),
        "agents": get_user_model()
        .objects.filter(fa_call_attempts__isnull=False)
        .distinct()
        .order_by("username"),
        "query_string": query.urlencode(),
        "can_import": request.user.is_superuser,
        "can_analyze": _can_analyze(request.user),
    }


@login_required
@require_GET
@never_cache
def index(request):
    rows, filters = _filtered(request)
    page_obj = Paginator(
        rows.select_related("assigned_to")
        .annotate(attempt_count=Count("attempts"))
        .order_by("name", "pk"),
        50,
    ).get_page(request.GET.get("page"))
    return render(
        request,
        "fa/index.html",
        {
            "enterprises": page_obj.object_list,
            "page_obj": page_obj,
            "metrics": _metrics(rows, request),
            **_filter_context(request, filters),
        },
    )


def _attempt_urls(attempt):
    return {
        "attempt_id": attempt.pk,
        "upload_url": reverse("fa_upload_audio", args=[attempt.pk]),
        "save_url": reverse("fa_save", args=[attempt.pk]),
        "finish_url": reverse("fa_finish", args=[attempt.pk]),
        "state_url": reverse("fa_state", args=[attempt.pk]),
    }


@login_required
@require_GET
@never_cache
def detail(request, pk):
    enterprise = get_object_or_404(Enterprise, pk=pk)
    attempts = list(
        enterprise.attempts.select_related("agent").prefetch_related("recordings")[:100]
    )
    attempt = next((item for item in attempts if item.ended_at is None), None)
    for item in attempts:
        recordings = list(item.recordings.all())
        allowed = _can_hear(request.user, item)
        item.latest_audio_url = (
            reverse("fa_audio", args=[recordings[-1].pk]) if recordings and allowed else ""
        )
        item.audio_history = recordings if allowed else []
        item.audio_entries = recordings if allowed else []
        for recording in recordings:
            recording.audio_url = reverse("fa_audio", args=[recording.pk]) if allowed else ""
            recording.url = recording.audio_url
    initial = {
        "q1_name": enterprise.name,
        "q4_phone": enterprise.phone,
        "q5_city": enterprise.city,
        "q8_sector": enterprise.sector,
        "q22_currency": "FCFA",
        **enterprise.answers,
    }
    form = QuestionnaireForm(initial=initial)
    urls = _attempt_urls(attempt) if attempt else {}
    next_sequence = (
        max((r.sequence for r in attempt.recordings.all()), default=-1) + 1 if attempt else 1
    )
    is_owner = bool(attempt and (attempt.agent_id == request.user.pk or request.user.is_superuser))
    context = {
        "enterprise": enterprise,
        "attempt": attempt,
        "attempts": attempts,
        "form": form,
        "form_sections": form.sections,
        "outcomes": OUTCOMES,
        "current_attempt_id": attempt.pk if attempt else "",
        "current_attempt_next_sequence": next_sequence,
        "next_sequence": next_sequence,
        "can_edit": not attempt or is_owner,
        "is_owner": is_owner,
        "start_url": reverse("fa_start", args=[pk]),
        "detail_url": reverse("fa_detail", args=[pk]),
        **{f"attempt_{key}": value for key, value in urls.items() if key.endswith("_url")},
    }
    return render(request, "fa/detail.html", context)


def _read_audio(request, *, first=False, final=False):
    uploaded = request.FILES.get("audio")
    if not uploaded or not uploaded.size:
        raise ValueError("L’enregistrement audio est obligatoire.")
    if uploaded.size > 64 * 1024 * 1024:
        raise ValueError("L’enregistrement dépasse 64 Mo. Conservez les segments et réessayez.")
    content = uploaded.read()
    if len(content) < 32:
        raise ValueError("Le fichier audio est vide ou incomplet.")
    kind = str(uploaded.content_type or "audio/webm").split(";", 1)[0]
    allowed = {
        "audio/webm": "webm",
        "video/webm": "webm",
        "audio/ogg": "ogg",
        "audio/mp4": "m4a",
        "audio/mpeg": "mp3",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
    }
    if kind not in allowed:
        raise ValueError("Format audio non pris en charge.")
    if first or final or request.POST.get("full") == "1":
        valid_header = (
            content.startswith((b"\x1aE\xdf\xa3", b"OggS", b"RIFF", b"ID3"))
            or content[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")
            or content[4:8] == b"ftyp"
        )
        if not valid_header:
            raise ValueError("Le fichier ne contient pas un enregistrement audio reconnu.")
    return content, kind, allowed[kind]


def _save_recording(attempt, sequence, content, kind, ext, final=False):
    digest = hashlib.sha256(content).hexdigest()
    existing = attempt.recordings.filter(sequence=sequence).first()
    if existing:
        if existing.sha256 != digest or existing.is_final != final:
            raise ValueError("Cette séquence audio est déjà enregistrée avec un autre contenu.")
        return existing
    latest = attempt.recordings.order_by("-sequence").first()
    if latest and sequence <= latest.sequence:
        raise ValueError("Séquence audio périmée. Rechargez le formulaire pour reprendre.")
    return Recording.objects.create(
        attempt=attempt,
        sequence=sequence,
        audio_file=ContentFile(content, name=f"recording.{ext}"),
        is_final=final,
        content_type=kind,
        sha256=digest,
        byte_size=len(content),
    )


@login_required
@require_POST
@never_cache
def start(request, pk):
    try:
        token = uuid.UUID(request.POST.get("client_token", ""))
    except (ValueError, TypeError, AttributeError):
        return _error("Identifiant de session absent ou invalide.")
    previous = CallAttempt.objects.filter(client_token=token).first()
    if previous:
        if previous.enterprise_id != pk or previous.agent_id != request.user.pk:
            return _error("Session déjà utilisée.", 409)
        if previous.ended_at:
            return _error("Cet appel est déjà terminé.", 409)
        next_sequence = max(previous.recordings.values_list("sequence", flat=True), default=-1) + 1
        return JsonResponse(
            {
                "ok": True,
                "status": previous.status,
                "resumed": True,
                "next_sequence": next_sequence,
                **_attempt_urls(previous),
            }
        )
    try:
        content, kind, ext = _read_audio(request, first=True)
    except ValueError as exc:
        return _error(str(exc))
    try:
        with transaction.atomic():
            enterprise = get_object_or_404(Enterprise.objects.select_for_update(), pk=pk)
            current = enterprise.attempts.filter(ended_at__isnull=True).first()
            if current:
                return _error(
                    "Un appel est déjà en cours pour cette entreprise. Reprenez sa session.",
                    409,
                    attempt_id=current.pk,
                )
            supplied_phone = request.POST.get("q4_phone", "").strip()
            if supplied_phone:
                from .imports import normalize_phone

                normalized_phone = normalize_phone(supplied_phone)
                if not normalized_phone or not any(char.isdigit() for char in normalized_phone):
                    return _error("Renseignez un téléphone valide pour démarrer.")
                enterprise.phone = normalized_phone
                enterprise.answers = {**enterprise.answers, "q4_phone": supplied_phone[:255]}
            if not enterprise.phone:
                return _error("Renseignez le téléphone de l’entreprise avant de démarrer.")
            attempt = CallAttempt.objects.create(
                enterprise=enterprise,
                agent=request.user,
                client_token=token,
                answers=enterprise.answers,
            )
            _save_recording(attempt, 0, content, kind, ext)
            enterprise.status, enterprise.assigned_to, enterprise.callback_at = (
                "en_cours",
                request.user,
                None,
            )
            enterprise.save(
                update_fields=[
                    "status",
                    "assigned_to",
                    "callback_at",
                    "phone",
                    "answers",
                    "updated_at",
                ]
            )
    except IntegrityError:
        return _error("Un autre opérateur vient de démarrer cet appel. Rechargez la liste.", 409)
    return JsonResponse(
        {"ok": True, "status": attempt.status, "next_sequence": 1, **_attempt_urls(attempt)}
    )


def _owned_attempt(request, pk):
    attempt = get_object_or_404(
        CallAttempt.objects.select_for_update().select_related("enterprise"), pk=pk
    )
    if attempt.agent_id != request.user.pk and not request.user.is_superuser:
        return None, _error("Cet appel appartient à un autre opérateur.", 403)
    if attempt.ended_at:
        return None, _error("Cet appel est déjà terminé.", 409)
    return attempt, None


@login_required
@require_POST
@never_cache
def upload_audio(request, pk):
    try:
        sequence = int(request.POST.get("sequence", ""))
        if sequence < 1:
            raise ValueError("La séquence doit être positive.")
        final = request.POST.get("final") in {"1", "true"}
        content, kind, ext = _read_audio(request, final=final)
    except (ValueError, TypeError) as exc:
        return _error(str(exc) or "Séquence audio invalide.")
    with transaction.atomic():
        attempt, error = _owned_attempt(request, pk)
        if error:
            return error
        try:
            recording = _save_recording(attempt, sequence, content, kind, ext, final)
        except ValueError as exc:
            return _error(str(exc), 409)
        attempt.save(update_fields=["updated_at"])
    return JsonResponse(
        {
            "ok": True,
            "audio_saved": True,
            "recording_id": recording.pk,
            "audio_url": reverse("fa_audio", args=[recording.pk]),
            "sequence": sequence,
            "final": final,
        }
    )


def _save_answers(attempt, form, notes):
    attempt.answers = form.answers()
    attempt.answers["survey_metadata"] = {
        "reference": attempt.enterprise.reference,
        "attempt_id": attempt.pk,
        "interviewer": (
            attempt.agent.get_full_name() or attempt.agent.get_username() if attempt.agent else ""
        ),
        "channel": "Téléphone",
        "started_at": attempt.started_at.isoformat(),
        "declaration_at": (
            timezone.now().isoformat() if attempt.answers.get("declaration_confirmed") else ""
        ),
    }
    attempt.notes = str(notes or "")[:10000]
    attempt.save(update_fields=["answers", "notes", "updated_at"])
    enterprise = attempt.enterprise
    enterprise.answers = attempt.answers
    if attempt.answers.get("q4_phone"):
        from .imports import normalize_phone

        enterprise.phone = normalize_phone(attempt.answers["q4_phone"])
    enterprise.save(update_fields=["answers", "phone", "updated_at"])


@login_required
@require_POST
@never_cache
def save(request, pk):
    with transaction.atomic():
        attempt, error = _owned_attempt(request, pk)
        if error:
            return error
        form = QuestionnaireForm(request.POST)
        if not form.is_valid():
            return _error("Corrigez les réponses signalées.", errors=form.errors.get_json_data())
        _save_answers(attempt, form, request.POST.get("notes", attempt.notes))
    return JsonResponse({"ok": True, "saved": True, "updated_at": attempt.updated_at.isoformat()})


@login_required
@require_POST
@never_cache
def state(request, pk):
    status = {"pause": "pause", "resume": "en_cours"}.get(request.POST.get("action"))
    if not status:
        return _error("Action invalide.")
    with transaction.atomic():
        attempt, error = _owned_attempt(request, pk)
        if error:
            return error
        attempt.status = status
        attempt.save(update_fields=["status", "updated_at"])
        Enterprise.objects.filter(pk=attempt.enterprise_id).update(
            status=status, updated_at=timezone.now()
        )
    next_sequence = (
        attempt.recordings.order_by("-sequence").values_list("sequence", flat=True).first()
    )
    return JsonResponse({"ok": True, "status": status, "next_sequence": (next_sequence or 0) + 1})


@login_required
@require_POST
@never_cache
def finish(request, pk):
    status = request.POST.get("status", "")
    if status not in OUTCOME_CODES:
        return _error("Choisissez un résultat d’appel valide.")
    with transaction.atomic():
        attempt, error = _owned_attempt(request, pk)
        if error:
            return error
        latest_audio = attempt.recordings.order_by("-sequence").first()
        if not latest_audio or not latest_audio.is_final:
            return _error(
                "Arrêtez puis sauvegardez l’enregistrement complet avant de terminer cet appel."
            )
        data = request.POST if any(q["key"] in request.POST for q in QUESTIONS) else attempt.answers
        form = QuestionnaireForm(data, complete=status == "formulaire_avec_audio")
        if not form.is_valid():
            return _error(
                "Le questionnaire est incomplet ou comporte des erreurs.",
                errors=form.errors.get_json_data(),
            )
        callback = None
        if status == "a_rappeler":
            try:
                callback = parse_datetime(request.POST.get("callback_at", ""))
            except ValueError:
                callback = None
            if callback and timezone.is_naive(callback):
                callback = timezone.make_aware(callback)
            if not callback or callback <= timezone.now():
                return _error(
                    "Indiquez une date de rappel future.",
                    errors={"callback_at": [{"message": "Date future obligatoire."}]},
                )
        _save_answers(attempt, form, request.POST.get("notes", attempt.notes))
        attempt.status, attempt.ended_at, attempt.callback_at = status, timezone.now(), callback
        attempt.save(update_fields=["status", "ended_at", "callback_at", "updated_at"])
        Enterprise.objects.filter(pk=attempt.enterprise_id).update(
            status=status, callback_at=callback, updated_at=timezone.now()
        )
    return JsonResponse(
        {
            "ok": True,
            "status": status,
            "status_label": attempt.get_status_display(),
            "ended_at": attempt.ended_at.isoformat(),
        }
    )


@login_required
@require_GET
@never_cache
def audio(request, pk):
    recording = get_object_or_404(Recording.objects.select_related("attempt"), pk=pk)
    if not _can_hear(request.user, recording.attempt):
        return HttpResponse(
            "Accès réservé à l’opérateur de l’appel et aux responsables autorisés.", status=403
        )
    try:
        stream = recording.audio_file.open("rb")
    except OSError as exc:
        raise Http404("Enregistrement introuvable.") from exc
    response = FileResponse(
        stream,
        content_type=recording.content_type,
        as_attachment=request.GET.get("download") == "1",
        filename=f"FA-appel-{recording.attempt_id}-{recording.sequence}{Path(recording.audio_file.name).suffix}",
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_superadmin_access
@require_POST
def import_enterprises(request):
    uploaded = request.FILES.get("file") or request.FILES.get("enterprises")
    if not uploaded or uploaded.size > 10 * 1024 * 1024:
        messages.error(request, "Choisissez un registre .xlsx de moins de 10 Mo.")
        return redirect("fa_index")
    try:
        result = import_records(records_from_file(uploaded))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        messages.error(request, f"Import impossible : {exc}")
    else:
        messages.success(
            request,
            f"Import FA : {result['created']} entreprises créées, {result['updated']} existantes mises à jour.",
        )
        for warning in result["warnings"][:12]:
            messages.warning(request, warning)
    return redirect("fa_index")


def _analytics(rows, request=None):
    metrics = _metrics(rows, request)
    labels = dict(Enterprise.STATUS_CHOICES)
    statuses = [
        {**row, "label": labels.get(row["status"], row["status"])}
        for row in rows.order_by().values("status").annotate(count=Count("pk"))
    ]
    sectors = list(
        rows.order_by("sector")
        .values("sector")
        .annotate(
            count=Count("pk"), completed=Count("pk", filter=Q(status="formulaire_avec_audio"))
        )
    )
    answers_list = list(
        rows.filter(status="formulaire_avec_audio").values_list("answers", flat=True)
    )

    def distribution(key, multi=False):
        counter = {}
        for answers in answers_list:
            value = answers.get(key)
            for label in (value or []) if multi else ([value] if value else []):
                counter[label] = counter.get(label, 0) + 1
        return [
            {"label": label, "count": count}
            for label, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
        ]

    amounts = []
    for answers in answers_list:
        if answers.get("q12_need") == "Oui" and answers.get("q13_amount") not in (None, ""):
            try:
                value = Decimal(str(answers["q13_amount"]))
                if value.is_finite():
                    amounts.append(value)
            except InvalidOperation:
                continue
    total = sum(amounts, Decimal(0))
    financing = {
        "total_requested": total,
        "average_requested": total / len(amounts) if amounts else 0,
        "respondents_with_amount": len(amounts),
        "respondents": len(answers_list),
    }
    breakdowns = [
        {
            "label": q["label"],
            "respondents": sum(bool(a.get(q["key"])) for a in answers_list),
            "multiple": q["kind"] == "multi",
            "rows": distribution(q["key"], q["kind"] == "multi"),
        }
        for q in QUESTIONS
        if q["kind"] in {"choice", "multi"}
    ]
    attempts = _attempt_scope(rows, request)
    agents = list(
        attempts.order_by("agent__username")
        .values("agent_id", "agent__username")
        .annotate(
            count=Count("pk"), completed=Count("pk", filter=Q(status="formulaire_avec_audio"))
        )
    )
    recording_counts = {
        row["attempt__agent_id"]: row["count"]
        for row in Recording.objects.filter(attempt__in=attempts)
        .order_by()
        .values("attempt__agent_id")
        .annotate(count=Count("pk"))
    }
    for agent in agents:
        agent["label"] = agent["agent__username"] or "Compte supprimé"
        agent["recordings"] = recording_counts.get(agent["agent_id"], 0)
    context = {
        "metrics": metrics,
        "completion_rate": metrics["completion_rate"],
        "status_counts": statuses,
        "sector_counts": sectors,
        "funding_counts": distribution("q12_need"),
        "financing": financing,
        "funding_total": total,
        "funding_average": financing["average_requested"],
        "funding_amount_count": len(amounts),
        "agent_counts": agents,
        "answer_breakdowns": breakdowns,
    }
    context["chart_data"] = json.dumps(
        {"status_counts": statuses, "sector_counts": sectors, "funding": context["funding_counts"]},
        ensure_ascii=False,
    )
    return context


@login_required
@require_GET
@never_cache
def analytics(request):
    if not _can_analyze(request.user):
        return HttpResponse("Accès réservé aux managers et consultants.", status=403)
    rows, filters = _filtered(request)
    return render(
        request,
        "fa/analytics.html",
        {**_analytics(rows, request), **_filter_context(request, filters)},
    )


def _csv_safe(value):
    text = str(value if value is not None else "")
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


@login_required
@require_GET
@never_cache
def export(request):
    if not _can_analyze(request.user):
        return HttpResponse("Accès réservé aux managers et consultants.", status=403)
    rows, _filters = _filtered(request)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="FA-enquetes.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(
        [
            "Référence",
            "Entreprise",
            "Téléphone",
            "Ville",
            "Filière",
            "CA FCFA",
            "Statut",
            "Rappel",
            *[q["label"] for q in QUESTIONS],
        ]
    )
    for row in rows.iterator(chunk_size=500):
        values = [
            row.reference,
            row.name,
            row.phone,
            row.city,
            row.sector,
            row.annual_revenue_fcfa,
            row.get_status_display(),
            row.callback_at.isoformat() if row.callback_at else "",
        ]
        for question in QUESTIONS:
            value = row.answers.get(question["key"], "")
            values.append(" / ".join(value) if isinstance(value, list) else value)
        writer.writerow([_csv_safe(value) for value in values])
    return response

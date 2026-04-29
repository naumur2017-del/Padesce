import json

from django.contrib.auth.decorators import login_required
from django.db import OperationalError, ProgrammingError, models
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from App_PADESCE.appels.models import CallAlert
from App_PADESCE.core.models import UserActivity, UserActivityEvent


ALERT_TYPE_OPTIONS = [
    {
        "value": "appel_ne_demarre_pas",
        "label": "L'appel ne demarre pas",
        "description": "Le bouton demarrer ne lance pas l'appel ou ne repond pas.",
    },
    {
        "value": "micro_non_accessible",
        "label": "Micro non accessible",
        "description": "Le navigateur bloque le micro ou aucun son n'est capte.",
    },
    {
        "value": "statut_ne_change_pas",
        "label": "Le statut ne change pas",
        "description": "Le statut reste bloque apres une action.",
    },
    {
        "value": "appel_bloque_en_cours",
        "label": "Appel bloque en cours",
        "description": "La ligne reste en cours alors que l'appel est fini.",
    },
    {
        "value": "appel_bloque_pause",
        "label": "Appel bloque en pause",
        "description": "Impossible de reprendre ou terminer un appel en pause.",
    },
    {
        "value": "rappel_sans_date",
        "label": "Rappel sans date",
        "description": "Le rappel est coche mais la date n'est pas enregistree.",
    },
    {
        "value": "formulaire_non_enregistre",
        "label": "Formulaire non enregistre",
        "description": "Les reponses ou commentaires disparaissent apres validation.",
    },
    {
        "value": "audio_non_enregistre",
        "label": "Audio non enregistre",
        "description": "L'enregistrement audio n'apparait pas apres l'appel.",
    },
    {
        "value": "statut_non_synchronise",
        "label": "Statut non synchronise",
        "description": "Le statut affiche ne correspond pas a l'action realisee.",
    },
    {
        "value": "compteur_non_mis_a_jour",
        "label": "Compteur non mis a jour",
        "description": "Les totaux ou progressions ne changent pas apres l'appel.",
    },
    {
        "value": "option_non_enregistree",
        "label": "Option cochee non enregistree",
        "description": "Une case comme deja forme, faux nom ou numero double ne reste pas cochee.",
    },
    {
        "value": "numero_manquant",
        "label": "Numero manquant ou incorrect",
        "description": "La ligne ne contient pas de numero exploitable.",
    },
    {
        "value": "hors_ligne_en_attente",
        "label": "Action hors ligne en attente",
        "description": "Une action reste dans le cache local et ne se synchronise pas.",
    },
    {
        "value": "erreur_serveur",
        "label": "Erreur serveur",
        "description": "Une action renvoie une erreur ou une reponse invalide.",
    },
]

ALERT_TYPE_LABELS = {item["value"]: item["label"] for item in ALERT_TYPE_OPTIONS}
ONLINE_WINDOW_SECONDS = 300


def _is_admin(user) -> bool:
    return bool(getattr(user, "is_authenticated", False) and getattr(user, "is_superuser", False))


def _json_body(request) -> dict:
    try:
        return json.loads((request.body or b"{}").decode("utf-8") or "{}")
    except (TypeError, ValueError, UnicodeDecodeError):
        return {}


def _clean_text(value, max_len: int | None = None) -> str:
    text = str(value or "").replace("\x00", "").strip()
    if max_len is not None:
        return text[:max_len]
    return text


def _clean_alert_types(value) -> list[str]:
    if not isinstance(value, list):
        return []
    seen = set()
    cleaned = []
    for item in value:
        key = _clean_text(item, 80)
        if key in ALERT_TYPE_LABELS and key not in seen:
            seen.add(key)
            cleaned.append(key)
    return cleaned


def _format_duration(seconds: int | None) -> str:
    if seconds is None:
        return ""
    seconds = max(0, int(seconds))
    minutes, sec = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    days, hour = divmod(hours, 24)
    if days:
        return f"{days}j {hour}h"
    if hours:
        return f"{hours}h {minute}min"
    if minutes:
        return f"{minutes}min {sec}s"
    return f"{sec}s"


def _activity_map(user_ids) -> dict[int, UserActivity]:
    ids = {uid for uid in user_ids if uid}
    if not ids:
        return {}
    try:
        return {row.user_id: row for row in UserActivity.objects.filter(user_id__in=ids)}
    except (ProgrammingError, OperationalError, AttributeError, NameError):
        return {}


def _recent_activity_events(user_id: int, limit: int = 8) -> list[dict]:
    if not user_id:
        return []
    try:
        events = UserActivityEvent.objects.filter(user_id=user_id).order_by("-occurred_at")[:limit]
    except (ProgrammingError, OperationalError, AttributeError, NameError):
        return []
    return [
        {
            "type": event.event_type,
            "page": event.page_title or event.page_path,
            "target": event.target_label or event.target_path,
            "path": event.page_path,
            "at": event.occurred_at.isoformat() if event.occurred_at else "",
        }
        for event in events
    ]


def _is_online(activity: UserActivity | None) -> bool:
    if not activity or not activity.last_seen:
        return False
    return activity.last_seen >= timezone.now() - timezone.timedelta(seconds=ONLINE_WINDOW_SECONDS)


def _activity_payload(activity: UserActivity | None) -> dict:
    if not activity:
        return {
            "is_online": False,
            "last_seen": "",
            "current_page": "",
            "last_action_label": "",
            "last_action_type": "",
            "last_action_at": "",
        }
    return {
        "is_online": _is_online(activity),
        "last_seen": activity.last_seen.isoformat() if activity.last_seen else "",
        "current_page": activity.current_page_title or activity.current_page,
        "last_action_label": activity.last_action_label,
        "last_action_type": activity.last_action_type,
        "last_action_at": activity.last_action_at.isoformat() if activity.last_action_at else "",
    }


def _serialize_alert(alert: CallAlert, *, activity: UserActivity | None = None, detail=False) -> dict:
    first_response_seconds = None
    if alert.first_response_at:
        first_response_seconds = int((alert.first_response_at - alert.created_at).total_seconds())
    resolution_seconds = None
    if alert.resolved_at:
        resolution_seconds = int((alert.resolved_at - alert.created_at).total_seconds())

    payload = {
        "id": alert.pk,
        "source": alert.source,
        "source_label": alert.get_source_display(),
        "status": alert.status,
        "status_label": alert.get_status_display(),
        "alert_types": alert.alert_types or [],
        "alert_type_labels": [
            ALERT_TYPE_LABELS.get(value, value) for value in (alert.alert_types or [])
        ],
        "details": alert.details,
        "reporter": alert.reporter.get_username(),
        "reporter_name": alert.reporter.get_full_name() or alert.reporter.get_username(),
        "call_id": alert.call_id,
        "call_label": alert.call_label,
        "call_status": alert.call_status,
        "page_path": alert.page_path,
        "page_title": alert.page_title,
        "created_at": alert.created_at.isoformat() if alert.created_at else "",
        "updated_at": alert.updated_at.isoformat() if alert.updated_at else "",
        "admin_message": alert.admin_message,
        "resolution_comment": alert.resolution_comment,
        "assigned_to": alert.assigned_to.get_username() if alert.assigned_to else "",
        "first_response_at": alert.first_response_at.isoformat() if alert.first_response_at else "",
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else "",
        "reaction_seconds": first_response_seconds,
        "reaction_label": _format_duration(first_response_seconds),
        "resolution_seconds": resolution_seconds,
        "resolution_label": _format_duration(resolution_seconds),
        "reporter_activity": _activity_payload(activity),
    }
    if detail:
        payload["last_actions"] = alert.last_actions or []
        payload["user_agent"] = alert.user_agent
        payload["recent_activity"] = _recent_activity_events(alert.reporter_id)
    return payload


@login_required
@require_GET
def call_alert_options(request):
    return JsonResponse(
        {
            "ok": True,
            "is_admin": _is_admin(request.user),
            "options": ALERT_TYPE_OPTIONS,
            "statuses": [
                {"value": value, "label": label} for value, label in CallAlert.STATUS_CHOICES
            ],
        }
    )


@login_required
@require_POST
def call_alert_create(request):
    data = _json_body(request)
    source = _clean_text(data.get("source"), 20)
    if source not in {CallAlert.SOURCE_PADESCE, CallAlert.SOURCE_CGA}:
        return JsonResponse({"ok": False, "error": "source_invalide"}, status=400)

    alert_types = _clean_alert_types(data.get("alert_types"))
    details = _clean_text(data.get("details"), 2000)
    if not alert_types and not details:
        return JsonResponse({"ok": False, "error": "alerte_vide"}, status=400)

    last_actions = data.get("last_actions")
    if not isinstance(last_actions, list):
        last_actions = []

    alert = CallAlert.objects.create(
        reporter=request.user,
        source=source,
        alert_types=alert_types,
        details=details,
        page_path=_clean_text(data.get("page_path"), 255),
        page_title=_clean_text(data.get("page_title"), 255),
        call_id=_clean_text(data.get("call_id"), 64),
        call_label=_clean_text(data.get("call_label"), 255),
        call_status=_clean_text(data.get("call_status"), 40),
        last_actions=last_actions[:10],
        user_agent=_clean_text(request.META.get("HTTP_USER_AGENT"), 1000),
        reporter_seen_at=timezone.now(),
    )
    activity = _activity_map([request.user.pk]).get(request.user.pk)
    return JsonResponse({"ok": True, "alert": _serialize_alert(alert, activity=activity)})


@login_required
@require_GET
def call_alert_list(request):
    scope = _clean_text(request.GET.get("scope"), 20)
    include_done = request.GET.get("include_done") == "1"
    is_admin = _is_admin(request.user)

    if scope == "received" and is_admin:
        qs = CallAlert.objects.select_related("reporter", "assigned_to").all()
        if not include_done:
            qs = qs.exclude(status=CallAlert.STATUS_DONE)
    else:
        qs = CallAlert.objects.select_related("reporter", "assigned_to").filter(
            reporter=request.user
        )

    alerts = list(qs.order_by("-updated_at")[:80])
    activities = _activity_map([alert.reporter_id for alert in alerts])
    if scope == "received" and is_admin:
        unread_count = CallAlert.objects.filter(admin_seen_at__isnull=True).exclude(
            status=CallAlert.STATUS_DONE
        ).count()
    else:
        unread_count = (
            CallAlert.objects.filter(reporter=request.user)
            .exclude(status=CallAlert.STATUS_TODO)
            .filter(
                models.Q(reporter_seen_at__isnull=True)
                | models.Q(reporter_seen_at__lt=models.F("updated_at"))
            )
            .count()
        )
    return JsonResponse(
        {
            "ok": True,
            "is_admin": is_admin,
            "scope": "received" if scope == "received" and is_admin else "mine",
            "unread_count": unread_count,
            "alerts": [
                _serialize_alert(alert, activity=activities.get(alert.reporter_id))
                for alert in alerts
            ],
        }
    )


@login_required
@require_GET
def call_alert_detail(request, pk: int):
    alert = (
        CallAlert.objects.select_related("reporter", "assigned_to", "admin_seen_by")
        .filter(pk=pk)
        .first()
    )
    if not alert:
        return JsonResponse({"ok": False, "error": "introuvable"}, status=404)
    is_admin = _is_admin(request.user)
    if not is_admin and alert.reporter_id != request.user.pk:
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    update_fields = []
    now = timezone.now()
    if is_admin and not alert.admin_seen_at:
        alert.admin_seen_at = now
        alert.admin_seen_by = request.user
        update_fields.extend(["admin_seen_at", "admin_seen_by"])
    elif alert.reporter_id == request.user.pk:
        alert.reporter_seen_at = now
        update_fields.append("reporter_seen_at")
    if update_fields:
        alert.save(update_fields=update_fields)

    activity = _activity_map([alert.reporter_id]).get(alert.reporter_id)
    return JsonResponse(
        {
            "ok": True,
            "is_admin": is_admin,
            "alert": _serialize_alert(alert, activity=activity, detail=True),
        }
    )


@login_required
@require_POST
def call_alert_update(request, pk: int):
    if not _is_admin(request.user):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    alert = CallAlert.objects.select_related("reporter", "assigned_to").filter(pk=pk).first()
    if not alert:
        return JsonResponse({"ok": False, "error": "introuvable"}, status=404)

    data = _json_body(request)
    next_status = _clean_text(data.get("status"), 20)
    valid_statuses = {value for value, _label in CallAlert.STATUS_CHOICES}
    if next_status not in valid_statuses:
        return JsonResponse({"ok": False, "error": "statut_invalide"}, status=400)

    admin_message = _clean_text(data.get("admin_message"), 2000)
    resolution_comment = _clean_text(data.get("resolution_comment"), 2000)
    if next_status == CallAlert.STATUS_DONE and not resolution_comment:
        return JsonResponse({"ok": False, "error": "commentaire_resolution_requis"}, status=400)

    now = timezone.now()
    update_fields = ["status", "assigned_to", "admin_message", "admin_seen_at", "admin_seen_by"]
    alert.status = next_status
    alert.assigned_to = request.user
    alert.admin_seen_at = now
    alert.admin_seen_by = request.user
    alert.admin_message = admin_message

    if next_status in {CallAlert.STATUS_DOING, CallAlert.STATUS_DONE} and not alert.first_response_at:
        alert.first_response_at = now
        update_fields.append("first_response_at")
    if next_status == CallAlert.STATUS_DOING and not alert.admin_message:
        alert.admin_message = "Le support est en train de traiter votre alerte."
    if next_status == CallAlert.STATUS_DONE:
        alert.resolution_comment = resolution_comment
        alert.resolved_at = now
        update_fields.extend(["resolution_comment", "resolved_at"])
    elif alert.resolved_at:
        alert.resolved_at = None
        update_fields.append("resolved_at")

    update_fields.append("updated_at")
    alert.save(update_fields=list(dict.fromkeys(update_fields)))

    activity = _activity_map([alert.reporter_id]).get(alert.reporter_id)
    return JsonResponse({"ok": True, "alert": _serialize_alert(alert, activity=activity)})

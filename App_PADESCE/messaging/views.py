import csv

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from App_PADESCE.messaging.forms import CampagneMessageForm, ContactForm, SupportAlarmForm, SupportMessageForm
from App_PADESCE.messaging.models import CampagneMessage, Contact, SupportAlarm, SupportMessage
from App_PADESCE.formations.models import Prestataire


def contacts_view(request):
    filters = {
        "prestataire_id": request.GET.get("prestataire") or None,
        "ville_residence": request.GET.get("ville") or None,
        "fenetre": request.GET.get("fenetre") or None,
    }
    qs = Contact.objects.select_related("prestataire", "formation").all()
    if filters["prestataire_id"]:
        qs = qs.filter(prestataire_id=filters["prestataire_id"])
    if filters["ville_residence"]:
        qs = qs.filter(ville_residence__icontains=filters["ville_residence"])
    if filters["fenetre"]:
        qs = qs.filter(fenetre__icontains=filters["fenetre"])

    contact_form = ContactForm(request.POST or None, prefix="contact")
    if request.method == "POST" and "contact_submit" in request.POST:
        if contact_form.is_valid():
            contact_form.save()
            messages.success(request, "Contact cree.")
            return redirect(request.path_info)
        else:
            messages.error(request, "Erreur lors de la creation du contact.")

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "contacts": page_obj,
        "page_obj": page_obj,
        "prestataires": Prestataire.objects.all().order_by("raison_sociale"),
        "filters": filters,
        "contact_form": contact_form,
    }
    return render(request, "messaging/contacts.html", context)


def contacts_export_csv(request):
    qs = Contact.objects.select_related("prestataire", "formation").all()
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=contacts.csv"
    writer = csv.writer(response)
    writer.writerow(
        [
            "nom_complet",
            "telephone",
            "prestataire",
            "formation",
            "fenetre",
            "ville_residence",
            "fonction",
        ]
    )
    for c in qs:
        writer.writerow(
            [
                c.nom_complet,
                c.telephone,
                c.prestataire,
                c.formation,
                c.fenetre,
                c.ville_residence,
                c.fonction,
            ]
        )
    return response


def campagnes_view(request):
    campagne_form = CampagneMessageForm(request.POST or None, prefix="campagne")
    if request.method == "POST" and "campagne_submit" in request.POST:
        if campagne_form.is_valid():
            obj = campagne_form.save(commit=False)
            if not obj.date_heure:
                obj.date_heure = timezone.now()
            if hasattr(request, "user") and request.user.is_authenticated:
                obj.enqueteur = request.user
            obj.save()
            messages.success(request, "Campagne enregistree.")
            return redirect(request.path_info)
        else:
            messages.error(request, "Erreur lors de l'enregistrement de la campagne.")

    campagnes = CampagneMessage.objects.select_related("enqueteur").order_by("-date_heure")[:100]

    context = {
        "campagne_form": campagne_form,
        "campagnes": campagnes,
    }
    return render(request, "messaging/campagnes.html", context)


def _is_manager(user) -> bool:
    if not user.is_authenticated:
        return False
    return user.groups.filter(name__in=["manager_cga", "manager_padesce"]).exists()


def _support_agents_queryset():
    User = get_user_model()
    return User.objects.filter(
        Q(is_superuser=True) | Q(groups__name__in=["manager_cga", "manager_padesce"])
    ).distinct()


@login_required
def support_center(request):
    user = request.user
    is_agent = bool(user.is_superuser or _is_manager(user))

    if is_agent:
        recipient_qs = get_user_model().objects.exclude(pk=user.pk).order_by("username")
    else:
        recipient_qs = _support_agents_queryset().exclude(pk=user.pk).order_by("username")

    recipient_ids = set(recipient_qs.values_list("id", flat=True))
    selected_id = request.GET.get("with")
    selected_user = None
    if selected_id and selected_id.isdigit():
        sid = int(selected_id)
        if sid in recipient_ids:
            selected_user = recipient_qs.filter(pk=sid).first()
    if not selected_user:
        selected_user = recipient_qs.first()

    message_form = SupportMessageForm(request.POST or None, prefix="msg")
    message_form.fields["recipient"].queryset = recipient_qs
    if selected_user and request.method != "POST":
        message_form.fields["recipient"].initial = selected_user.pk
    alarm_form = SupportAlarmForm(request.POST or None, prefix="alarm")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "send_message":
            if message_form.is_valid():
                msg = message_form.save(commit=False)
                if msg.recipient_id not in recipient_ids:
                    messages.error(request, "Destinataire non autorise.")
                else:
                    msg.sender = user
                    msg.kind = SupportMessage.KIND_CHAT
                    msg.save()
                    messages.success(request, "Message envoye.")
                    return redirect(f"{request.path}?with={msg.recipient_id}")
            else:
                messages.error(request, "Impossible d'envoyer le message.")
        elif action == "raise_alarm":
            if alarm_form.is_valid():
                alarm = alarm_form.save(commit=False)
                alarm.reporter = user
                alarm.save()
                # Mirror alarm to all superusers as unread support messages.
                for admin_user in get_user_model().objects.filter(is_superuser=True):
                    if admin_user.pk == user.pk:
                        continue
                    SupportMessage.objects.create(
                        sender=user,
                        recipient=admin_user,
                        body=f"[ALARM] {alarm.title}\nModule: {alarm.module or '-'}\n{alarm.details}",
                        kind=SupportMessage.KIND_ALARM,
                        is_read=False,
                    )
                messages.success(request, "Alerte envoyee au superadmin.")
                return redirect(request.path)
            messages.error(request, "Impossible d'envoyer l'alerte.")

    thread_messages = SupportMessage.objects.none()
    if selected_user:
        thread_messages = (
            SupportMessage.objects.filter(
                (Q(sender=user, recipient=selected_user) | Q(sender=selected_user, recipient=user))
            )
            .select_related("sender", "recipient")
            .order_by("created_at")
        )
        SupportMessage.objects.filter(
            sender=selected_user, recipient=user, is_read=False
        ).update(is_read=True)

    unread_inbox_count = SupportMessage.objects.filter(recipient=user, is_read=False).count()
    if user.is_superuser:
        alarms_qs = SupportAlarm.objects.all().select_related("reporter", "seen_by", "resolved_by")
    elif is_agent:
        alarms_qs = SupportAlarm.objects.filter(
            Q(reporter=user) | Q(is_seen=False)
        ).select_related("reporter", "seen_by", "resolved_by")
    else:
        alarms_qs = SupportAlarm.objects.filter(reporter=user).select_related("reporter", "seen_by", "resolved_by")

    context = {
        "message_form": message_form,
        "alarm_form": alarm_form,
        "recipient_users": recipient_qs[:200],
        "selected_user": selected_user,
        "thread_messages": thread_messages,
        "support_alarms": alarms_qs[:150],
        "is_support_agent": is_agent,
        "unread_inbox_count": unread_inbox_count,
    }
    return render(request, "messaging/support.html", context)


@login_required
def support_alarm_poll(request):
    if not request.user.is_superuser:
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
    unseen_qs = SupportAlarm.objects.filter(is_seen=False).select_related("reporter").order_by("-created_at")
    latest = unseen_qs.first()
    return JsonResponse(
        {
            "ok": True,
            "unseen_count": unseen_qs.count(),
            "latest": {
                "id": latest.id,
                "title": latest.title,
                "module": latest.module,
                "reporter": latest.reporter.get_username() if latest else "",
                "created_at": latest.created_at.isoformat() if latest else "",
                "details": latest.details if latest else "",
            }
            if latest
            else None,
        }
    )


@login_required
@require_POST
def support_alarm_mark_seen(request, pk: int):
    if not request.user.is_superuser:
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
    alarm = SupportAlarm.objects.filter(pk=pk).first()
    if not alarm:
        return JsonResponse({"ok": False, "error": "not_found"}, status=404)
    alarm.is_seen = True
    alarm.seen_by = request.user
    alarm.seen_at = timezone.now()
    alarm.save(update_fields=["is_seen", "seen_by", "seen_at", "updated_at"])
    return JsonResponse({"ok": True})

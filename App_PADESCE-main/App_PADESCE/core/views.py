from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.utils import timezone

from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.core.models import UserActivity
from App_PADESCE.formations.models import Classe
from App_PADESCE.presences.models import Presence
from App_PADESCE.satisfaction_apprenants.models import SatisfactionApprenant
from App_PADESCE.satisfaction_formateurs.models import SatisfactionFormateur
from App_PADESCE.environnement.models import EnqueteEnvironnement


def home(request):
    today = date.today()
    start_date = date(2025, 9, 26)
    end_date = date(2026, 8, 26)
    total_days = (end_date - start_date).days or 1
    elapsed_days = max(0, min((today - start_date).days, total_days))
    progress_pct = round((elapsed_days / total_days) * 100, 1)
    countdown_days = max(0, (end_date - today).days)

    context = {
        "nb_classes": Classe.objects.count(),
        "nb_apprenants": Apprenant.objects.count(),
        "nb_presence": Presence.objects.count(),
        "nb_sat_apprenants": SatisfactionApprenant.objects.count(),
        "nb_sat_formateurs": SatisfactionFormateur.objects.count(),
        "nb_env": EnqueteEnvironnement.objects.count(),
        "progress_pct": progress_pct,
        "countdown_days": countdown_days,
        "deadline_iso": end_date.isoformat(),
        "stat_cards": [
            {"label": "Classes", "value": Classe.objects.count(), "color": "primary"},
            {"label": "Apprenants", "value": Apprenant.objects.count(), "color": "success"},
            {"label": "Enquêtes présence", "value": Presence.objects.count(), "color": "info"},
            {"label": "Sat. apprenants", "value": SatisfactionApprenant.objects.count(), "color": "warning"},
            {"label": "Sat. formateurs", "value": SatisfactionFormateur.objects.count(), "color": "danger"},
            {"label": "Environnement", "value": EnqueteEnvironnement.objects.count(), "color": "secondary"},
        ],
    }
    if request.user.is_superuser:
        User = get_user_model()
        cutoff = timezone.now() - timedelta(minutes=10)
        activities = {a.user_id: a for a in UserActivity.objects.select_related("user")}
        rows = []
        for user in User.objects.all().order_by("username"):
            activity = activities.get(user.id)
            last_seen = activity.last_seen if activity else user.last_login
            is_online = bool(last_seen and last_seen >= cutoff)
            rows.append(
                {
                    "username": user.get_username(),
                    "is_online": is_online,
                    "last_seen": last_seen,
                }
            )
        context["user_activity_rows"] = rows
    return render(request, "home.html", context)

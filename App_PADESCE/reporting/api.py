from typing import Any, Dict, List

from django.db.models import Avg, Count, Q, Sum
from django.http import JsonResponse, Http404

from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.environnement.models import EnqueteEnvironnement
from App_PADESCE.formations.models import Formation, Prestation
from App_PADESCE.presences.models import Presence
from App_PADESCE.satisfaction_apprenants.models import SatisfactionApprenant
from App_PADESCE.satisfaction_formateurs.models import SatisfactionFormateur


def safe_rate(num: float, den: float) -> float:
    return round((num / den) * 100, 2) if den else 0.0


def _presence_rates(field: str) -> List[Dict[str, Any]]:
    qs = (
        Presence.objects.values(field)
        .annotate(total=Count("id"), pr=Count("id", filter=Q(presence="PR")))
        .order_by("-total")
    )
    return [
        {"label": r[field], "pr": r["pr"], "total": r["total"], "taux": safe_rate(r["pr"], r["total"])}
        for r in qs
    ]


def _sat_avg(model, field: str, display: str) -> List[Dict[str, Any]]:
    qs = model.objects.values(display).annotate(moy=Avg(field)).order_by("-moy")
    return [{"label": r[display], "moy": r["moy"]} for r in qs]


def get_chart_data(code: str) -> Dict[str, Any]:
    code = code.upper()
    # Gauges RES00-01..05
    total_pres = Presence.objects.count()
    total_pr = Presence.objects.filter(presence="PR").count()
    taux_presence_global = safe_rate(total_pr, total_pres)
    sat_appr_moy = SatisfactionApprenant.objects.aggregate(m=Avg("q9_satisfaction_globale")).get("m") or 0
    sat_form_moy = SatisfactionFormateur.objects.aggregate(m=Avg("q9_satisfaction_globale_prestataire")).get("m") or 0
    env_fields = [
        "tables",
        "chaises",
        "ecran",
        "videoprojecteur",
        "ventilation",
        "eclairage",
        "salle_propre",
        "salle_securisee",
    ]
    env_counts = EnqueteEnvironnement.objects.aggregate(
        total=Count("id"), **{f: Sum(f) for f in env_fields}
    )
    env_score = safe_rate(
        sum((env_counts.get(f) or 0) for f in env_fields),
        (env_counts.get("total") or 0) * len(env_fields),
    )

    gauges = {
        "RES00-01": {"value": taux_presence_global, "max": 100},
        "RES00-02": {"value": 0, "max": 100, "note": "Synthèse contractuelle à renseigner"},
        "RES00-03": {"value": env_score, "max": 100},
        "RES00-04": {"value": sat_appr_moy, "max": 5},
        "RES00-05": {"value": sat_form_moy, "max": 5},
    }
    if code in gauges:
        return {"type": "gauge", **gauges[code]}

    # Présence par axes
    presence_map = {
        "RES01-01": _presence_rates("classe__prestation__prestataire__raison_sociale"),
        "RES01-02": _presence_rates("classe__prestation__code"),
        "RES01-03": _presence_rates("classe__prestation__beneficiaire__nom_structure"),
        "RES01-04": _presence_rates("classe__formation__nom"),
        "RES01-05": _presence_rates("classe__formation__nom_harmonise"),
    }
    if code in presence_map:
        return {"type": "bar", "series": presence_map[code]}

    # Satisfaction apprenants
    sat_appr_map = {
        "RES04-02": _sat_avg(SatisfactionApprenant, "q9_satisfaction_globale", "classe__prestation__prestataire__raison_sociale"),
        "RES04-03": _sat_avg(SatisfactionApprenant, "q9_satisfaction_globale", "classe__prestation__code"),
        "RES04-04": _sat_avg(SatisfactionApprenant, "q9_satisfaction_globale", "classe__prestation__beneficiaire__nom_structure"),
        "RES04-05": _sat_avg(SatisfactionApprenant, "q9_satisfaction_globale", "classe__formation__nom"),
        "RES04-06": _sat_avg(SatisfactionApprenant, "q9_satisfaction_globale", "classe__formation__nom_harmonise"),
    }
    if code in sat_appr_map:
        return {"type": "bar", "series": sat_appr_map[code]}

    # Satisfaction formateurs
    sat_form_map = {
        "RES05-01": _sat_avg(SatisfactionFormateur, "q9_satisfaction_globale_prestataire", "classe__code"),
    }
    if code in sat_form_map:
        return {"type": "bar", "series": sat_form_map[code]}

    # Répartition apprenants
    repart_map = {
        "PER01-01": Apprenant.objects.values("region").annotate(total=Count("id")).order_by("-total"),
        "PER01-02": Apprenant.objects.values("formation__nom").annotate(total=Count("id")).order_by("-total"),
        "PER01-03": Apprenant.objects.values("classe__prestation__beneficiaire__nom_structure").annotate(total=Count("id")).order_by("-total"),
        "PER01-04": Apprenant.objects.values("classe__prestation__prestataire__raison_sociale").annotate(total=Count("id")).order_by("-total"),
    }
    if code in repart_map:
        return {
            "type": "bar",
            "series": [{"label": r[next(iter(r.keys()))], "total": r["total"]} for r in repart_map[code]],
        }

    # Carte des lieux
    if code == "RES03-01":
        data = []
        for lieu in Formation._meta.apps.get_model("formations", "Lieu").objects.all():
            try:
                lat = float(lieu.latitude)
                lon = float(lieu.longitude)
            except (TypeError, ValueError):
                continue
            data.append({"label": lieu.nom_lieu, "lat": lat, "lon": lon})
        return {"type": "map", "points": data}

    # Env table
    if code == "RES03-02":
        qs = (
            EnqueteEnvironnement.objects.values("classe__lieu__nom_lieu", "classe__lieu__region")
            .annotate(total=Count("id"), tables=Sum("tables"), chaises=Sum("chaises"), ecran=Sum("ecran"))
            .order_by("-total")
        )
        return {"type": "table", "rows": list(qs)}

    raise Http404(f"Code {code} non pris en charge")


def api_chart(request, code: str):
    data = get_chart_data(code)
    return JsonResponse(data, safe=False)

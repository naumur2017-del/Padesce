import csv
from datetime import date as date_cls

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Case, Count, ExpressionWrapper, F, FloatField, Q, Value, When
from django.http import HttpResponse
from django.shortcuts import redirect, render

from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.presences.forms import PresenceForm
from App_PADESCE.presences.models import Presence
from App_PADESCE.formations.models import Classe


def presence_list(request):
    """
    Saisie et listing des presences avec filtre par classe et export.
    """
    filter_classe = request.GET.get("classe")
    presences_qs = Presence.objects.select_related(
        "classe", "apprenant", "inspecteur", "enqueteur"
    ).order_by("-date", "-heure_enregistrement")
    if filter_classe:
        presences_qs = presences_qs.filter(classe_id=filter_classe)

    if request.method == "POST":
        form = PresenceForm(request.POST)
        if form.is_valid():
            presence = form.save(commit=False)
            if hasattr(request, "user") and request.user.is_authenticated:
                presence.enqueteur = request.user
            presence.save()
            messages.success(request, "Presence enregistree.")
            return redirect(request.path_info + f"?classe={filter_classe}" if filter_classe else request.path_info)
    else:
        form = PresenceForm(initial={"date": date_cls.today()})

    stats = presences_qs.values("classe__code").annotate(
        total=Count("id"),
        presents=Count("id", filter=Q(presence="PR")),
        absents=Count("id", filter=Q(presence="AB")),
    )

    paginator = Paginator(presences_qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "form": form,
        "presences": page_obj,
        "page_obj": page_obj,
        "classes": Classe.objects.all().order_by("code"),
        "filter_classe": filter_classe,
        "stats": stats,
    }
    return render(request, "presences/index.html", context)


def appels(request):
    """
    Tableau des apprenants dont la classe est terminee, filtre par seuil de taux de presence,
    avec controles d'enregistrement/lecture audio (cote navigateur).
    """
    try:
        seuil = int(request.GET.get("seuil", 50))
    except (TypeError, ValueError):
        seuil = 50
    seuil = max(0, min(seuil, 100))

    apprenants_qs = (
        Apprenant.objects.select_related("classe", "classe__prestation", "classe__formation")
        .filter(classe__statut="termine")
        .annotate(
            total=Count("presences", distinct=True),
            pr=Count("presences", filter=Q(presences__presence="PR"), distinct=True),
        )
    )
    apprenants_qs = apprenants_qs.annotate(
        taux_presence=Case(
            When(total__gt=0, then=ExpressionWrapper(100.0 * F("pr") / F("total"), output_field=FloatField())),
            default=Value(0.0),
            output_field=FloatField(),
        )
    ).filter(taux_presence__lte=seuil).order_by("classe__prestation__code", "classe__code", "nom_complet")

    context = {
        "apprenants": apprenants_qs,
        "seuil": seuil,
    }
    return render(request, "presences/appels.html", context)


def presence_export_csv(request):
    filter_classe = request.GET.get("classe")
    presences_qs = Presence.objects.select_related("classe", "apprenant", "inspecteur", "enqueteur").order_by("-date")
    if filter_classe:
        presences_qs = presences_qs.filter(classe_id=filter_classe)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=presences.csv"
    writer = csv.writer(response)
    writer.writerow(
        [
            "classe",
            "apprenant",
            "inspecteur",
            "enqueteur",
            "date",
            "heure_debut",
            "heure_fin",
            "presence",
            "statut",
            "moyen_enregistrement",
            "remarques",
            "heure_enregistrement",
        ]
    )
    for p in presences_qs:
        writer.writerow(
            [
                p.classe,
                p.apprenant,
                p.inspecteur,
                p.enqueteur,
                p.date,
                p.heure_debut,
                p.heure_fin,
                p.presence,
                p.statut,
                p.moyen_enregistrement,
                p.remarques,
                p.heure_enregistrement,
            ]
        )
    return response

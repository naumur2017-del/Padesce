from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.formations.forms import ClasseCreateForm
from App_PADESCE.formations.models import Classe, Formation, Lieu, Prestation
from App_PADESCE.presences.models import Presence
from App_PADESCE.satisfaction_apprenants.models import SatisfactionApprenant
from App_PADESCE.satisfaction_formateurs.models import SatisfactionFormateur
from App_PADESCE.environnement.models import EnqueteEnvironnement


def generate_code(model_cls, prefix: str, padding: int = 3) -> str:
    total = model_cls.objects.count()
    return f"{prefix}{total + 1:0{padding}d}"


def class_list(request):
    classes = (
        Classe.objects.select_related("prestation", "formation", "lieu", "formateur")
        .all()
        .order_by("code")
    )
    return render(request, "formations/class_list.html", {"classes": classes})


def class_detail(request, pk: int):
    classe = get_object_or_404(
        Classe.objects.select_related("prestation", "formation", "lieu", "formateur"),
        pk=pk,
    )
    enquete_list = (
        Presence.objects.filter(classe=classe)
        .select_related("inspecteur", "enqueteur")
        .order_by("-date")[:20]
    )
    apprenants = getattr(classe, "apprenants", None) or []
    return render(
        request,
        "formations/class_detail.html",
        {"classe": classe, "enquetes": enquete_list, "apprenants": apprenants},
    )


@transaction.atomic
def class_create(request):
    initial_code = generate_code(Classe, "CLA")
    prestation_id = request.GET.get("prestation")
    initial_data = {"code": initial_code, "cohorte": 1}

    if prestation_id:
        prestation = get_object_or_404(Prestation.objects.select_related("formation"), pk=prestation_id)
        initial_data["prestation"] = prestation

    form = ClasseCreateForm(request.POST or None, initial=initial_data)

    if request.method == "POST" and form.is_valid():
        classe: Classe = form.save(commit=False)
        if classe.prestation_id:
            existing_max = (
                Classe.objects.filter(prestation=classe.prestation)
                .order_by("-cohorte")
                .values_list("cohorte", flat=True)
                .first()
            )
            classe.cohorte = (existing_max or 0) + 1
            classe.formation = classe.prestation.formation

        lieu_payload = {
            "nom_lieu": form.cleaned_data.get("lieu_nom", "").strip(),
            "precision": form.cleaned_data.get("lieu_precision", "").strip(),
            "arrondissement": form.cleaned_data.get("lieu_arrondissement", "").strip(),
            "departement": form.cleaned_data.get("lieu_departement", "").strip(),
            "ville": form.cleaned_data.get("lieu_ville", "").strip(),
            "region": form.cleaned_data.get("lieu_region", "").strip(),
            "longitude": form.cleaned_data.get("lieu_longitude", "").strip(),
            "latitude": form.cleaned_data.get("lieu_latitude", "").strip(),
        }
        if any(lieu_payload.values()):
            lieu_code = generate_code(Lieu, "LIE")
            if not lieu_payload["nom_lieu"]:
                lieu_payload["nom_lieu"] = f"Lieu {lieu_code}"
            classe.lieu = Lieu.objects.create(code=lieu_code, **lieu_payload)

        classe.code = initial_code
        classe.save()
        messages.success(request, f"Classe {classe.code} creee. Importez les apprenants CSV.")
        return redirect(reverse("apprenants_import", args=[classe.id]))

    prestation_map = {
        str(p.id): p.formation.nom if p.formation else ""
        for p in Prestation.objects.select_related("formation")
    }

    return render(
        request,
        "formations/class_form.html",
        {"form": form, "initial_code": initial_code, "prestation_map": prestation_map},
    )


@require_POST
def class_delete(request, pk: int):
    classe = get_object_or_404(Classe, pk=pk)
    code = classe.code
    try:
        classe.delete()
        messages.success(request, f"Classe {code} supprimee.")
    except Exception as exc:  # pragma: no cover - defensive guard
        messages.error(request, f"Impossible de supprimer {code}: {exc}")
    return redirect(reverse("class_list"))


@require_POST
def class_toggle_status(request, pk: int):
    classe = get_object_or_404(Classe.objects.select_related("prestation"), pk=pk)
    new_statut = "en_cours" if classe.statut == "termine" else "termine"
    classe.statut = new_statut
    classe.save(update_fields=["statut"])

    prestation = classe.prestation
    total_classes = prestation.classes.count()
    classes_terminees = prestation.classes.filter(statut="termine").count()
    total_apprenants = Apprenant.objects.filter(classe__prestation=prestation).count()
    prestation_terminee = (
        total_classes > 0
        and classes_terminees == total_classes
        and total_apprenants >= prestation.effectif_a_former
    )

    return JsonResponse(
        {
            "ok": True,
            "classe_id": classe.id,
            "statut": classe.statut,
            "statut_label": classe.get_statut_display(),
            "prestation_id": prestation.id,
            "prestation_terminee": prestation_terminee,
            "classes_terminees": classes_terminees,
            "total_classes": total_classes,
            "total_apprenants": total_apprenants,
            "objectif_effectif": prestation.effectif_a_former,
            "femmes_cible": prestation.femmes,
        }
    )


def formation_list(request):
    """
    Page End : liste des prestations avec leurs classes et cibles (effectif total / femmes),
    possibilite de basculer le statut des classes.
    """
    prestations = (
        Prestation.objects.select_related("prestataire", "formation", "beneficiaire")
        .annotate(
            total_apprenants=Count("classes__apprenants", distinct=True),
            total_classes=Count("classes", distinct=True),
            classes_terminees=Count("classes", filter=Q(classes__statut="termine"), distinct=True),
        )
        .prefetch_related(
            Prefetch(
                "classes",
                queryset=Classe.objects.select_related("lieu")
                .annotate(apprenants_count=Count("apprenants", distinct=True))
                .order_by("code"),
            )
        )
        .order_by("code")
    )
    return render(request, "formations/end.html", {"prestations": prestations})


def class_reports(request, pk: int):
    classe = get_object_or_404(
        Classe.objects.select_related("prestation", "formation", "lieu"),
        pk=pk,
    )
    presence_dates = (
        Presence.objects.filter(classe=classe)
        .values("date")
        .annotate(total=Count("id"), presents=Count("id", filter=Q(presence="PR")), absents=Count("id", filter=Q(presence="AB")))
        .order_by("-date")
    )
    sat_appr = SatisfactionApprenant.objects.filter(classe=classe).order_by("-date")
    sat_form = SatisfactionFormateur.objects.filter(classe=classe).order_by("-date")
    envs = EnqueteEnvironnement.objects.filter(classe=classe).order_by("-date")
    return render(
        request,
        "formations/reports.html",
        {
            "classe": classe,
            "presence_dates": presence_dates,
            "sat_appr": sat_appr,
            "sat_form": sat_form,
            "envs": envs,
        },
    )


def presence_report_detail(request, pk: int, date_str: str):
    classe = get_object_or_404(
        Classe.objects.select_related("prestation", "formation", "lieu"),
        pk=pk,
    )
    presences = Presence.objects.select_related("apprenant").filter(classe=classe, date=date_str).order_by("apprenant__nom_complet")
    total = presences.count()
    presents = presences.filter(presence="PR").count()
    absents = presences.filter(presence="AB").count()
    actifs = getattr(classe, "apprenants", Apprenant.objects.none()).count()
    return render(
        request,
        "formations/report_presence_detail.html",
        {
            "classe": classe,
            "date": date_str,
            "presences": presences,
            "total": total,
            "presents": presents,
            "absents": absents,
            "actifs": actifs,
        },
    )


def api_prestation_cohorte(request):
    prestation_id = request.GET.get("prestation_id")
    if not prestation_id:
        return JsonResponse({"cohorte": 1})
    try:
        existing_max = (
            Classe.objects.filter(prestation_id=prestation_id)
            .order_by("-cohorte")
            .values_list("cohorte", flat=True)
            .first()
        )
    except (ValueError, TypeError):
        return JsonResponse({"cohorte": 1})
    return JsonResponse({"cohorte": (existing_max or 0) + 1})

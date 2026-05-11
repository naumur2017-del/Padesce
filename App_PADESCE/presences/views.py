import csv
from datetime import date as date_cls

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case, Count, ExpressionWrapper, F, FloatField, Q, Value, When
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.formations.models import Classe
from App_PADESCE.presences.forms import PresenceControlForm, PresenceForm
from App_PADESCE.presences.models import Presence, PresenceControl
from App_PADESCE.presences.services import (
    TeamsSendError,
    build_presence_control_csv_bytes,
    build_presence_control_xlsx_bytes,
    presence_control_export_filename,
    send_presence_control_csv_to_teams,
)

CONTROL_TYPES = tuple(f"C{i}" for i in range(1, 7))
MANUAL_MOYENS = (("P", "Papier"), ("R", "Rien"))


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
            return redirect(
                request.path_info + f"?classe={filter_classe}"
                if filter_classe
                else request.path_info
            )
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


def _next_control_type(classe: Classe) -> str:
    used = set(
        PresenceControl.objects.filter(classe=classe).values_list("type_controle", flat=True)
    )
    for control_type in CONTROL_TYPES:
        if control_type not in used:
            return control_type
    return CONTROL_TYPES[-1]


def _presence_control_initial(classe: Classe) -> dict:
    formateur = getattr(classe, "formateur", None)
    prestation = getattr(classe, "prestation", None)
    return {
        "date": date_cls.today(),
        "type_controle": _next_control_type(classe),
        "duree_prevue_formation": getattr(prestation, "duree_prevue_heures", None),
        "formateur1_nom": getattr(formateur, "nom_complet", "") if formateur else "",
        "formateur1_telephone": getattr(formateur, "telephone", "") if formateur else "",
    }


def _control_marker_field(control: PresenceControl) -> str:
    return str(control.type_controle or "").lower()


def _set_apprenant_control_marker(
    apprenant: Apprenant, control: PresenceControl, marker: str
) -> None:
    field = _control_marker_field(control)
    if not field or not hasattr(apprenant, field):
        return
    if getattr(apprenant, field) == marker:
        return
    setattr(apprenant, field, marker)
    apprenant.save(update_fields=[field, "updated_at"])


def _seed_presence_rows(control: PresenceControl) -> int:
    apprenants = list(control.classe.apprenants.filter(actif=True).order_by("nom_complet", "code"))
    rows = [
        Presence(
            controle=control,
            classe=control.classe,
            apprenant=apprenant,
            inspecteur=control.inspecteur,
            enqueteur=control.enqueteur,
            date=control.date,
            heure_debut=control.heure_debut,
            heure_fin=control.heure_fin,
            presence="AB",
            statut="absent",
            moyen_enregistrement="",
        )
        for apprenant in apprenants
    ]
    Presence.objects.bulk_create(rows, batch_size=500, ignore_conflicts=True)

    field = _control_marker_field(control)
    if field:
        to_update = []
        now = timezone.now()
        for apprenant in apprenants:
            if hasattr(apprenant, field) and getattr(apprenant, field) != "AB":
                setattr(apprenant, field, "AB")
                apprenant.updated_at = now
                to_update.append(apprenant)
        if to_update:
            Apprenant.objects.bulk_update(to_update, [field, "updated_at"], batch_size=500)
    return len(apprenants)


def _mark_presence(control: PresenceControl, apprenant: Apprenant, moyen: str = "C") -> Presence:
    presence, _created = Presence.objects.get_or_create(
        controle=control,
        apprenant=apprenant,
        defaults={
            "classe": control.classe,
            "inspecteur": control.inspecteur,
            "enqueteur": control.enqueteur,
            "date": control.date,
            "heure_debut": control.heure_debut,
            "heure_fin": control.heure_fin,
        },
    )
    presence.classe = control.classe
    presence.inspecteur = control.inspecteur
    presence.enqueteur = control.enqueteur
    presence.date = control.date
    presence.heure_debut = control.heure_debut
    presence.heure_fin = control.heure_fin
    presence.presence = "PR"
    presence.statut = "present"
    presence.moyen_enregistrement = moyen
    presence.heure_presence = timezone.localtime().time().replace(microsecond=0)
    presence.save()
    _set_apprenant_control_marker(apprenant, control, "PR")
    return presence


def _mark_absent(control: PresenceControl, apprenant: Apprenant) -> Presence:
    presence, _created = Presence.objects.get_or_create(
        controle=control,
        apprenant=apprenant,
        defaults={
            "classe": control.classe,
            "inspecteur": control.inspecteur,
            "enqueteur": control.enqueteur,
            "date": control.date,
            "heure_debut": control.heure_debut,
            "heure_fin": control.heure_fin,
        },
    )
    presence.classe = control.classe
    presence.inspecteur = control.inspecteur
    presence.enqueteur = control.enqueteur
    presence.date = control.date
    presence.heure_debut = control.heure_debut
    presence.heure_fin = control.heure_fin
    presence.presence = "AB"
    presence.statut = "absent"
    presence.moyen_enregistrement = ""
    presence.heure_presence = None
    presence.save()
    _set_apprenant_control_marker(apprenant, control, "AB")
    return presence


def _search_control_apprenants(control: PresenceControl, query: str):
    clean_query = str(query or "").strip()
    if not clean_query:
        return Apprenant.objects.none()
    return (
        control.classe.apprenants.filter(actif=True)
        .filter(
            Q(code__icontains=clean_query)
            | Q(numero__icontains=clean_query)
            | Q(nom_complet__icontains=clean_query)
            | Q(telephone1__icontains=clean_query)
        )
        .order_by("nom_complet", "code")[:20]
    )


def _exact_code_match(control: PresenceControl, query: str):
    clean_query = str(query or "").strip()
    if not clean_query:
        return None
    matches = list(
        control.classe.apprenants.filter(actif=True)
        .filter(Q(code__iexact=clean_query) | Q(numero__iexact=clean_query))
        .order_by("nom_complet", "code")[:2]
    )
    return matches[0] if len(matches) == 1 else None


def presence_control_create(request, classe_id: int):
    classe = get_object_or_404(
        Classe.objects.select_related("prestation", "formation", "lieu", "formateur"),
        pk=classe_id,
    )
    if request.method == "POST":
        form = PresenceControlForm(request.POST, classe=classe)
        if form.is_valid():
            with transaction.atomic():
                control = form.save(commit=False)
                control.classe = classe
                if hasattr(request, "user") and request.user.is_authenticated:
                    control.enqueteur = request.user
                control.save()
                count = _seed_presence_rows(control)
            messages.success(
                request,
                f"Contrôle {control.type_controle} créé avec {count} apprenant(s) en AB par défaut.",
            )
            return redirect("presence_control_detail", pk=control.pk)
    else:
        form = PresenceControlForm(initial=_presence_control_initial(classe), classe=classe)

    return render(
        request,
        "presences/control_form.html",
        {"classe": classe, "form": form, "next_type": _next_control_type(classe)},
    )


def presence_control_detail(request, pk: int):
    control = get_object_or_404(
        PresenceControl.objects.select_related(
            "classe", "classe__prestation", "classe__formation", "inspecteur", "enqueteur"
        ),
        pk=pk,
    )
    search_results = []
    query = ""

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "search":
            query = request.POST.get("q", "").strip()
            exact = _exact_code_match(control, query)
            if exact is not None:
                _mark_presence(control, exact, "C")
                messages.success(request, f"{exact.nom_complet} marqué présent par code.")
                return redirect("presence_control_detail", pk=control.pk)
            search_results = list(_search_control_apprenants(control, query))
            if not search_results:
                messages.warning(request, "Aucun apprenant trouvé pour cette recherche.")
        elif action == "mark_present":
            apprenant = get_object_or_404(
                Apprenant, pk=request.POST.get("apprenant_id"), classe=control.classe, actif=True
            )
            moyen = request.POST.get("moyen", "")
            if moyen not in {"P", "R", "C"}:
                messages.error(request, "Précisez le moyen: Papier ou Rien.")
            else:
                _mark_presence(control, apprenant, moyen)
                messages.success(request, f"{apprenant.nom_complet} marqué présent.")
                return redirect("presence_control_detail", pk=control.pk)
        elif action == "mark_absent":
            apprenant = get_object_or_404(
                Apprenant, pk=request.POST.get("apprenant_id"), classe=control.classe, actif=True
            )
            _mark_absent(control, apprenant)
            messages.success(request, f"{apprenant.nom_complet} remis absent.")
            return redirect("presence_control_detail", pk=control.pk)

    presences = (
        control.presences.select_related("apprenant")
        .all()
        .order_by("apprenant__nom_complet", "apprenant__code")
    )
    stats = presences.aggregate(
        total=Count("id"),
        presents=Count("id", filter=Q(presence="PR")),
        absents=Count("id", filter=Q(presence="AB")),
    )
    return render(
        request,
        "presences/control_detail.html",
        {
            "control": control,
            "classe": control.classe,
            "presences": presences,
            "stats": stats,
            "search_results": search_results,
            "query": query,
            "manual_moyens": MANUAL_MOYENS,
            "csv_filename": presence_control_export_filename(control, "csv"),
            "xlsx_filename": presence_control_export_filename(control, "xlsx"),
        },
    )


def presence_control_export_csv(request, pk: int):
    control = get_object_or_404(PresenceControl.objects.select_related("classe"), pk=pk)
    response = HttpResponse(build_presence_control_csv_bytes(control), content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="{presence_control_export_filename(control, "csv")}"'
    )
    return response


def presence_control_export_xlsx(request, pk: int):
    control = get_object_or_404(PresenceControl.objects.select_related("classe"), pk=pk)
    response = HttpResponse(
        build_presence_control_xlsx_bytes(control),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{presence_control_export_filename(control, "xlsx")}"'
    )
    return response


def presence_control_send_teams(request, pk: int):
    if request.method != "POST":
        return redirect("presence_control_detail", pk=pk)
    control = get_object_or_404(PresenceControl.objects.select_related("classe"), pk=pk)
    try:
        result = send_presence_control_csv_to_teams(control)
    except TeamsSendError as exc:
        messages.error(request, f"Envoi Teams impossible: {exc}")
    else:
        messages.success(request, result["message"])
    return redirect(reverse("presence_control_detail", kwargs={"pk": control.pk}))


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
    apprenants_qs = (
        apprenants_qs.annotate(
            taux_presence=Case(
                When(
                    total__gt=0,
                    then=ExpressionWrapper(100.0 * F("pr") / F("total"), output_field=FloatField()),
                ),
                default=Value(0.0),
                output_field=FloatField(),
            )
        )
        .filter(taux_presence__lte=seuil)
        .order_by("classe__prestation__code", "classe__code", "nom_complet")
    )

    context = {
        "apprenants": apprenants_qs,
        "seuil": seuil,
    }
    return render(request, "presences/appels.html", context)


def presence_export_csv(request):
    filter_classe = request.GET.get("classe")
    presences_qs = Presence.objects.select_related(
        "classe", "apprenant", "inspecteur", "enqueteur"
    ).order_by("-date")
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

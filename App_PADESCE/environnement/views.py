import csv
from datetime import date as date_cls

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import redirect, render

from App_PADESCE.environnement.forms import EnqueteEnvironnementForm
from App_PADESCE.environnement.models import EnqueteEnvironnement
from App_PADESCE.formations.models import Classe


def environnement(request):
    filter_classe = request.GET.get("classe")
    classes = Classe.objects.select_related("prestation", "formation", "lieu").all().order_by("code")
    selected_classe = None
    if filter_classe:
        try:
            selected_classe = classes.get(pk=int(filter_classe))
        except (Classe.DoesNotExist, TypeError, ValueError):
            selected_classe = None

    qs = EnqueteEnvironnement.objects.select_related("classe", "inspecteur", "enqueteur").order_by("-date", "-created_at")
    if selected_classe:
        qs = qs.filter(classe=selected_classe)
    elif filter_classe:
        qs = qs.filter(classe_id=filter_classe)

    if request.method == "POST":
        form = EnqueteEnvironnementForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            if hasattr(request, "user") and request.user.is_authenticated:
                obj.enqueteur = request.user
            obj.save()
            target_classe = obj.classe_id or filter_classe
            messages.success(request, "Enquete environnement enregistree.")
            if target_classe:
                return redirect(f"{request.path_info}?classe={target_classe}")
            return redirect(request.path_info)
    else:
        initial = {"date": date_cls.today()}
        if selected_classe:
            initial["classe"] = selected_classe
        form = EnqueteEnvironnementForm(initial=initial)

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "form": form,
        "enquetes": page_obj,
        "page_obj": page_obj,
        "classes": classes,
        "filter_classe": filter_classe,
        "selected_classe": selected_classe,
    }
    return render(request, "environnement/index.html", context)


def environnement_export_csv(request):
    filter_classe = request.GET.get("classe")
    qs = EnqueteEnvironnement.objects.select_related("classe", "inspecteur", "enqueteur").order_by("-date")
    if filter_classe:
        qs = qs.filter(classe_id=filter_classe)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=environnement.csv"
    writer = csv.writer(response)
    writer.writerow(
        [
            "classe",
            "inspecteur",
            "enqueteur",
            "date",
            "heure_enregistrement",
            "tables",
            "chaises",
            "ecran",
            "videoprojecteur",
            "ventilation",
            "eclairage",
            "aeration",
            "prises_electriques",
            "salle_propre",
            "salle_accessible",
            "salle_securisee",
            "signaletique",
            "commodite",
            "accessibilite",
            "securite",
            "acces_eau",
            "commentaire_salle",
            "commentaire_global",
        ]
    )
    for e in qs:
        writer.writerow(
            [
                e.classe,
                e.inspecteur,
                e.enqueteur,
                e.date,
                e.heure_enregistrement,
                e.tables,
                e.chaises,
                e.ecran,
                e.videoprojecteur,
                e.ventilation,
                e.eclairage,
                e.aeration,
                e.prises_electriques,
                e.salle_propre,
                e.salle_accessible,
                e.salle_securisee,
                e.signaletique,
                e.commodite,
                e.accessibilite,
                e.securite,
                e.acces_eau,
                e.commentaire_salle,
                e.commentaire_global,
            ]
        )
    return response

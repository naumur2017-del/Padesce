import csv

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from App_PADESCE.messaging.forms import CampagneMessageForm, ContactForm
from App_PADESCE.messaging.models import CampagneMessage, Contact
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

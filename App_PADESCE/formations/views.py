import re
import unicodedata
from urllib.parse import quote

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from App_PADESCE.appels.models import Appel, AppelAnswers, AppelFormateur
from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.core.access import require_analysis_access
from App_PADESCE.formations.forms import ClasseCreateForm
from App_PADESCE.formations.models import Classe, Formation, Lieu, Prestation
from App_PADESCE.presences.models import Presence
from App_PADESCE.satisfaction_apprenants.models import SatisfactionApprenant
from App_PADESCE.satisfaction_formateurs.models import SatisfactionFormateur
from App_PADESCE.environnement.models import EnqueteEnvironnement


APPRENANT_DETAIL_FIELDS = (
    ("Clarte des exposes", "q1_clarte_exposes"),
    ("Interaction avec le formateur", "q2_interaction_formateur"),
    ("Maitrise du contenu", "q3_maitrise_contenu"),
    ("Salle adequate", "q4_salle_adequate"),
    ("Materiel disponible", "q5_materiel_disponible"),
    ("Organisation du temps", "q6_organisation_temps"),
    ("Utilite de la formation", "q7_utilite_formation"),
    ("Adequation aux besoins", "q8_adequation_besoins"),
    ("Satisfaction globale", "q9_satisfaction_globale"),
)

FORMATEUR_SCORE_FIELDS = (
    ("Prerequis apprenants", "q1_prerequis_apprenants"),
    ("Interaction apprenants", "q2_interaction_apprenants"),
    ("Competences acquises", "q3_competences_acquises"),
)

FORMATEUR_TEXT_FIELDS = (
    ("Gestion administrative", "q4_gestion_administrative"),
    ("Gestion financiere", "q5_gestion_financiere"),
    ("Communication", "q6_communication"),
)


def _normalize_analysis_text(value) -> str:
    text = " ".join(str(value or "").strip().lower().split())
    normalized = unicodedata.normalize("NFKD", text)
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", without_accents).strip()


def _phone_digits(value) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _split_source_contact_phones(value) -> list[str]:
    phones = []
    seen = set()
    for chunk in re.split(r"[/,;|]", str(value or "")):
        digits = _phone_digits(chunk)
        if not digits or digits in seen:
            continue
        seen.add(digits)
        phones.append(digits)
    return phones


def _cohorte_matches(raw_value, expected_value) -> bool:
    expected = str(expected_value or "").strip()
    if not expected:
        return True
    raw_text = str(raw_value or "").strip()
    if not raw_text:
        return False
    if raw_text == expected:
        return True
    digits = set(re.findall(r"\d+", raw_text))
    return expected in digits


def _formation_matches(expected_value, current_value) -> bool:
    expected = _normalize_analysis_text(expected_value)
    current = _normalize_analysis_text(current_value)
    if not expected or not current:
        return True
    return expected == current or expected in current or current in expected


def _file_state(file_field) -> tuple[bool, str]:
    if not file_field:
        return False, ""
    name = getattr(file_field, "name", "") or ""
    if not name:
        return False, ""
    try:
        exists = file_field.storage.exists(name)
    except Exception:
        exists = False
    if not exists:
        return False, ""
    try:
        return True, file_field.url
    except Exception:
        return True, ""


def _appel_answers_or_none(appel: Appel):
    try:
        return appel.answers
    except AppelAnswers.DoesNotExist:
        return None


def _satisfaction_or_none(appel: Appel):
    try:
        return appel.satisfaction_apprenant
    except SatisfactionApprenant.DoesNotExist:
        return None


def _resolve_back_url(route_name: str, code: str, tab: str) -> str:
    return f"{reverse(route_name, args=[code])}?tab={tab}"


def _detail_url(route_name: str, pk: int, back_url: str) -> str:
    return f"{reverse(route_name, args=[pk])}?next={quote(back_url, safe='')}"


def _resolve_apprenant_audio(appel: Appel, satisfaction: SatisfactionApprenant | None):
    has_audio, audio_url = _file_state(getattr(appel, "audio_file", None))
    if has_audio:
        return has_audio, audio_url
    if satisfaction:
        return _file_state(getattr(satisfaction, "audio_appel", None))
    return False, ""


def _apprenant_form_state(appel: Appel) -> dict:
    answers = _appel_answers_or_none(appel)
    satisfaction = _satisfaction_or_none(appel)
    question_rows = []
    filled_questions_count = 0

    for label, field_name in APPRENANT_DETAIL_FIELDS:
        value = getattr(answers, field_name, None) if answers else None
        if value is None and satisfaction:
            value = getattr(satisfaction, field_name, None)
        if value is not None:
            filled_questions_count += 1
        question_rows.append((label, value))

    commentaire = (
        str(getattr(answers, "commentaire", "") or "").strip()
        or str(getattr(satisfaction, "commentaire", "") or "").strip()
    )
    recommandations = (
        str(getattr(answers, "recommandations", "") or "").strip()
        or str(getattr(satisfaction, "recommandations", "") or "").strip()
    )
    flags = {
        "pas_forme": bool(getattr(appel, "flag_pas_forme", False)),
        "deja_appele": bool(getattr(appel, "flag_deja_appele", False)),
        "numero_double": bool(getattr(appel, "flag_numero_double", False)),
        "faux_nom": bool(getattr(appel, "flag_faux_nom", False)),
        "vrai_nom": str(getattr(appel, "flag_vrai_nom", "") or "").strip(),
        "deja_forme": bool(getattr(appel, "deja_forme", False)),
    }
    has_form = bool(
        answers
        or satisfaction
        or filled_questions_count
        or commentaire
        or recommandations
        or any(value for value in flags.values())
    )
    return {
        "answers": answers,
        "satisfaction": satisfaction,
        "question_rows": question_rows,
        "filled_questions_count": filled_questions_count,
        "commentaire": commentaire,
        "recommandations": recommandations,
        "flags": flags,
        "has_form": has_form,
    }


def _formateur_form_state(row: AppelFormateur) -> dict:
    score_rows = []
    filled_score_count = 0
    for label, field_name in FORMATEUR_SCORE_FIELDS:
        value = getattr(row, field_name, None)
        if value is not None:
            filled_score_count += 1
        score_rows.append((label, value))

    text_rows = []
    for label, field_name in FORMATEUR_TEXT_FIELDS:
        text_rows.append((label, str(getattr(row, field_name, "") or "").strip()))

    commentaires = str(getattr(row, "commentaires", "") or "").strip()
    recommandations = str(getattr(row, "recommandations", "") or "").strip()
    has_form = bool(
        filled_score_count
        or any(value for _label, value in text_rows)
        or commentaires
        or recommandations
    )
    return {
        "score_rows": score_rows,
        "text_rows": text_rows,
        "filled_score_count": filled_score_count,
        "commentaires": commentaires,
        "recommandations": recommandations,
        "has_form": has_form,
    }


def _apprenant_call_count(appel: Appel, has_form: bool, has_audio: bool) -> int:
    status = str(getattr(appel, "status", "") or "").strip()
    return 1 if status and status != "en_attente" or has_form or has_audio else 0


def _formateur_person_key(row: AppelFormateur) -> str:
    primary_phone = _phone_digits(getattr(row, "telephone", ""))
    if primary_phone:
        return primary_phone
    for phone in _split_source_contact_phones(getattr(row, "source_contact", "")):
        if phone:
            return phone
    return _normalize_analysis_text(getattr(row, "reference_code", ""))


def _status_sort_value(status: str) -> int:
    order = {
        "termine": 0,
        "a_rappeler": 1,
        "pause": 2,
        "en_cours": 3,
        "en_attente": 4,
    }
    return order.get(str(status or "").strip(), 5)


def _prestation_formateur_candidates(prestation: Prestation):
    queryset = AppelFormateur.objects.filter(is_active=True).select_related("locked_by")
    prestataire_name = str(getattr(getattr(prestation, "prestataire", None), "raison_sociale", "") or "").strip()
    beneficiaire_name = str(getattr(getattr(prestation, "beneficiaire", None), "nom_structure", "") or "").strip()
    if prestataire_name:
        queryset = queryset.filter(prestataire__iexact=prestataire_name)
    if beneficiaire_name:
        queryset = queryset.filter(beneficiaire__iexact=beneficiaire_name)
    formation_name = str(getattr(getattr(prestation, "formation", None), "nom", "") or "").strip()
    rows = list(queryset.order_by("session_date", "numero_seance", "reference_code"))
    if formation_name:
        matched_rows = [row for row in rows if _formation_matches(formation_name, row.formation)]
        if matched_rows:
            rows = matched_rows
    return rows


def _class_formateur_candidates(classe: Classe):
    class_phone = _phone_digits(getattr(getattr(classe, "formateur", None), "telephone", ""))
    formation_name = str(classe.intitule_formation or getattr(getattr(classe, "formation", None), "nom", "") or "").strip()
    matched_rows = []
    for row in _prestation_formateur_candidates(classe.prestation):
        if not _cohorte_matches(row.cohorte, classe.cohorte):
            continue
        row_phone_candidates = [_phone_digits(getattr(row, "telephone", "")), *_split_source_contact_phones(row.source_contact)]
        if class_phone and class_phone in row_phone_candidates:
            matched_rows.append(row)
            continue
        if _formation_matches(formation_name, row.formation):
            matched_rows.append(row)
    return matched_rows


def _resolve_classe_for_formateur_analysis(row: AppelFormateur):
    queryset = Classe.objects.select_related(
        "formateur",
        "prestation__prestataire",
        "prestation__beneficiaire",
        "formation",
    ).filter(formateur__isnull=False)
    if row.prestataire:
        queryset = queryset.filter(prestation__prestataire__raison_sociale__iexact=row.prestataire)
    if row.beneficiaire:
        queryset = queryset.filter(prestation__beneficiaire__nom_structure__iexact=row.beneficiaire)
    if row.cohorte and str(row.cohorte).strip().isdigit():
        queryset = queryset.filter(cohorte=int(str(row.cohorte).strip()))

    row_phones = {_phone_digits(row.telephone), *_split_source_contact_phones(row.source_contact)}
    row_phones.discard("")
    candidates = list(queryset)
    for classe in candidates:
        class_phone = _phone_digits(getattr(getattr(classe, "formateur", None), "telephone", ""))
        if class_phone and class_phone in row_phones:
            return classe

    formation_name = str(row.formation or "").strip()
    for classe in candidates:
        current_name = str(classe.intitule_formation or getattr(getattr(classe, "formation", None), "nom", "") or "").strip()
        if _formation_matches(current_name, formation_name):
            return classe
    return candidates[0] if candidates else None


def _build_apprenant_rows(appels, *, back_url: str):
    rows = []
    for appel in appels:
        form_state = _apprenant_form_state(appel)
        satisfaction = form_state["satisfaction"]
        has_audio, audio_url = _resolve_apprenant_audio(appel, satisfaction)
        call_count = _apprenant_call_count(appel, form_state["has_form"], has_audio)
        detail_url = _detail_url("analysis_apprenant_call_detail", appel.pk, back_url)
        rows.append(
            {
                "id": appel.pk,
                "code": appel.code,
                "nom": appel.nom,
                "telephone": appel.telephone1 or appel.telephone2 or "",
                "statut": appel.status,
                "statut_label": appel.get_status_display(),
                "locked_by": getattr(getattr(appel, "locked_by", None), "username", "") or "",
                "call_count": call_count,
                "has_audio": has_audio,
                "audio_url": audio_url,
                "has_form": form_state["has_form"],
                "detail_url": detail_url,
                "updated_at": appel.updated_at,
            }
        )
    return sorted(
        rows,
        key=lambda item: (_status_sort_value(item["statut"]), (item["nom"] or "").casefold(), item["id"]),
    )


def _build_formateur_rows(rows, *, back_url: str):
    count_map = {}
    for row in rows:
        if not (str(getattr(row, "status", "") or "").strip() and row.status != "en_attente"):
            continue
        key = _formateur_person_key(row)
        if not key:
            continue
        count_map[key] = count_map.get(key, 0) + 1

    payload = []
    for row in rows:
        form_state = _formateur_form_state(row)
        has_audio, audio_url = _file_state(getattr(row, "audio_file", None))
        detail_url = _detail_url("analysis_formateur_call_detail", row.pk, back_url)
        person_key = _formateur_person_key(row)
        payload.append(
            {
                "id": row.pk,
                "reference_code": row.reference_code,
                "telephone": row.telephone or "",
                "formation": row.formation or "",
                "cohorte": row.cohorte or "",
                "session_date": row.session_date,
                "date_label": row.date_label or "",
                "statut": row.status,
                "statut_label": row.get_status_display(),
                "call_count": count_map.get(person_key, 0),
                "has_audio": has_audio,
                "audio_url": audio_url,
                "has_form": form_state["has_form"],
                "detail_url": detail_url,
                "updated_at": row.updated_at,
            }
        )
    return sorted(
        payload,
        key=lambda item: (
            _status_sort_value(item["statut"]),
            item["session_date"] or item["updated_at"].date(),
            (item["reference_code"] or "").casefold(),
            item["id"],
        ),
    )


def _entity_summary(apprenant_rows, formateur_rows) -> dict:
    analyzed_apprenants = sum(1 for row in apprenant_rows if row["call_count"] or row["has_form"] or row["has_audio"])
    analyzed_formateurs = sum(1 for row in formateur_rows if row["call_count"] or row["has_form"] or row["has_audio"])
    return {
        "apprenants_total": len(apprenant_rows),
        "apprenants_analyzed": analyzed_apprenants,
        "apprenants_with_audio": sum(1 for row in apprenant_rows if row["has_audio"]),
        "apprenants_with_form": sum(1 for row in apprenant_rows if row["has_form"]),
        "formateurs_total": len(formateur_rows),
        "formateurs_analyzed": analyzed_formateurs,
        "formateurs_with_audio": sum(1 for row in formateur_rows if row["has_audio"]),
        "formateurs_with_form": sum(1 for row in formateur_rows if row["has_form"]),
        "has_analysis": bool(analyzed_apprenants or analyzed_formateurs),
    }


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


@require_analysis_access
def class_analysis_detail(request, code: str):
    classe = get_object_or_404(
        Classe.objects.select_related(
            "prestation",
            "prestation__prestataire",
            "prestation__beneficiaire",
            "formation",
            "lieu",
            "formateur",
        ).prefetch_related("apprenants"),
        code__iexact=code,
    )
    active_tab = request.GET.get("tab") if request.GET.get("tab") in {"apprenants", "formateurs"} else "apprenants"
    apprenant_back_url = _resolve_back_url("class_analysis_detail", classe.code, "apprenants")
    formateur_back_url = _resolve_back_url("class_analysis_detail", classe.code, "formateurs")

    apprenant_appels = list(
        Appel.objects.filter(is_active=True, classe=classe)
        .select_related(
            "locked_by",
            "classe",
            "classe__prestation",
            "classe__prestation__prestataire",
            "classe__prestation__beneficiaire",
            "answers",
            "satisfaction_apprenant",
        )
        .order_by("nom", "code", "pk")
    )
    formateur_appels = _class_formateur_candidates(classe)

    apprenant_rows = _build_apprenant_rows(apprenant_appels, back_url=apprenant_back_url)
    formateur_rows = _build_formateur_rows(formateur_appels, back_url=formateur_back_url)
    summary = _entity_summary(apprenant_rows, formateur_rows)

    return render(
        request,
        "formations/analysis_entity_detail.html",
        {
            "entity_type": "classe",
            "entity_title": classe.code,
            "entity_subtitle": classe.intitule_formation,
            "entity": classe,
            "classe": classe,
            "prestation": classe.prestation,
            "apprenant_rows": apprenant_rows,
            "formateur_rows": formateur_rows,
            "summary": summary,
            "active_tab": active_tab,
            "class_links": [],
            "matching_note": "Rattachement formateurs via prestataire, beneficiaire, cohorte et formation.",
        },
    )


@require_analysis_access
def prestation_analysis_detail(request, code: str):
    prestation = get_object_or_404(
        Prestation.objects.select_related("prestataire", "formation", "beneficiaire").prefetch_related(
            Prefetch(
                "classes",
                queryset=Classe.objects.select_related("lieu", "formateur").annotate(
                    apprenants_count=Count("apprenants", distinct=True),
                    appels_count=Count("appels", distinct=True),
                ).order_by("code"),
            )
        ),
        code__iexact=code,
    )
    active_tab = request.GET.get("tab") if request.GET.get("tab") in {"apprenants", "formateurs"} else "apprenants"
    apprenant_back_url = _resolve_back_url("prestation_analysis_detail", prestation.code, "apprenants")
    formateur_back_url = _resolve_back_url("prestation_analysis_detail", prestation.code, "formateurs")

    apprenant_appels = list(
        Appel.objects.filter(is_active=True, classe__prestation=prestation)
        .select_related(
            "locked_by",
            "classe",
            "classe__prestation",
            "classe__prestation__prestataire",
            "classe__prestation__beneficiaire",
            "answers",
            "satisfaction_apprenant",
        )
        .order_by("classe__code", "nom", "code", "pk")
    )
    formateur_appels = _prestation_formateur_candidates(prestation)

    apprenant_rows = _build_apprenant_rows(apprenant_appels, back_url=apprenant_back_url)
    formateur_rows = _build_formateur_rows(formateur_appels, back_url=formateur_back_url)
    summary = _entity_summary(apprenant_rows, formateur_rows)
    class_links = [
        {
            "code": item.code,
            "intitule": item.intitule_formation,
            "apprenants_count": item.apprenants_count,
            "appels_count": item.appels_count,
            "url": reverse("class_analysis_detail", args=[item.code]),
        }
        for item in prestation.classes.all()
    ]

    return render(
        request,
        "formations/analysis_entity_detail.html",
        {
            "entity_type": "prestation",
            "entity_title": prestation.code,
            "entity_subtitle": str(getattr(getattr(prestation, "formation", None), "nom", "") or prestation),
            "entity": prestation,
            "prestation": prestation,
            "classe": None,
            "apprenant_rows": apprenant_rows,
            "formateur_rows": formateur_rows,
            "summary": summary,
            "active_tab": active_tab,
            "class_links": class_links,
            "matching_note": "Rattachement formateurs via prestataire, beneficiaire et formation.",
        },
    )


@require_analysis_access
def analysis_apprenant_call_detail(request, pk: int):
    appel = get_object_or_404(
        Appel.objects.filter(is_active=True).select_related(
            "locked_by",
            "classe",
            "classe__prestation",
            "classe__prestation__prestataire",
            "classe__prestation__beneficiaire",
            "answers",
            "satisfaction_apprenant",
        ),
        pk=pk,
    )
    form_state = _apprenant_form_state(appel)
    has_audio, audio_url = _resolve_apprenant_audio(appel, form_state["satisfaction"])
    next_url = request.GET.get("next") or reverse("satisfaction_dashboard")
    return render(
        request,
        "formations/analysis_apprenant_call_detail.html",
        {
            "appel": appel,
            "form_state": form_state,
            "has_audio": has_audio,
            "audio_url": audio_url,
            "next_url": next_url,
            "filled_questions_count": form_state["filled_questions_count"],
        },
    )


@require_analysis_access
def analysis_formateur_call_detail(request, pk: int):
    row = get_object_or_404(
        AppelFormateur.objects.filter(is_active=True).select_related("locked_by"),
        pk=pk,
    )
    form_state = _formateur_form_state(row)
    has_audio, audio_url = _file_state(getattr(row, "audio_file", None))
    next_url = request.GET.get("next") or reverse("satisfaction_formateurs_dashboard")
    resolved_classe = _resolve_classe_for_formateur_analysis(row)
    return render(
        request,
        "formations/analysis_formateur_call_detail.html",
        {
            "row": row,
            "form_state": form_state,
            "has_audio": has_audio,
            "audio_url": audio_url,
            "next_url": next_url,
            "resolved_classe": resolved_classe,
            "filled_score_count": form_state["filled_score_count"],
        },
    )


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

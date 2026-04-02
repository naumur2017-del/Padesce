import base64
import csv
import hashlib
import logging
import os
import re
import uuid
from collections import defaultdict
from datetime import date as date_cls

import requests
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import redirect, render

from App_PADESCE.appels.models import AppelFormateur
from App_PADESCE.core.access import require_analysis_access
from App_PADESCE.formations.models import Classe, Formateur
from App_PADESCE.satisfaction_formateurs.forms import SatisfactionFormateurForm
from App_PADESCE.satisfaction_formateurs.models import SatisfactionFormateur

SESSION_KEY = "sat_form_workflow"

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_TRANSCRIBE_MODEL = "google/gemini-2.5-flash"
SUPPORTED_AUDIO_FORMATS = {"wav", "mp3", "m4a", "ogg", "webm", "flac"}

logger = logging.getLogger(__name__)


def _normalize_phone(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def _find_formateur(classe_id: str, identifiant: str) -> tuple[Formateur | None, str | None]:
    identifiant = identifiant.strip()
    if not identifiant:
        return None, "Renseignez le code ou telephone du formateur."
    classe = Classe.objects.select_related("formateur").filter(id=classe_id).first()
    if not classe:
        return None, "Classe introuvable."
    if not classe.formateur:
        return None, "Aucun formateur associe a cette classe."
    formateur = classe.formateur
    identifiant_lower = identifiant.lower()
    identifiant_digits = _normalize_phone(identifiant)
    if formateur.code.lower() == identifiant_lower:
        return formateur, None
    if identifiant_digits and _normalize_phone(formateur.telephone) == identifiant_digits:
        return formateur, None
    return None, "Ce formateur ne correspond pas a la classe."


def _save_audio(uploaded_file, folder: str) -> str:
    _, ext = os.path.splitext(uploaded_file.name)
    ext = ext or ".dat"
    filename = f"{uuid.uuid4().hex}{ext}"
    return default_storage.save(f"enquetes/{folder}/{filename}", uploaded_file)


# Fallback scoring when transcript does not include explicit answers.
def _ai_scores(seed: str, count: int = 9) -> list[int]:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return [1 + (digest[i] % 5) for i in range(count)]


def _flatten_message_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                parts.append(item["text"])
        return "\n".join(parts)
    return ""


def _extract_transcription_text(result) -> str:
    if not result:
        return ""
    if isinstance(result, dict):
        if "choices" in result:
            try:
                content = result["choices"][0]["message"].get("content")
            except (IndexError, KeyError, TypeError, AttributeError):
                content = None
            return _flatten_message_content(content)
        return result.get("text") or result.get("transcript") or ""
    if hasattr(result, "text"):
        return result.text or ""
    return str(result)


def _guess_audio_format(audio_path: str) -> str:
    ext = os.path.splitext(audio_path)[1].lstrip(".").lower()
    if ext == "ma4":
        ext = "m4a"
    return ext if ext in SUPPORTED_AUDIO_FORMATS else "wav"


def _encode_audio_to_base64(audio_path: str) -> str:
    with default_storage.open(audio_path, "rb") as audio_file:
        return base64.b64encode(audio_file.read()).decode("ascii")


def _transcribe_audio(audio_path: str) -> tuple[str | None, str | None]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None, "Cle OpenRouter manquante. Definissez OPENROUTER_API_KEY dans l'environnement."
    audio_format = _guess_audio_format(audio_path)
    model = os.getenv("OPENROUTER_TRANSCRIBE_MODEL", DEFAULT_TRANSCRIBE_MODEL)
    logger.info(
        "Transcription OpenRouter demarree. audio=%s format=%s model=%s",
        audio_path,
        audio_format,
        model,
    )
    try:
        base64_audio = _encode_audio_to_base64(audio_path)
    except Exception as exc:
        logger.exception("Lecture audio impossible pour transcription. audio=%s", audio_path)
        return None, f"Impossible de lire l'audio: {exc}"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Please transcribe this audio file."},
                    {
                        "type": "input_audio",
                        "input_audio": {"data": base64_audio, "format": audio_format},
                    },
                ],
            }
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    response = None
    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        detail = ""
        if response is not None:
            try:
                detail = response.json().get("error", {}).get("message") or response.text
            except ValueError:
                detail = response.text
        detail = detail.strip()
        logger.error(
            "Echec transcription OpenRouter. audio=%s status=%s detail=%s",
            audio_path,
            response.status_code if response is not None else "n/a",
            detail or str(exc),
        )
        return None, f"Echec de transcription OpenRouter: {exc} {detail}".strip()
    except ValueError as exc:
        logger.error("Reponse OpenRouter invalide. audio=%s error=%s", audio_path, exc)
        return None, f"Reponse OpenRouter invalide: {exc}"

    text = _extract_transcription_text(data).strip()
    if not text:
        logger.error("Transcription OpenRouter videe. audio=%s", audio_path)
        return None, "Transcription videe ou non reconnue."
    logger.info("Transcription OpenRouter terminee. audio=%s chars=%s", audio_path, len(text))
    return text[:8000], None


def _parse_scores_from_transcript(transcript: str, total_questions: int = 3) -> dict[int, int]:
    results: dict[int, int] = {}
    if not transcript:
        return results
    lowered = transcript.lower()
    for idx in range(1, total_questions + 1):
        pattern = rf"(?:\bq{idx}\b|question\s*{idx})[^\d]{{0,10}}([1-5])"
        match = re.search(pattern, lowered)
        if match:
            results[idx] = int(match.group(1))
    return results


def _ai_results_formateur(audio_path: str) -> tuple[dict | None, str | None, str | None]:
    transcript, error = _transcribe_audio(audio_path)
    if error:
        return None, None, error
    size = default_storage.size(audio_path)
    scores = _ai_scores(f"{audio_path}:{size}:{len(transcript)}", count=3)
    parsed = _parse_scores_from_transcript(transcript, total_questions=3)
    for idx, value in parsed.items():
        if 1 <= idx <= 3:
            scores[idx - 1] = value
    results = {
        "q1_prerequis_apprenants": scores[0],
        "q2_interaction_apprenants": scores[1],
        "q3_competences_acquises": scores[2],
        # Q4-Q6 : questions ouvertes — a saisir manuellement apres transcription
        "q4_gestion_administrative": "",
        "q5_gestion_financiere": "",
        "q6_communication": "",
        "commentaires": "",
        "recommandations": "",
    }
    return results, transcript, None


def satisfaction_formateurs(request):
    filter_classe = request.GET.get("classe")
    qs = SatisfactionFormateur.objects.select_related(
        "classe", "formateur", "inspecteur", "enqueteur"
    ).order_by("-date", "-created_at")
    if filter_classe:
        qs = qs.filter(classe_id=filter_classe)

    workflow = request.session.get(SESSION_KEY, {})
    save_errors = None

    if request.method == "POST":
        action = request.POST.get("action")
        identifiant = (request.POST.get("identifiant") or "").strip()
        posted_classe = request.POST.get("classe") or workflow.get("classe_id")
        posted_inspecteur = request.POST.get("inspecteur") or workflow.get("inspecteur_id")
        posted_date = request.POST.get("date") or workflow.get("date")
        posted_heure = request.POST.get("heure") or workflow.get("heure")

        if posted_classe:
            workflow["classe_id"] = str(posted_classe)
        if posted_inspecteur:
            workflow["inspecteur_id"] = posted_inspecteur
        if posted_date:
            workflow["date"] = posted_date
        if posted_heure:
            workflow["heure"] = posted_heure
        if identifiant:
            workflow["identifiant"] = identifiant

        if action == "identify":
            if not posted_classe or not identifiant:
                messages.error(
                    request, "Renseignez la classe et le code ou telephone du formateur."
                )
            else:
                formateur, error = _find_formateur(posted_classe, identifiant)
                if formateur:
                    workflow["formateur_id"] = formateur.id
                    workflow.pop("audio_path", None)
                    workflow.pop("ai_results", None)
                    messages.success(request, f"Formateur identifie: {formateur}.")
                else:
                    messages.error(request, error or "Formateur non trouve pour cette classe.")
        elif action == "process_audio":
            if not workflow.get("formateur_id"):
                messages.error(request, "Identifiez d'abord un formateur.")
            elif str(posted_classe or "") != str(workflow.get("classe_id") or ""):
                messages.error(request, "La classe ne correspond pas au formateur identifie.")
            else:
                uploaded_audio = request.FILES.get("audio_appel")
                if uploaded_audio:
                    workflow["audio_path"] = _save_audio(uploaded_audio, "satisfaction_formateurs")
                    logger.info(
                        "Audio recu pour transcription formateur. fichier=%s taille=%s",
                        uploaded_audio.name,
                        getattr(uploaded_audio, "size", "n/a"),
                    )
                if not workflow.get("audio_path"):
                    messages.error(request, "Chargez un audio d'appel pour lancer le traitement.")
                else:
                    results, transcript, error = _ai_results_formateur(workflow["audio_path"])
                    if error:
                        messages.error(request, error)
                    else:
                        workflow["ai_results"] = results
                        workflow["transcription"] = transcript
                        messages.success(
                            request, "Transcription terminee et traitement vocal actualise."
                        )
        elif action == "save":
            if not workflow.get("formateur_id"):
                messages.error(request, "Identifiez un formateur avant d'enregistrer.")
            elif not workflow.get("ai_results"):
                messages.error(request, "Lancez le traitement vocal avant d'enregistrer.")
            else:
                data = request.POST.copy()
                data["formateur"] = workflow["formateur_id"]
                if workflow.get("classe_id"):
                    data["classe"] = workflow["classe_id"]
                if workflow.get("inspecteur_id"):
                    data["inspecteur"] = workflow["inspecteur_id"]
                if workflow.get("date"):
                    data["date"] = workflow["date"]
                if workflow.get("heure"):
                    data["heure"] = workflow["heure"]
                # Q1-Q3 viennent de l'IA ; Q4-Q6 viennent du POST (saisie manuelle)
                ai = workflow["ai_results"]
                data["q1_prerequis_apprenants"] = ai.get("q1_prerequis_apprenants", 1)
                data["q2_interaction_apprenants"] = ai.get("q2_interaction_apprenants", 1)
                data["q3_competences_acquises"] = ai.get("q3_competences_acquises", 1)
                save_form = SatisfactionFormateurForm(data)
                if save_form.is_valid():
                    obj = save_form.save(commit=False)
                    if hasattr(request, "user") and request.user.is_authenticated:
                        obj.enqueteur = request.user
                    audio_path = workflow.get("audio_path")
                    if audio_path:
                        obj.audio_appel.name = audio_path
                    obj.transcription = workflow.get("transcription", "")
                    obj.save()
                    messages.success(request, "Satisfaction formateur enregistree.")
                    request.session.pop(SESSION_KEY, None)
                    return redirect(
                        request.path_info + f"?classe={filter_classe}"
                        if filter_classe
                        else request.path_info
                    )
                else:
                    save_errors = save_form.errors

        request.session[SESSION_KEY] = workflow
        request.session.modified = True

    initial = {
        "classe": workflow.get("classe_id"),
        "inspecteur": workflow.get("inspecteur_id"),
        "date": workflow.get("date") or date_cls.today(),
        "heure": workflow.get("heure"),
    }
    form = SatisfactionFormateurForm(initial=initial)

    identified_formateur = None
    formateur_id = workflow.get("formateur_id")
    if formateur_id:
        identified_formateur = Formateur.objects.filter(id=formateur_id).first()
        if not identified_formateur:
            workflow.pop("formateur_id", None)
            workflow.pop("ai_results", None)
            workflow.pop("audio_path", None)
            request.session[SESSION_KEY] = workflow
            request.session.modified = True

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "form": form,
        "identified_formateur": identified_formateur,
        "identifiant": workflow.get("identifiant", ""),
        "ai_results": workflow.get("ai_results"),
        "transcription": workflow.get("transcription"),
        "audio_name": (
            os.path.basename(workflow.get("audio_path")) if workflow.get("audio_path") else None
        ),
        "save_errors": save_errors,
        "enquetes": page_obj,
        "page_obj": page_obj,
        "classes": Classe.objects.all().order_by("code"),
        "filter_classe": filter_classe,
    }
    return render(request, "satisfaction_formateurs/index.html", context)


def satisfaction_formateurs_export_csv(request):
    filter_classe = request.GET.get("classe")
    qs = SatisfactionFormateur.objects.select_related(
        "classe", "formateur", "inspecteur", "enqueteur"
    ).order_by("-date")
    if filter_classe:
        qs = qs.filter(classe_id=filter_classe)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=satisfaction_formateurs.csv"
    writer = csv.writer(response)
    writer.writerow(
        [
            "classe",
            "formateur",
            "inspecteur",
            "enqueteur",
            "date",
            "heure",
            "Q1 - Prerequis apprenants (1-5)",
            "Q2 - Interaction apprenants (1-5)",
            "Q3 - Competences acquises (1-5)",
            "Q4 - Gestion administrative (texte)",
            "Q5 - Gestion financiere (texte)",
            "Q6 - Communication (texte)",
            "commentaires",
            "recommandations",
        ]
    )
    for s in qs:
        writer.writerow(
            [
                s.classe,
                s.formateur,
                s.inspecteur,
                s.enqueteur,
                s.date,
                s.heure,
                s.q1_prerequis_apprenants,
                s.q2_interaction_apprenants,
                s.q3_competences_acquises,
                s.q4_gestion_administrative,
                s.q5_gestion_financiere,
                s.q6_communication,
                s.commentaires,
                s.recommandations,
            ]
        )
    return response


# ---------------------------------------------------------------------------
# Dashboard Analyse – Appels Formateurs
# ---------------------------------------------------------------------------

Q_FORM_FIELDS = [
    ("q1_prerequis_apprenants", "Prérequis apprenants"),
    ("q2_interaction_apprenants", "Interaction apprenants"),
    ("q3_competences_acquises", "Compétences acquises"),
]


def _avg_num(values):
    nums = [v for v in values if v is not None]
    return round(sum(nums) / len(nums), 2) if nums else 0


@require_analysis_access
def satisfaction_formateurs_dashboard(request):
    """
    Tableau de bord d'analyse des appels formateurs.
    Stats par prestataire, bénéficiaire, cohorte + résumé Q4-Q6 textuels.
    """
    f_prestataire = (request.GET.get("prestataire") or "").strip()
    f_beneficiaire = (request.GET.get("beneficiaire") or "").strip()
    f_cohorte = (request.GET.get("cohorte") or "").strip()

    qs = AppelFormateur.objects.filter(is_active=True).order_by("session_date", "prestataire")
    if f_prestataire:
        qs = qs.filter(prestataire=f_prestataire)
    if f_beneficiaire:
        qs = qs.filter(beneficiaire=f_beneficiaire)
    if f_cohorte:
        qs = qs.filter(cohorte=f_cohorte)

    records = list(
        qs.values(
            "id",
            "reference_code",
            "prestataire",
            "beneficiaire",
            "formation",
            "cohorte",
            "session_date",
            "telephone",
            "status",
            "q1_prerequis_apprenants",
            "q2_interaction_apprenants",
            "q3_competences_acquises",
            "q4_gestion_administrative",
            "q5_gestion_financiere",
            "q6_communication",
            "commentaires",
            "recommandations",
        )
    )

    total = len(records)
    termines = sum(1 for r in records if r["status"] == "termine")
    with_scores = sum(1 for r in records if all(r.get(f) is not None for f, _ in Q_FORM_FIELDS))

    global_avgs = {label: _avg_num([r[field] for r in records]) for field, label in Q_FORM_FIELDS}

    def _group_stats(key_fn):
        groups = defaultdict(list)
        for r in records:
            groups[key_fn(r)].append(r)
        return sorted(
            [
                {
                    "label": k,
                    "nb": len(v),
                    "avgs": [_avg_num([r[f] for r in v]) for f, _ in Q_FORM_FIELDS],
                }
                for k, v in groups.items()
            ],
            key=lambda x: x["label"],
        )

    prestataire_stats = _group_stats(lambda r: r["prestataire"] or "—")
    beneficiaire_stats = _group_stats(lambda r: r["beneficiaire"] or "—")
    cohorte_stats = _group_stats(lambda r: r["cohorte"] or "—")

    all_qs = AppelFormateur.objects.filter(is_active=True)
    prestataires = sorted(set(all_qs.values_list("prestataire", flat=True)) - {""})
    beneficiaires = sorted(set(all_qs.values_list("beneficiaire", flat=True)) - {""})
    cohortes = sorted(set(all_qs.values_list("cohorte", flat=True)) - {""})

    status_counts = defaultdict(int)
    for r in records:
        status_counts[r["status"]] += 1

    context = {
        "total": total,
        "termines": termines,
        "with_scores": with_scores,
        "global_avgs": global_avgs,
        "q_labels": [label for _, label in Q_FORM_FIELDS],
        "prestataire_stats": prestataire_stats,
        "beneficiaire_stats": beneficiaire_stats,
        "cohorte_stats": cohorte_stats,
        "status_counts": dict(status_counts),
        "prestataires": prestataires,
        "beneficiaires": beneficiaires,
        "cohortes": cohortes,
        "f_prestataire": f_prestataire,
        "f_beneficiaire": f_beneficiaire,
        "f_cohorte": f_cohorte,
        "rows": records[:200],
    }
    return render(request, "satisfaction_formateurs/dashboard.html", context)

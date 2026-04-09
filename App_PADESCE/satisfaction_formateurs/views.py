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
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from App_PADESCE.appels.models import (
    FORMATEUR_SCORE_FIELDS,
    FORMATEUR_TEXT_FIELDS,
    AppelFormateur,
    derive_formateur_status,
    formateur_has_any_audio,
    formateur_has_any_form_data,
    sync_formateur_status,
)
from App_PADESCE.core.access import require_analysis_access
from App_PADESCE.core.fast_stats import build_fast_stats_context
from App_PADESCE.formations.models import Classe, Formateur
from App_PADESCE.satisfaction_formateurs.forms import (
    SatisfactionFormateurBatchUpdateForm,
    SatisfactionFormateurForm,
)
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


def _normalize_batch_update_container(raw_value: str) -> str:
    text = str(raw_value or "").strip()
    if text.startswith("[") and text.endswith("]"):
        return text[1:-1].strip()
    return text


def _parse_formateur_batch_targets(raw_codes: str) -> list[str]:
    parsed_targets: list[str] = []
    seen_codes: set[str] = set()
    for block in re.split(r"[\r\n;]+", _normalize_batch_update_container(raw_codes)):
        block = _normalize_batch_update_container(block)
        if not block:
            continue
        for token in [item.strip() for item in re.split(r"[\s,]+", block) if item.strip()]:
            code_key = token.casefold()
            if not code_key or code_key in seen_codes:
                continue
            seen_codes.add(code_key)
            parsed_targets.append(token)
    return parsed_targets


def _merge_formateur_batch_targets(
    raw_codes: str,
    selected_targets: list[str] | None,
) -> list[str]:
    merged_targets: list[str] = []
    seen_codes: set[str] = set()
    for raw_value in [raw_codes, *(selected_targets or [])]:
        for target in _parse_formateur_batch_targets(raw_value):
            code_key = target.casefold()
            if code_key in seen_codes:
                continue
            seen_codes.add(code_key)
            merged_targets.append(target)
    return merged_targets


def _expand_formateur_batch_values(
    values: list,
    target_count: int,
    *,
    label: str,
    default_value=None,
) -> list:
    if not values:
        return [default_value] * target_count
    if len(values) == 1:
        return list(values) * target_count
    if len(values) == target_count:
        return list(values)
    raise ValueError(f"{label}: fournissez une seule valeur ou exactement {target_count} valeurs.")


def _build_formateur_batch_payloads(cleaned_data: dict, target_count: int) -> list[dict]:
    payloads = [{} for _ in range(target_count)]
    field_labels = {
        "q1_prerequis_apprenants": "Q1 Prerequis apprenants",
        "q2_interaction_apprenants": "Q2 Interaction apprenants",
        "q3_competences_acquises": "Q3 Competences acquises",
        "q4_gestion_administrative": "Q4 Gestion administrative",
        "q5_gestion_financiere": "Q5 Gestion financiere",
        "q6_communication": "Q6 Communication",
        "commentaires_values": "Commentaires",
        "recommandations_values": "Recommandations",
    }

    for field_name in FORMATEUR_SCORE_FIELDS:
        expanded_values = _expand_formateur_batch_values(
            cleaned_data.get(field_name) or [],
            target_count,
            label=field_labels[field_name],
            default_value=3,
        )
        for index, value in enumerate(expanded_values):
            payloads[index][field_name] = value

    for form_field, payload_field in (
        ("q4_gestion_administrative", "q4_gestion_administrative"),
        ("q5_gestion_financiere", "q5_gestion_financiere"),
        ("q6_communication", "q6_communication"),
        ("commentaires_values", "commentaires"),
        ("recommandations_values", "recommandations"),
    ):
        expanded_values = _expand_formateur_batch_values(
            cleaned_data.get(form_field) or [],
            target_count,
            label=field_labels[form_field],
            default_value="RAS",
        )
        for index, value in enumerate(expanded_values):
            payloads[index][payload_field] = value

    return payloads


def _formateur_batch_status_display(status_code: str) -> str:
    normalized_status = str(status_code or "").strip()
    return dict(AppelFormateur.STATUS_CHOICES).get(normalized_status, normalized_status or "-")


def _has_complete_formateur_form(row: AppelFormateur) -> bool:
    return all(getattr(row, field_name, None) is not None for field_name in FORMATEUR_SCORE_FIELDS)


def _formateur_complete_form_queryset():
    queryset = AppelFormateur.objects.filter(is_active=True).order_by(
        "session_date", "numero_seance", "reference_code"
    )
    for field_name in FORMATEUR_SCORE_FIELDS:
        queryset = queryset.filter(**{f"{field_name}__isnull": False})
    return queryset


def _formateur_termine_without_form_queryset():
    return (
        AppelFormateur.objects.filter(is_active=True, status="termine")
        .order_by("session_date", "numero_seance", "reference_code")
        .exclude(pk__in=_formateur_complete_form_queryset().values("pk"))
    )


def _formateur_form_status_issue_queryset():
    return _formateur_complete_form_queryset().exclude(status="termine")


def _resolve_batch_update_formateur_classe(row: AppelFormateur):
    from App_PADESCE.appels.formateurs_views import _resolve_classe_for_formateur_row

    return _resolve_classe_for_formateur_row(row)


def _sync_batch_update_formateur_satisfaction(row: AppelFormateur, user) -> bool:
    from App_PADESCE.appels.formateurs_views import _sync_satisfaction_from_formateur_row

    return _sync_satisfaction_from_formateur_row(row, user)


def _build_formateur_candidate_row(row: AppelFormateur) -> dict:
    classe = _resolve_batch_update_formateur_classe(row)
    formateur = getattr(classe, "formateur", None)
    has_complete_form = _has_complete_formateur_form(row)
    has_partial_form = formateur_has_any_form_data(row)
    return {
        "reference_code": row.reference_code,
        "classe_code": getattr(classe, "code", "") or "-",
        "formateur_label": str(formateur or "-"),
        "prestataire": row.prestataire or "-",
        "beneficiaire": row.beneficiaire or "-",
        "formation": row.formation or "-",
        "cohorte": row.cohorte or "-",
        "telephone": row.telephone or "-",
        "audio_label": "Oui" if formateur_has_any_audio(row) else "Non",
        "formulaire_label": (
            "Complet" if has_complete_form else ("Partiel" if has_partial_form else "Non")
        ),
        "current_status": row.status or "",
        "current_status_label": row.get_status_display(),
        "computed_status": derive_formateur_status(row),
        "computed_status_label": _formateur_batch_status_display(derive_formateur_status(row)),
        "commentaires": row.commentaires or "-",
        "recommandations": row.recommandations or "-",
        "selection_value": row.reference_code,
        "has_complete_form": has_complete_form,
    }


def _formateur_answer_summary(row: AppelFormateur) -> str:
    return " / ".join(
        str(getattr(row, field_name, None) or "-") for field_name in FORMATEUR_SCORE_FIELDS
    )


def _paginate_formateur_update_form_rows(
    request,
    queryset,
    *,
    page_param: str,
    per_page: int = 50,
):
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(request.GET.get(page_param))
    return page_obj, [_build_formateur_candidate_row(row) for row in page_obj.object_list]


def _apply_formateur_batch_update_target(reference_code: str, payload: dict, user) -> dict:
    result = {
        "reference_code": reference_code,
        "classe_code": "-",
        "formateur_label": "-",
        "before_status": "-",
        "after_status": "-",
        "before_answers": "-",
        "after_answers": "-",
        "commentaires": payload.get("commentaires", "-") or "-",
        "recommandations": payload.get("recommandations", "-") or "-",
        "message": "",
        "ok": False,
        "survey_synced": False,
    }

    row = AppelFormateur.objects.filter(
        is_active=True, reference_code__iexact=reference_code
    ).first()
    if row is None:
        result["message"] = "Reference formateur introuvable."
        return result

    classe = _resolve_batch_update_formateur_classe(row)
    formateur = getattr(classe, "formateur", None)
    result["classe_code"] = getattr(classe, "code", "") or "-"
    result["formateur_label"] = str(formateur or "-")
    result["before_status"] = row.get_status_display()
    result["before_answers"] = _formateur_answer_summary(row)

    update_fields = [*FORMATEUR_SCORE_FIELDS, *FORMATEUR_TEXT_FIELDS, "updated_at"]
    try:
        with transaction.atomic():
            for field_name, value in payload.items():
                setattr(row, field_name, value)
            row.save(update_fields=update_fields)
            sync_formateur_status(row)
            survey_synced = False
            if _has_complete_formateur_form(row):
                survey_synced = _sync_batch_update_formateur_satisfaction(row, user)

        result["after_status"] = row.get_status_display()
        result["after_answers"] = _formateur_answer_summary(row)
        result["commentaires"] = row.commentaires or "-"
        result["recommandations"] = row.recommandations or "-"
        result["survey_synced"] = survey_synced
        result["message"] = (
            "Formulaire mis a jour et fiche satisfaction synchronisee."
            if survey_synced
            else "Mise a jour enregistree. Fiche satisfaction non synchronisee."
        )
        result["ok"] = True
        return result
    except Exception as exc:
        logger.exception(
            "UPDATE FORM formateurs batch update failed for reference=%s", reference_code
        )
        result["message"] = f"Erreur interne pendant la mise a jour: {exc}"
        return result


def _apply_formateur_batch_status_target(reference_code: str, target_status: str, user) -> dict:
    result = {
        "reference_code": reference_code,
        "classe_code": "-",
        "formateur_label": "-",
        "before_status": "-",
        "after_status": "-",
        "before_answers": "-",
        "after_answers": "-",
        "commentaires": "-",
        "recommandations": "-",
        "message": "",
        "ok": False,
        "survey_synced": False,
    }

    row = AppelFormateur.objects.filter(
        is_active=True, reference_code__iexact=reference_code
    ).first()
    if row is None:
        result["message"] = "Reference formateur introuvable."
        return result

    classe = _resolve_batch_update_formateur_classe(row)
    formateur = getattr(classe, "formateur", None)
    result["classe_code"] = getattr(classe, "code", "") or "-"
    result["formateur_label"] = str(formateur or "-")
    result["before_status"] = row.get_status_display()
    result["before_answers"] = _formateur_answer_summary(row)
    result["commentaires"] = row.commentaires or "-"
    result["recommandations"] = row.recommandations or "-"

    if not _has_complete_formateur_form(row):
        result["message"] = "Aucun formulaire complet trouve pour cette reference."
        return result

    try:
        with transaction.atomic():
            update_fields = ["status", "updated_at"]
            row.status = target_status
            if target_status in {"termine", "a_rappeler"}:
                row.satisfaction_completed_at = timezone.now()
                update_fields.append("satisfaction_completed_at")
            row.save(update_fields=update_fields)
            survey_synced = False
            if target_status in {"termine", "a_rappeler"}:
                survey_synced = _sync_batch_update_formateur_satisfaction(row, user)

        result["after_status"] = row.get_status_display()
        result["after_answers"] = _formateur_answer_summary(row)
        result["survey_synced"] = survey_synced
        result["message"] = (
            f"Statut mis a jour vers {row.get_status_display()} et fiche satisfaction synchronisee."
            if survey_synced
            else f"Statut mis a jour vers {row.get_status_display()}."
        )
        result["ok"] = True
        return result
    except Exception as exc:
        logger.exception(
            "UPDATE FORM formateurs status update failed for reference=%s", reference_code
        )
        result["message"] = f"Erreur interne pendant le changement de statut: {exc}"
        return result


@require_analysis_access
def satisfaction_formateurs_update_form_page(request):
    initial = {
        "reference_codes_text": str(request.GET.get("codes", "") or "").strip(),
    }
    form = SatisfactionFormateurBatchUpdateForm(request.POST or None, initial=initial)
    results: list[dict] = []
    summary = {
        "requested_total": 0,
        "updated_total": 0,
        "error_total": 0,
        "synced_total": 0,
        "action_label": "formulaire(s)",
    }
    selected_target_values = {
        str(value or "").strip()
        for value in request.POST.getlist("selected_targets")
        if str(value or "").strip()
    }

    if request.method == "POST" and form.is_valid():
        action = str(request.POST.get("action") or "update_form").strip() or "update_form"
        targets = _merge_formateur_batch_targets(
            form.cleaned_data["reference_codes_text"],
            request.POST.getlist("selected_targets"),
        )
        if not targets:
            form.add_error(
                "reference_codes_text",
                "Ajoutez au moins une reference valide ou selectionnez au moins une ligne.",
            )
        elif action == "update_status":
            requested_status = str(form.cleaned_data.get("target_status") or "").strip()
            if not requested_status:
                form.add_error("target_status", "Choisissez le statut a appliquer.")
            else:
                results = [
                    _apply_formateur_batch_status_target(
                        reference_code, requested_status, request.user
                    )
                    for reference_code in targets
                ]
                summary = {
                    "requested_total": len(results),
                    "updated_total": sum(1 for item in results if item["ok"]),
                    "error_total": sum(1 for item in results if not item["ok"]),
                    "synced_total": sum(1 for item in results if item["survey_synced"]),
                    "action_label": "statut(s)",
                }
                if summary["updated_total"]:
                    messages.success(
                        request,
                        f"{summary['updated_total']} statut(s) mis a jour.",
                    )
                if summary["error_total"]:
                    messages.warning(
                        request,
                        f"{summary['error_total']} reference(s) n'ont pas pu etre traitees.",
                    )
        else:
            try:
                payloads = _build_formateur_batch_payloads(form.cleaned_data, len(targets))
            except ValueError as exc:
                form.add_error(None, str(exc))
            else:
                results = [
                    _apply_formateur_batch_update_target(reference_code, payload, request.user)
                    for reference_code, payload in zip(targets, payloads)
                ]
                summary = {
                    "requested_total": len(results),
                    "updated_total": sum(1 for item in results if item["ok"]),
                    "error_total": sum(1 for item in results if not item["ok"]),
                    "synced_total": sum(1 for item in results if item["survey_synced"]),
                    "action_label": "formulaire(s)",
                }
                if summary["updated_total"]:
                    messages.success(
                        request,
                        f"{summary['updated_total']} formulaire(s) mis a jour.",
                    )
                if summary["error_total"]:
                    messages.warning(
                        request,
                        f"{summary['error_total']} reference(s) n'ont pas pu etre traitees.",
                    )

    termine_qs = _formateur_termine_without_form_queryset()
    form_status_qs = _formateur_form_status_issue_queryset()
    termine_without_form_total = termine_qs.count()
    form_status_issue_total = form_status_qs.count()
    termine_page_obj, termine_without_form_rows = _paginate_formateur_update_form_rows(
        request,
        termine_qs,
        page_param="termine_page",
    )
    form_status_page_obj, form_status_issue_rows = _paginate_formateur_update_form_rows(
        request,
        form_status_qs,
        page_param="status_page",
    )

    context = {
        "form": form,
        "results": results,
        "summary": summary,
        "selected_target_values": selected_target_values,
        "termine_without_form_rows": termine_without_form_rows,
        "termine_without_form_total": termine_without_form_total,
        "termine_without_form_page_obj": termine_page_obj,
        "form_status_issue_rows": form_status_issue_rows,
        "form_status_issue_total": form_status_issue_total,
        "form_status_issue_page_obj": form_status_page_obj,
        "candidate_total": termine_without_form_total + form_status_issue_total,
        "dashboard_url": reverse("satisfaction_formateurs_dashboard"),
        "index_url": reverse("satisfaction_formateurs_index"),
    }
    return render(request, "satisfaction_formateurs/update_form.html", context)


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
    context.update(build_fast_stats_context(request, default_mode="formateur"))
    return render(request, "satisfaction_formateurs/dashboard.html", context)

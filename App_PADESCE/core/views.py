import json
import os
from collections import defaultdict
from datetime import date, timedelta
from functools import lru_cache
from types import SimpleNamespace
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Q
from django.http import QueryDict
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin

from App_PADESCE.appels.models import (
    APPEL_ANSWER_QUESTION_FIELDS,
    Appel,
    AppelAnswers,
    AppelCGA,
    AppelFormateur,
    appel_answers_completed_q,
    appel_answers_modified_completion_q,
    padesce_form_tracking_cutoff,
)
from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.core.access import (
    has_analysis_access,
    has_consultant_access,
    require_analysis_access,
    require_consultant_access,
)
from App_PADESCE.core.analysis_rules import (
    analysis_threshold_target,
    appel_is_analysis_eligible,
)
from App_PADESCE.core.call_metrics import has_usable_phone
from App_PADESCE.core.fast_stats import (
    build_fast_stats_api_response,
    build_fast_stats_export_response,
)
from App_PADESCE.core.models import UserActivity
from App_PADESCE.environnement.models import EnqueteEnvironnement
from App_PADESCE.formations.models import Classe
from App_PADESCE.presences.models import Presence
from App_PADESCE.satisfaction_apprenants.models import SatisfactionApprenant
from App_PADESCE.satisfaction_formateurs.models import SatisfactionFormateur


def _normalize_dashboard_fenetre(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text in {"2", "3"}:
        return text
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits if digits in {"2", "3"} else ""


def _group_appel_ids_by_user(queryset, user_field: str) -> dict[int, set[int]]:
    grouped: dict[int, set[int]] = defaultdict(set)
    for row in queryset.values("id", user_field):
        user_id = row.get(user_field)
        if user_id:
            grouped[user_id].add(row["id"])
    return grouped


def _source_class_apprenant_counts(source_bundle: dict | None) -> dict[str, int]:
    from App_PADESCE.core.call_metrics import count_callable_source_records_by_class

    return count_callable_source_records_by_class(source_bundle)


def _consultant_qualified_prestation_codes(source_bundle: dict | None) -> set[str]:
    from App_PADESCE.reporting.network_excel import normalize_network_lookup

    if not source_bundle:
        return set()

    source_classes = list((source_bundle.get("classes") or {}).values())
    if not source_classes:
        return set()

    terminated_by_class = {
        normalize_network_lookup(code): count
        for code, count in (
            Appel.objects.filter(is_active=True, status="termine")
            .exclude(classe_label="")
            .values("classe_label")
            .annotate(total=Count("id"))
            .values_list("classe_label", "total")
        )
    }
    apprenant_counts = {
        normalize_network_lookup(code): count
        for code, count in _source_class_apprenant_counts(source_bundle).items()
    }

    prestation_classes: dict[str, set[str]] = {}
    for source_class in source_classes:
        prestation_key = normalize_network_lookup(source_class.get("prestation_id", ""))
        classe_key = normalize_network_lookup(source_class.get("classe_id", ""))
        if not prestation_key or not classe_key:
            continue
        if int(apprenant_counts.get(classe_key) or 0) <= 0:
            continue
        prestation_classes.setdefault(prestation_key, set()).add(classe_key)

    qualified_codes: set[str] = set()
    for prestation_key, class_keys in prestation_classes.items():
        if not class_keys:
            continue
        all_reached = True
        for class_key in class_keys:
            total_apprenants = int(apprenant_counts.get(class_key) or 0)
            if total_apprenants <= 0:
                all_reached = False
                break
            threshold_count = analysis_threshold_target(total_apprenants)
            total_termines = int(terminated_by_class.get(class_key) or 0)
            if total_termines < threshold_count:
                all_reached = False
                break
        if all_reached:
            qualified_codes.add(prestation_key)
    return qualified_codes


def _consultant_class_display(appel: Appel) -> str:
    classe = getattr(appel, "classe", None)
    classe_code = str(getattr(classe, "code", "") or "").strip()
    classe_intitule = str(getattr(classe, "intitule_formation", "") or "").strip()
    if classe_code and classe_intitule:
        return f"{classe_code} - {classe_intitule}"
    if classe_code:
        return classe_code
    return (getattr(appel, "classe_label", "") or "").strip() or "-"


def _consultant_dashboard_fenetre(appel: Appel) -> str:
    classe = getattr(appel, "classe", None)
    prestation = getattr(classe, "prestation", None) if classe else None
    beneficiaire = getattr(prestation, "beneficiaire", None) if prestation else None
    beneficiaire_type = str(getattr(beneficiaire, "type_structure", "") or "").strip().lower()

    raw_fenetre = (
        str(getattr(appel, "fenetre", "") or "").strip()
        or str(getattr(classe, "fenetre", "") or "").strip()
    )
    normalized = _normalize_dashboard_fenetre(raw_fenetre)
    if normalized in {"2", "3"}:
        return normalized
    if "entreprise" in beneficiaire_type:
        return "2"
    if "association" in beneficiaire_type or "gic" in beneficiaire_type:
        return "3"
    return ""


@lru_cache(maxsize=1)
def _load_conformity_ranking_priorities():
    path = os.path.join(settings.BASE_DIR, "conformity_ranking.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        priorities = {}
        for item in data:
            sugg = item.get("reponses_suggerees_audio")
            if sugg and all(v is not None for v in sugg.values()):
                # Calculate average satisfaction
                vals = [float(v) for v in sugg.values() if v is not None]
                avg = sum(vals) / len(vals) if vals else 0
                priorities[item["code"]] = {
                    "responses": sugg,
                    "avg_satisfaction": avg,
                    "name": item.get("name"),
                }
        return priorities
    except Exception:
        return {}


def _consultant_answers_complete(answers: AppelAnswers | None) -> bool:
    if not answers:
        return False
    return all(getattr(answers, field, None) is not None for field in APPEL_ANSWER_QUESTION_FIELDS)


def _consultant_answer_or_none(appel: Appel):
    try:
        return appel.answers
    except AppelAnswers.DoesNotExist:
        return None


def _consultant_survey_or_none(appel: Appel):
    try:
        return appel.satisfaction_apprenant
    except SatisfactionApprenant.DoesNotExist:
        return None


CONSULTANT_QUESTION_LABELS = (
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


def _consultant_has_phone(appel: Appel) -> bool:
    return has_usable_phone(getattr(appel, "telephone1", ""), getattr(appel, "telephone2", ""))


def _consultant_simulated_answers_payload(appel: Appel) -> dict[str, object]:
    seed = sum(ord(char) for char in f"{appel.pk}:{appel.code}:{appel.nom}")
    profiles = (
        (4, 4, 4, 3, 4, 3, 4, 4, 4),
        (4, 3, 4, 4, 3, 4, 4, 3, 4),
        (3, 4, 3, 4, 4, 3, 4, 4, 4),
    )
    scores = profiles[seed % len(profiles)]
    has_phone = _consultant_has_phone(appel)
    return {
        **{
            field_name: scores[index]
            for index, field_name in enumerate(APPEL_ANSWER_QUESTION_FIELDS)
        },
        "commentaire": (
            "Satisfaction globalement positive, avec quelques points mineurs a consolider."
            if has_phone
            else (
                "Satisfaction estimee positive malgre l'absence de numero "
                "joignable dans le dossier."
            )
        ),
        "recommandations": (
            "Maintenir l'accompagnement, renforcer le suivi pratique et "
            "clarifier les points logistiques."
        ),
    }


def _consultant_display_answers(appel: Appel, answers: AppelAnswers | None) -> tuple[object, bool]:
    priorities = _load_conformity_ranking_priorities()
    if appel.code in priorities:
        p_data = priorities[appel.code]
        # Map JSON keys ('q1', 'q2', etc.) to model fields
        payload = {
            field: p_data["responses"].get(field[:2]) for field in APPEL_ANSWER_QUESTION_FIELDS
        }
        payload["commentaire"] = "Réponses extraites de l'audio par analyse de conformité."
        payload["recommandations"] = "N/A (Calculé via analyse audio)"
        return SimpleNamespace(**payload), False

    if answers and _consultant_answers_complete(answers):
        commentaire = str(getattr(answers, "commentaire", "") or "").strip()
        recommandations = str(getattr(answers, "recommandations", "") or "").strip()
        if commentaire and recommandations:
            return answers, False

    simulated = _consultant_simulated_answers_payload(appel)
    payload = {}
    for field_name in APPEL_ANSWER_QUESTION_FIELDS:
        value = getattr(answers, field_name, None) if answers else None
        payload[field_name] = value if value is not None else simulated[field_name]

    commentaire = str(getattr(answers, "commentaire", "") or "").strip() if answers else ""
    recommandations = str(getattr(answers, "recommandations", "") or "").strip() if answers else ""
    payload["commentaire"] = commentaire or simulated["commentaire"]
    payload["recommandations"] = recommandations or simulated["recommandations"]
    return SimpleNamespace(**payload), True


def _consultant_has_audio(appel: Appel) -> bool:
    audio_file = getattr(appel, "audio_file", None)
    return bool(audio_file and getattr(audio_file, "name", ""))


@lru_cache(maxsize=1024)
def _cached_audio_duration_seconds(audio_path: str) -> float | None:
    if not audio_path:
        return None

    try:
        import av
    except Exception:
        return None

    container = None
    try:
        container = av.open(audio_path)
        duration = getattr(container, "duration", None)
        if duration:
            duration_seconds = float(duration) / 1_000_000.0
            return duration_seconds if duration_seconds > 0 else None

        for stream in getattr(container, "streams", []) or []:
            if getattr(stream, "type", "") != "audio":
                continue
            stream_duration = getattr(stream, "duration", None)
            time_base = getattr(stream, "time_base", None)
            if stream_duration and time_base:
                duration_seconds = float(stream_duration * time_base)
                return duration_seconds if duration_seconds > 0 else None
    except Exception:
        return None
    finally:
        if container is not None:
            try:
                container.close()
            except Exception:
                pass

    return None


def _consultant_audio_duration_seconds(appel: Appel) -> float | None:
    if not _consultant_has_audio(appel):
        return None
    try:
        audio_path = str(appel.audio_file.path)
    except Exception:
        return None
    return _cached_audio_duration_seconds(audio_path)


def _consultant_row_sort_key(appel: Appel) -> tuple:
    return (
        0 if getattr(appel, "consultant_priority", False) else 1,
        0 if getattr(appel, "consultant_has_audio", False) else 1,
        (getattr(appel, "consultant_class_display", "") or "").casefold(),
        (getattr(appel, "nom", "") or "").casefold(),
        getattr(appel, "pk", 0),
    )


def _fallback_consultant_analysis_snapshot(rows: list[Appel]) -> dict:
    class_options = []
    seen_classes: set[str] = set()
    prestataire_options = sorted(
        {(row.prestataire or "").strip() for row in rows if (row.prestataire or "").strip()}
    )
    beneficiaire_options = sorted(
        {(row.beneficiaire or "").strip() for row in rows if (row.beneficiaire or "").strip()}
    )
    fenetre_options = sorted(
        {
            _consultant_dashboard_fenetre(row)
            for row in rows
            if _consultant_dashboard_fenetre(row) in {"2", "3"}
        }
    )
    prestation_codes = sorted(
        {
            str(
                getattr(getattr(getattr(row, "classe", None), "prestation", None), "code", "") or ""
            ).strip()
            for row in rows
            if getattr(getattr(getattr(row, "classe", None), "prestation", None), "code", "")
        }
    )

    for row in rows:
        classe = getattr(row, "classe", None)
        class_code = str(getattr(classe, "code", "") or "").strip()
        class_label = _consultant_class_display(row)
        class_value = class_code or (getattr(row, "classe_label", "") or "").strip()
        if not class_value or not class_label or class_label == "-" or class_value in seen_classes:
            continue
        seen_classes.add(class_value)
        class_options.append({"value": class_value, "label": class_label})

    class_options.sort(key=lambda item: (item["label"] or "").casefold())
    return {
        "class_options": class_options,
        "prestataire_options": prestataire_options,
        "beneficiaire_options": beneficiaire_options,
        "fenetre_options": fenetre_options,
        "counts": {
            "analyzed_classes_count": len(class_options),
            "analyzed_prestations_count": len(prestation_codes),
            "analyzed_prestataires_count": len(prestataire_options),
            "analyzed_beneficiaires_count": len(beneficiaire_options),
            "analysis_audio_count": sum(1 for row in rows if _consultant_has_audio(row)),
            "analyzed_learners_count": len(rows),
            "total_apprenants": len(rows),
        },
    }


def _consultant_analysis_snapshot(
    user, *, classe_filter: str = "", prestataire_filter: str = ""
) -> dict | None:
    try:
        from App_PADESCE.satisfaction_apprenants.views import _build_satisfaction_dashboard_data

        query = QueryDict("", mutable=True)
        query["source"] = "cutoff"
        if classe_filter:
            query["classe"] = classe_filter
        if prestataire_filter:
            query["prestataire"] = prestataire_filter

        payload = _build_satisfaction_dashboard_data(SimpleNamespace(GET=query, user=user))
        context = payload["context"]
        class_options = [
            {
                "value": item["code"],
                "label": f"{item['code']} - {item['intitule']}",
            }
            for item in context["classe_stats"]
            if str(item.get("code") or "").strip()
        ]
        prestataire_options = [
            item["label"]
            for item in context["analyzed_prestataires"]
            if str(item.get("label") or "").strip()
        ]
        beneficiaire_options = [
            item["label"]
            for item in context.get("analyzed_beneficiaires", [])
            if str(item.get("label") or "").strip()
        ]
        fenetre_options = [
            item["label"]
            for item in context.get("analyzed_fenetres", [])
            if str(item.get("label") or "").strip()
        ]
        return {
            "class_options": class_options,
            "prestataire_options": prestataire_options,
            "beneficiaire_options": beneficiaire_options,
            "fenetre_options": fenetre_options,
            "counts": {
                "analyzed_classes_count": context["analyzed_classes_count"],
                "analyzed_prestations_count": context["analyzed_prestations_count"],
                "analyzed_prestataires_count": context["analyzed_prestataires_count"],
                "analyzed_beneficiaires_count": context["analyzed_beneficiaires_count"],
                "analysis_audio_count": context.get("analysis_audio_count", 0),
                "analyzed_learners_count": context["total"],
                "total_apprenants": context["total"],
            },
        }
    except Exception:
        return None


def home(request):
    today = date.today()
    start_date = date(2025, 9, 26)
    end_date = date(2026, 8, 26)
    total_days = (end_date - start_date).days or 1
    elapsed_days = max(0, min((today - start_date).days, total_days))
    progress_pct = round((elapsed_days / total_days) * 100, 1)
    countdown_days = max(0, (end_date - today).days)

    appels_termine_qs = Appel.objects.filter(is_active=True, status="termine")
    prestataire_appels = (
        appels_termine_qs.values("prestataire")
        .annotate(total=Count("id"))
        .order_by("-total", "prestataire")
    )
    padesce_total = Appel.objects.filter(is_active=True).count()
    padesce_effectues = Appel.objects.filter(is_active=True).exclude(status="en_attente").count()
    cga_total = AppelCGA.objects.filter(is_active=True).count()
    cga_effectues = AppelCGA.objects.filter(is_active=True).exclude(status="en_attente").count()
    formateurs_total = AppelFormateur.objects.filter(is_active=True).count()
    formateurs_effectues = (
        AppelFormateur.objects.filter(is_active=True).exclude(status="en_attente").count()
    )

    is_superuser = bool(request.user.is_authenticated and request.user.is_superuser)
    is_cga_manager = bool(
        request.user.is_authenticated and request.user.groups.filter(name="manager_cga").exists()
    )
    is_padesce_manager = bool(
        request.user.is_authenticated
        and request.user.groups.filter(name="manager_padesce").exists()
    )
    is_consultant_only = bool(
        has_consultant_access(request.user)
        and not is_superuser
        and not is_padesce_manager
        and not is_cga_manager
    )
    can_view_call_cards = bool(request.user.is_authenticated and not is_consultant_only)
    can_view_analysis_pages = has_analysis_access(request.user)
    can_view_consultant_space = has_consultant_access(request.user)
    can_view_padesce_dashboard = bool(is_superuser or is_padesce_manager)
    can_view_cga_dashboard = bool(is_superuser or is_cga_manager)

    context = {
        "nb_classes": Classe.objects.count(),
        "nb_apprenants": Apprenant.objects.count(),
        "nb_presence": Presence.objects.count(),
        "nb_sat_apprenants": SatisfactionApprenant.objects.count(),
        "nb_sat_formateurs": SatisfactionFormateur.objects.count(),
        "nb_env": EnqueteEnvironnement.objects.count(),
        "nb_appels_termine": appels_termine_qs.count(),
        "prestataire_appels": prestataire_appels,
        "padesce_total": padesce_total,
        "padesce_effectues": padesce_effectues,
        "cga_total": cga_total,
        "cga_effectues": cga_effectues,
        "formateurs_total": formateurs_total,
        "formateurs_effectues": formateurs_effectues,
        "progress_pct": progress_pct,
        "countdown_days": countdown_days,
        "deadline_iso": end_date.isoformat(),
        "is_superuser_dashboard": is_superuser,
        "can_view_call_cards": can_view_call_cards,
        "can_view_analysis_pages": can_view_analysis_pages,
        "can_view_consultant_space": can_view_consultant_space,
        "is_consultant_only": is_consultant_only,
        "can_view_padesce_dashboard": can_view_padesce_dashboard,
        "can_view_cga_dashboard": can_view_cga_dashboard,
        "stat_cards": [
            {"label": "Classes", "value": Classe.objects.count(), "color": "primary"},
            {"label": "Apprenants", "value": Apprenant.objects.count(), "color": "success"},
            {"label": "Enquêtes présence", "value": Presence.objects.count(), "color": "info"},
            {
                "label": "Sat. apprenants",
                "value": SatisfactionApprenant.objects.count(),
                "color": "warning",
            },
            {
                "label": "Sat. formateurs",
                "value": SatisfactionFormateur.objects.count(),
                "color": "danger",
            },
            {
                "label": "Environnement",
                "value": EnqueteEnvironnement.objects.count(),
                "color": "secondary",
            },
        ],
    }
    if can_view_padesce_dashboard or can_view_cga_dashboard:
        User = get_user_model()
        since_24h = timezone.now() - timedelta(hours=24)
        cutoff = timezone.now() - timedelta(minutes=10)
        user_search = (request.GET.get("user_search") or "").strip()

        if is_superuser:
            activities = {a.user_id: a for a in UserActivity.objects.select_related("user")}
            appels_index_url = reverse("appels_index")
            completed_answers_filter = appel_answers_completed_q("answers__")
            modified_answers_filter = appel_answers_modified_completion_q("answers__")
            form_tracking_cutoff = padesce_form_tracking_cutoff()
            tracked_audio_filter = Q(audio_file__isnull=False) & ~Q(audio_file="")
            call_stats = {
                row["locked_by_id"]: row
                for row in Appel.objects.filter(is_active=True, locked_by__isnull=False)
                .values("locked_by_id")
                .annotate(
                    total_appels=Count("id"),
                    a_rappeler=Count("id", filter=Q(status="a_rappeler")),
                    en_cours=Count("id", filter=Q(status="en_cours")),
                )
            }
            formulaires_remplis_by_user = _group_appel_ids_by_user(
                Appel.objects.filter(is_active=True, locked_by__isnull=False)
                .filter(completed_answers_filter)
                .distinct(),
                "locked_by_id",
            )
            formulaires_modifies_by_user = _group_appel_ids_by_user(
                Appel.objects.filter(is_active=True).filter(modified_answers_filter).distinct(),
                "answers__modified_by_id",
            )
            legacy_termines_by_user = _group_appel_ids_by_user(
                Appel.objects.filter(
                    is_active=True,
                    status="termine",
                    updated_at__lt=form_tracking_cutoff,
                    locked_by__isnull=False,
                ),
                "locked_by_id",
            )
            audio_termines_by_user = _group_appel_ids_by_user(
                Appel.objects.filter(
                    is_active=True,
                    status="termine",
                    updated_at__gte=form_tracking_cutoff,
                    locked_by__isnull=False,
                )
                .filter(tracked_audio_filter)
                .distinct(),
                "locked_by_id",
            )
            current_calls_by_user = {}
            for appel in Appel.objects.filter(
                is_active=True, status="en_cours", locked_by__isnull=False
            ).order_by("locked_by__username", "nom"):
                query_params = urlencode(
                    {"agent": appel.locked_by.username, "status": "en_cours", "q": appel.code}
                )
                current_calls_by_user.setdefault(appel.locked_by_id, []).append(
                    {
                        "code": appel.code,
                        "nom": appel.nom,
                        "url": f"{appels_index_url}?{query_params}",
                    }
                )

            def build_appels_url(**params):
                query = {key: value for key, value in params.items() if value not in (None, "", [])}
                if not query:
                    return appels_index_url
                return f"{appels_index_url}?{urlencode(query, doseq=True)}"

            user_rows = []
            for user in User.objects.all().order_by("username"):
                username = user.get_username()
                if user_search and user_search.lower() not in username.lower():
                    continue
                activity = activities.get(user.id)
                last_seen = activity.last_seen if activity else user.last_login
                is_online = bool(last_seen and last_seen >= cutoff)
                stats_row = call_stats.get(user.id, {})
                formulaires_remplis_ids = formulaires_remplis_by_user.get(user.id, set())
                formulaires_modifies_ids = formulaires_modifies_by_user.get(user.id, set())
                termines_ids = set(legacy_termines_by_user.get(user.id, set()))
                termines_ids.update(formulaires_remplis_ids)
                termines_ids.update(formulaires_modifies_ids)
                termines_ids.update(audio_termines_by_user.get(user.id, set()))
                user_rows.append(
                    {
                        "username": username,
                        "is_online": is_online,
                        "last_seen": last_seen,
                        "last_login": user.last_login,
                        "total_appels": int(stats_row.get("total_appels") or 0),
                        "a_rappeler": int(stats_row.get("a_rappeler") or 0),
                        "formulaires_remplis": len(formulaires_remplis_ids),
                        "formulaires_modifies": len(formulaires_modifies_ids),
                        "termines": len(termines_ids),
                        "en_cours": int(stats_row.get("en_cours") or 0),
                        "current_calls": current_calls_by_user.get(user.id, []),
                        "total_url": build_appels_url(agent=username),
                        "rappel_url": build_appels_url(agent=username, status="a_rappeler"),
                        "formulaires_url": build_appels_url(agent=username, formulaire="rempli"),
                        "modifies_url": build_appels_url(
                            modified_by=username, formulaire="modifie"
                        ),
                        "termines_url": build_appels_url(
                            tracking_termine=1, tracking_user=username
                        ),
                        "en_cours_url": build_appels_url(agent=username, status="en_cours"),
                    }
                )
            user_rows.sort(
                key=lambda row: (
                    -row["termines"],
                    -row["formulaires_remplis"],
                    -row["formulaires_modifies"],
                    row["username"].lower(),
                )
            )
            context["user_activity_rows"] = user_rows
            context["user_search"] = user_search

        if can_view_padesce_dashboard:
            padesce_called_qs = Appel.objects.filter(is_active=True).exclude(status="en_attente")
            padesce_all_qs = Appel.objects.filter(is_active=True)

            # --- KPIs 24h ---
            padesce_24h_qs = Appel.objects.filter(
                is_active=True, status="termine", updated_at__gte=since_24h
            )
            context["kpi_24h_total_termines"] = padesce_24h_qs.count()

            kpi_24h_users = list(
                padesce_24h_qs.filter(locked_by__isnull=False)
                .values("locked_by__username")
                .annotate(termines_24h=Count("id"))
                .order_by("-termines_24h", "locked_by__username")
            )
            for row in kpi_24h_users:
                row["username"] = row.get("locked_by__username") or "Inconnu"
            context["kpi_24h_users"] = kpi_24h_users

            kpi_24h_classe_prestation = list(
                padesce_24h_qs.values("classe_label", "prestataire", "beneficiaire")
                .annotate(termines_24h=Count("id"))
                .order_by("-termines_24h", "classe_label", "prestataire", "beneficiaire")
            )
            for row in kpi_24h_classe_prestation:
                classe = (row.get("classe_label") or "Classe inconnue").strip() or "Classe inconnue"
                prestataire = (
                    row.get("prestataire") or "Sans prestataire"
                ).strip() or "Sans prestataire"
                beneficiaire = (
                    row.get("beneficiaire") or "Sans beneficiaire"
                ).strip() or "Sans beneficiaire"
                row["label"] = f"{classe} {prestataire}-{beneficiaire}"
            context["kpi_24h_classe_prestation"] = kpi_24h_classe_prestation

            kpi_24h_prestation = list(
                padesce_24h_qs.values("prestataire", "beneficiaire")
                .annotate(termines_24h=Count("id"))
                .order_by("-termines_24h", "prestataire", "beneficiaire")
            )
            for row in kpi_24h_prestation:
                prestataire = (
                    row.get("prestataire") or "Sans prestataire"
                ).strip() or "Sans prestataire"
                beneficiaire = (
                    row.get("beneficiaire") or "Sans beneficiaire"
                ).strip() or "Sans beneficiaire"
                row["label"] = f"{prestataire}-{beneficiaire}"
            context["kpi_24h_prestation"] = kpi_24h_prestation
            # -----------------

            padesce_prestataire_ranking = list(
                Appel.objects.filter(is_active=True)
                .values("prestataire")
                .annotate(
                    total_appeles=Count("id", filter=~Q(status="en_attente")),
                    total_termines=Count("id", filter=Q(status="termine")),
                )
                .order_by("-total_termines", "-total_appeles", "prestataire")
            )
            for row in padesce_prestataire_ranking:
                row["prestataire"] = (
                    row.get("prestataire") or "Non renseigne"
                ).strip() or "Non renseigne"
            context["padesce_prestataire_ranking"] = padesce_prestataire_ranking

            prestation_progress_rows = list(
                padesce_all_qs.values("prestataire", "beneficiaire")
                .annotate(
                    total_apprenants=Count("id"),
                    total_appeles=Count("id", filter=~Q(status="en_attente")),
                    total_termines=Count("id", filter=Q(status="termine")),
                )
                .order_by("prestataire", "beneficiaire")
            )
            for row in prestation_progress_rows:
                prestataire = (
                    row.get("prestataire") or "Sans prestataire"
                ).strip() or "Sans prestataire"
                beneficiaire = (
                    row.get("beneficiaire") or "Sans beneficiaire"
                ).strip() or "Sans beneficiaire"
                total = int(row.get("total_apprenants") or 0)
                appeles = int(row.get("total_appeles") or 0)
                restants = max(total - appeles, 0)
                row["prestataire"] = prestataire
                row["beneficiaire"] = beneficiaire
                row["prestation_label"] = f"{prestataire} - {beneficiaire}"
                row["restants"] = restants
                row["is_complete"] = restants == 0
            context["padesce_prestation_progress"] = prestation_progress_rows

            fenetre_counter = {}
            for fenetre_value in (
                padesce_called_qs.exclude(fenetre__isnull=True)
                .exclude(fenetre="")
                .values_list("fenetre", flat=True)
            ):
                normalized = _normalize_dashboard_fenetre(fenetre_value)
                if not normalized:
                    continue
                fenetre_counter[normalized] = fenetre_counter.get(normalized, 0) + 1
            fenetre_rows = [
                {"fenetre": fenetre, "total": total}
                for fenetre, total in sorted(
                    fenetre_counter.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ]
            context["padesce_fenetre_rows"] = fenetre_rows

            padesce_user_ranking = list(
                padesce_called_qs.filter(locked_by__isnull=False)
                .values("locked_by__username")
                .annotate(
                    total_appeles=Count("id"),
                    total_termines=Count("id", filter=Q(status="termine")),
                    recent_24h=Count("id", filter=Q(updated_at__gte=since_24h)),
                )
                .order_by("-total_termines", "-total_appeles", "locked_by__username")
            )
            context["padesce_user_ranking"] = padesce_user_ranking

            prestation_global_rows = list(
                padesce_called_qs.values("classe_label", "prestataire", "beneficiaire")
                .annotate(
                    total_appeles=Count("id"),
                    total_termines=Count("id", filter=Q(status="termine")),
                )
                .order_by(
                    "-total_termines",
                    "-total_appeles",
                    "classe_label",
                    "prestataire",
                    "beneficiaire",
                )
            )
            for row in prestation_global_rows:
                classe = (row.get("classe_label") or "Classe inconnue").strip() or "Classe inconnue"
                prestataire = (
                    row.get("prestataire") or "Sans prestataire"
                ).strip() or "Sans prestataire"
                beneficiaire = (
                    row.get("beneficiaire") or "Sans beneficiaire"
                ).strip() or "Sans beneficiaire"
                row["prestation_label"] = f"{classe} {prestataire}-{beneficiaire}"
            context["padesce_prestation_ranking"] = prestation_global_rows

            prestation_user_rows = list(
                padesce_called_qs.filter(locked_by__isnull=False)
                .values("locked_by__username", "classe_label", "prestataire", "beneficiaire")
                .annotate(
                    total_appeles=Count("id"),
                    total_termines=Count("id", filter=Q(status="termine")),
                )
                .order_by(
                    "-total_termines", "-total_appeles", "locked_by__username", "classe_label"
                )
            )
            for row in prestation_user_rows:
                classe = (row.get("classe_label") or "Classe inconnue").strip() or "Classe inconnue"
                prestataire = (
                    row.get("prestataire") or "Sans prestataire"
                ).strip() or "Sans prestataire"
                beneficiaire = (
                    row.get("beneficiaire") or "Sans beneficiaire"
                ).strip() or "Sans beneficiaire"
                row["prestation_label"] = f"{classe} {prestataire}-{beneficiaire}"
            context["padesce_prestation_user_ranking"] = prestation_user_rows

            formateurs_called_qs = AppelFormateur.objects.filter(is_active=True).exclude(
                status="en_attente"
            )
            formateurs_all_qs = AppelFormateur.objects.filter(is_active=True)

            formateurs_prestataire_ranking = list(
                formateurs_all_qs.values("prestataire")
                .annotate(
                    total_appels=Count("id", filter=~Q(status="en_attente")),
                    total_termines=Count("id", filter=Q(status="termine")),
                )
                .order_by("-total_termines", "-total_appels", "prestataire")
            )
            for row in formateurs_prestataire_ranking:
                row["prestataire"] = (
                    row.get("prestataire") or "Non renseigne"
                ).strip() or "Non renseigne"
            context["formateurs_prestataire_ranking"] = formateurs_prestataire_ranking

            formateurs_cohorte_rows = list(
                formateurs_all_qs.values("cohorte")
                .annotate(
                    total=Count("id"),
                    total_termines=Count("id", filter=Q(status="termine")),
                )
                .order_by("-total", "cohorte")
            )
            for row in formateurs_cohorte_rows:
                row["cohorte"] = (
                    row.get("cohorte") or "Non renseignee"
                ).strip() or "Non renseignee"
            context["formateurs_cohorte_rows"] = formateurs_cohorte_rows

            formateurs_date_rows = list(
                formateurs_called_qs.values("session_date", "date_label")
                .annotate(total=Count("id"))
                .order_by("session_date", "date_label")
            )
            for row in formateurs_date_rows:
                row["date_display"] = (
                    row.get("session_date").isoformat()
                    if row.get("session_date")
                    else ((row.get("date_label") or "Date inconnue").strip() or "Date inconnue")
                )
            context["formateurs_date_rows"] = formateurs_date_rows

            formateurs_user_ranking = list(
                formateurs_called_qs.filter(locked_by__isnull=False)
                .values("locked_by__username")
                .annotate(
                    total_appels=Count("id"),
                    total_termines=Count("id", filter=Q(status="termine")),
                )
                .order_by("-total_termines", "-total_appels", "locked_by__username")
            )
            context["formateurs_user_ranking"] = formateurs_user_ranking

        if can_view_cga_dashboard:
            cga_called_qs = AppelCGA.objects.filter(is_active=True).exclude(status="en_attente")

            cga_regime_ranking = list(
                cga_called_qs.values("regime")
                .annotate(
                    total_appeles=Count("id"),
                    total_termines=Count("id", filter=Q(status="termine")),
                )
                .order_by("-total_termines", "-total_appeles", "regime")
            )
            for row in cga_regime_ranking:
                row["regime"] = (row.get("regime") or "Non renseigne").strip() or "Non renseigne"
            context["cga_regime_ranking"] = cga_regime_ranking

            cga_cri_ranking = list(
                cga_called_qs.values("cri")
                .annotate(
                    total_appeles=Count("id"),
                    total_termines=Count("id", filter=Q(status="termine")),
                )
                .order_by("-total_termines", "-total_appeles", "cri")
            )
            for row in cga_cri_ranking:
                row["cri"] = (row.get("cri") or "Non renseigne").strip() or "Non renseigne"
            context["cga_cri_ranking"] = cga_cri_ranking

            cga_centre_ranking = list(
                cga_called_qs.values("centre_de_rattachement")
                .annotate(
                    total_appeles=Count("id"),
                    total_termines=Count("id", filter=Q(status="termine")),
                )
                .order_by("-total_termines", "-total_appeles", "centre_de_rattachement")
            )
            for row in cga_centre_ranking:
                row["centre_de_rattachement"] = (
                    row.get("centre_de_rattachement") or "Non renseigne"
                ).strip() or "Non renseigne"
            context["cga_centre_ranking"] = cga_centre_ranking

            cga_user_ranking = list(
                cga_called_qs.filter(locked_by__isnull=False)
                .values("locked_by__username")
                .annotate(
                    total_appeles=Count("id"),
                    total_termines=Count("id", filter=Q(status="termine")),
                )
                .order_by("-total_termines", "-total_appeles", "locked_by__username")
            )
            context["cga_user_ranking"] = cga_user_ranking
    return render(request, "home.html", context)


def operator_guide(request):
    return render(request, "guide_operateur.html")


@require_analysis_access
def fast_stats_export_xlsx(request):
    return build_fast_stats_export_response(request)


@require_analysis_access
def fast_stats_api(request):
    return build_fast_stats_api_response(request)


@require_consultant_access
def consultant_dashboard(request):
    search = (request.GET.get("q") or "").strip()
    classe_filter = (request.GET.get("classe") or "").strip()
    prestation_filter = (request.GET.get("prestation") or "").strip()
    beneficiaire_filter = (request.GET.get("beneficiaire") or "").strip()
    fenetre_filter = (request.GET.get("fenetre") or "").strip()
    status_filter = (request.GET.get("status") or "").strip()

    _terminal_statuses = ["appel_tente", "appel_reussi", "formulaire_rempli", "formulaire_avec_audio"]
    rows_qs = Appel.objects.filter(is_active=True, status__in=_terminal_statuses).select_related(
        "classe",
        "classe__prestation__beneficiaire",
        "classe__prestation__prestataire",
        "answers",
        "answers__modified_by",
        "satisfaction_apprenant",
        "satisfaction_apprenant__enqueteur",
    )
    if search:
        rows_qs = rows_qs.filter(
            Q(nom__icontains=search)
            | Q(code__icontains=search)
            | Q(telephone1__icontains=search)
            | Q(telephone2__icontains=search)
            | Q(classe_label__icontains=search)
            | Q(prestataire__icontains=search)
            | Q(beneficiaire__icontains=search)
        )
    if classe_filter:
        rows_qs = rows_qs.filter(
            Q(classe__code__iexact=classe_filter) | Q(classe_label__icontains=classe_filter)
        )
    if prestation_filter:
        rows_qs = rows_qs.filter(prestataire__iexact=prestation_filter)
    if beneficiaire_filter:
        rows_qs = rows_qs.filter(beneficiaire__iexact=beneficiaire_filter)
    if status_filter:
        rows_qs = rows_qs.filter(status=status_filter)

    priorities = _load_conformity_ranking_priorities()
    rows: list[Appel] = []
    for app in rows_qs:
        fenetre = _consultant_dashboard_fenetre(app)
        if fenetre not in {"2", "3"}:
            continue
        if fenetre_filter and fenetre != fenetre_filter:
            continue
        answers = _consultant_answer_or_none(app)
        survey = _consultant_survey_or_none(app)
        if not appel_is_analysis_eligible(app, answer=answers, survey=survey):
            continue

        has_audio = _consultant_has_audio(app)
        audio_duration = _consultant_audio_duration_seconds(app) if has_audio else None
        answers_complete = _consultant_answers_complete(answers)

        app.consultant_class_display = _consultant_class_display(app)
        app.consultant_has_audio = has_audio
        app.consultant_audio_duration = audio_duration or 0
        app.consultant_has_form = answers_complete
        app.consultant_priority = bool(has_audio and answers_complete and (audio_duration or 0) >= 60)
        
        # Descriptive status display
        status_display = app.get_status_display()
        if getattr(app, 'flag_pas_forme', False):
            status_display = "Pas formé"
        elif getattr(app, 'flag_faux_nom', False):
            status_display = "Faux nom"
        elif getattr(app, 'flag_numero_double', False):
            status_display = "Numéro double"
        elif getattr(app, 'deja_forme', False):
            status_display = "Déjà formé"
        elif answers:
            if not answers_complete:
                status_display = "Formulaire incomplet"
            elif (getattr(answers, 'commentaire', '') or 'RAS').strip().upper() == "RAS":
                status_display = "Formulaire RAS"
            else:
                status_display = "Formulaire rempli"
        app.consultant_status_display = status_display

        if app.code in priorities:
            app.priority_avg = priorities[app.code]["avg_satisfaction"]
        rows.append(app)

    rows.sort(key=_consultant_row_sort_key)

    # Unfiltered snapshot for card counts (must match satisfaction analysis page)
    _all_eligible_qs = (
        Appel.objects.filter(is_active=True, status__in=_terminal_statuses)
        .select_related(
            "classe",
            "classe__prestation__beneficiaire",
            "classe__prestation__prestataire",
            "answers",
            "answers__modified_by",
            "satisfaction_apprenant",
            "satisfaction_apprenant__enqueteur",
        )
        .order_by("nom", "pk")
    )
    _all_eligible = [
        app for app in _all_eligible_qs
        if _consultant_dashboard_fenetre(app) in {"2", "3"}
        and appel_is_analysis_eligible(
            app,
            answer=_consultant_answer_or_none(app),
            survey=_consultant_survey_or_none(app),
        )
    ]

    card_snapshot = _consultant_analysis_snapshot(
        getattr(request, "user", None)
    ) or _fallback_consultant_analysis_snapshot(_all_eligible)

    analysis_snapshot = _fallback_consultant_analysis_snapshot(_all_eligible)

    # Build filter_map for dynamic JS cascading
    _status_label_map = dict(Appel.STATUS_CHOICES)
    _filter_rows = []
    for app in _all_eligible:
        fenetre = _consultant_dashboard_fenetre(app)
        classe = getattr(app, "classe", None)
        class_code = str(getattr(classe, "code", "") or "").strip() or (app.classe_label or "").strip()
        class_label = _consultant_class_display(app)
        _filter_rows.append({
            "beneficiaire": (app.beneficiaire or "").strip(),
            "prestataire": (app.prestataire or "").strip(),
            "classe_value": class_code,
            "classe_label": class_label if class_label != "-" else class_code,
            "fenetre": fenetre,
            "status": app.status or "",
            "status_label": _status_label_map.get(app.status, app.status or ""),
        })
    filter_map_json = json.dumps(_filter_rows, ensure_ascii=False)

    # Strict form counting: q1-q9 must all be non-null.
    # AppelAnswers fields are nullable so check each individually.
    # SatisfactionApprenant fields are non-nullable — existence of the related
    # record is sufficient (avoids Django 6.x ValueError on non-nullable
    # integer fields used with __isnull via a LEFT JOIN).
    q_fields = [
        "q1_clarte_exposes", "q2_interaction_formateur", "q3_maitrise_contenu",
        "q4_salle_adequate", "q5_materiel_disponible", "q6_organisation_temps",
        "q7_utilite_formation", "q8_adequation_besoins", "q9_satisfaction_globale"
    ]
    answers_valid_q = Q()
    for f in q_fields:
        answers_valid_q &= Q(**{f"answers__{f}__isnull": False})

    survey_valid_q = Q(satisfaction_apprenant__isnull=False)

    strict_form_q = answers_valid_q | survey_valid_q

    tentes = reussis = form_remplis = form_audio = audios_enregistres = 0
    target_class_codes = [opt["value"] for opt in card_snapshot["class_options"] if opt["value"]]
    if target_class_codes:
        base_qs = Appel.objects.filter(is_active=True).filter(
            Q(classe__code__in=target_class_codes) | Q(classe_label__in=target_class_codes)
        )
        stats = base_qs.aggregate(
            tentes=Count("id", filter=Q(status__in=["appel_tente", "appel_reussi", "formulaire_rempli", "formulaire_avec_audio"])),
            reussis=Count("id", filter=Q(status__in=["appel_reussi", "formulaire_rempli", "formulaire_avec_audio"])),
            forms=Count("id", filter=strict_form_q),
            forms_audio=Count("id", filter=strict_form_q & (Q(audio_file__isnull=False) & ~Q(audio_file=""))),
            audios=Count("id", filter=Q(audio_file__isnull=False) & ~Q(audio_file=""))
        )
        tentes = stats["tentes"] or 0
        reussis = stats["reussis"] or 0
        form_remplis = stats["forms"] or 0
        form_audio = stats["forms_audio"] or 0
        audios_enregistres = stats["audios"] or 0

        # Optional: refine the count using actual form validation, but database query is much faster for a dashboard.

    paginator = Paginator(rows, 25)
    page_number = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    return render(
        request,
        "consultant/dashboard.html",
        {
            "rows": list(page_obj.object_list),
            "page_obj": page_obj,
            "paginator": paginator,
            "filters": {
                "q": search,
                "classe": classe_filter,
                "prestation": prestation_filter,
                "beneficiaire": beneficiaire_filter,
                "fenetre": fenetre_filter,
                "status": status_filter,
                "classes": analysis_snapshot["class_options"],
                "prestataires": analysis_snapshot["prestataire_options"],
                "beneficiaires": analysis_snapshot.get("beneficiaire_options", []),
                "fenetres": analysis_snapshot.get("fenetre_options", []),
            },
            "filter_map_json": filter_map_json,
            "total_rows": len(rows),
            "card_prestations_count": card_snapshot["counts"].get("analyzed_prestations_count", 0),
            "card_classes_count": card_snapshot["counts"].get("analyzed_classes_count", 0),
            "card_prestataires_count": card_snapshot["counts"].get("analyzed_prestataires_count", 0),
            "card_beneficiaires_count": card_snapshot["counts"].get("analyzed_beneficiaires_count", 0),
            "card_apprenants_count": card_snapshot["counts"].get("analyzed_learners_count", 0),
            "card_audio_count": card_snapshot["counts"].get("analysis_audio_count", 0),
            "card_fenetres": card_snapshot["fenetre_options"],
            "summary_tentes": tentes,
            "summary_reussis": reussis,
            "summary_form_remplis": form_remplis,
            "summary_form_audio": form_audio,
            "summary_audios": audios_enregistres,
        },
    )


@xframe_options_sameorigin
@require_consultant_access
def consultant_call_detail(request, pk: int):
    appel = get_object_or_404(
        Appel.objects.select_related("classe", "locked_by", "answers"),
        pk=pk,
        is_active=True,
        status="termine",
    )
    try:
        answers = appel.answers
    except AppelAnswers.DoesNotExist:
        answers = None
    display_answers, consultant_answers_simulated = _consultant_display_answers(appel, answers)
    question_rows = [
        (label, getattr(display_answers, field_name, None))
        for label, field_name in CONSULTANT_QUESTION_LABELS
    ]
    has_audio = bool(getattr(appel, "audio_file", None) and getattr(appel.audio_file, "name", ""))
    try:
        audio_url = appel.audio_file.url if has_audio else ""
    except Exception:
        audio_url = ""
        has_audio = False
    modal_mode = (
        request.GET.get("modal") == "1"
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )
    return render(
        request,
        (
            "consultant/partials/call_detail_content.html"
            if modal_mode
            else "consultant/call_detail.html"
        ),
        {
            "appel": appel,
            "answers": display_answers,
            "consultant_answers_simulated": consultant_answers_simulated,
            "question_rows": question_rows,
            "has_audio": has_audio,
            "audio_url": audio_url,
            "filled_questions_count": sum(1 for _label, value in question_rows if value),
        },
    )

from __future__ import annotations

from django.core.exceptions import FieldDoesNotExist
from django.db.models import Q, QuerySet

from App_PADESCE.appels.models import Appel, AppelFormateur
from App_PADESCE.formations.models import Classe, Formateur

PHASE_SCOPE_V1 = "v1"
PHASE_SCOPE_V1_POST = "v1_post"
PHASE_SCOPE_V1_COMBINED = "v1_combined"

PHASE_SCOPE_CHOICES = [
    (PHASE_SCOPE_V1, "Vague 1"),
    (PHASE_SCOPE_V1_POST, "Vague 1 (POST)"),
    (PHASE_SCOPE_V1_COMBINED, "Vague 1 (COMBINÉ)"),
]


def normalize_phase_scope(value: str | None, default: str = PHASE_SCOPE_V1) -> str:
    raw = str(value or "").strip().lower()
    allowed = {item[0] for item in PHASE_SCOPE_CHOICES}
    return raw if raw in allowed else default


def phase_ids_for_scope(scope: str) -> tuple[int, ...]:
    if scope == PHASE_SCOPE_V1:
        return (1,)
    if scope == PHASE_SCOPE_V1_POST:
        return (2,)
    if scope == PHASE_SCOPE_V1_COMBINED:
        return (1, 2)
    return (1,)


def phase_scope_options(selected_scope: str) -> list[dict[str, str]]:
    selected = normalize_phase_scope(selected_scope)
    return [
        {"value": value, "label": label, "selected": value == selected}
        for value, label in PHASE_SCOPE_CHOICES
    ]


def filter_appel_queryset_by_phase(queryset: QuerySet[Appel], scope: str) -> QuerySet[Appel]:
    phase_ids = phase_ids_for_scope(scope)
    class_codes = list(
        Classe.objects.filter(phase_id__in=phase_ids).exclude(code="").values_list("code", flat=True)
    )
    model = queryset.model
    try:
        model._meta.get_field("classe")
        classe_lookup = "classe"
        classe_label_lookup = "classe_label"
    except FieldDoesNotExist:
        try:
            # Some querysets (e.g. AppelAnswers) relate to Appel through `appel`.
            model._meta.get_field("appel")
            classe_lookup = "appel__classe"
            classe_label_lookup = "appel__classe_label"
        except FieldDoesNotExist:
            # Fallback safety: do not crash pages if queryset has no Appel-compatible path.
            return queryset

    p_app_prefix = "code" if classe_lookup == "classe" else "appel__code"
    return queryset.filter(
        Q(**{f"{classe_lookup}__phase_id__in": phase_ids})
        | Q(**{f"{classe_lookup}__isnull": True, f"{classe_label_lookup}__in": class_codes})
        | Q(**{f"{p_app_prefix}__startswith": "P-APP"})
        | Q(**{f"{classe_lookup}__phase_id__isnull": True, f"{classe_lookup}__isnull": False})
    )


def filter_appelformateur_queryset_by_phase(
    queryset: QuerySet[AppelFormateur], scope: str
) -> QuerySet[AppelFormateur]:
    phase_ids = phase_ids_for_scope(scope)
    phones = list(
        Formateur.objects.filter(phase_id__in=phase_ids)
        .exclude(telephone__isnull=True)
        .exclude(telephone="")
        .values_list("telephone", flat=True)
    )
    return queryset.filter(telephone__in=phones)

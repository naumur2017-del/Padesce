from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from django.db import connection, transaction

from App_PADESCE.appels.models import Appel
from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.formations.models import (
    Beneficiaire,
    Classe,
    Formation,
    Inspecteur,
    Lieu,
    Prestataire,
    Prestation,
)
from App_PADESCE.reporting.network_excel import build_padesce_source_index, normalize_network_lookup
from App_PADESCE.satisfaction_apprenants.management.commands.import_satisfaction_excel import (
    _clean_text,
    _reference_cache,
    _sync_source_models,
)
from App_PADESCE.satisfaction_apprenants.models import SatisfactionApprenant


def _related_or_none(instance, attr_name: str):
    try:
        return getattr(instance, attr_name)
    except ObjectDoesNotExist:
        return None


def _empty_sync_summary(source_key: str) -> dict:
    return {
        "source_key": source_key,
        "source_records": 0,
        "null_pk_rows_deleted": 0,
        "synced_apprenants": 0,
        "synced_classes": 0,
        "synced_prestations": 0,
        "synced_formations": 0,
        "synced_prestataires": 0,
        "synced_beneficiaires": 0,
        "synced_lieux": 0,
        "synced_inspecteurs": 0,
        "appels_updated": 0,
        "appels_deactivated": 0,
        "surveys_linked": 0,
        "apprenants_deactivated": 0,
        "classes_deactivated": 0,
        "prestations_deactivated": 0,
        "formations_deactivated": 0,
        "prestataires_deactivated": 0,
        "beneficiaires_deactivated": 0,
        "lieux_deactivated": 0,
        "inspecteurs_deactivated": 0,
        "dry_run": False,
    }


def _purge_null_pk_rows() -> int:
    deleted_total = 0
    models = (
        Apprenant,
        Classe,
        Prestation,
        Formation,
        Prestataire,
        Beneficiaire,
        Lieu,
        Inspecteur,
    )
    with connection.cursor() as cursor:
        for model in models:
            table_name = connection.ops.quote_name(model._meta.db_table)
            cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE id IS NULL")
            row = cursor.fetchone()
            row_count = int((row or [0])[0] or 0)
            if not row_count:
                continue
            cursor.execute(f"DELETE FROM {table_name} WHERE id IS NULL")
            deleted_total += row_count
    return deleted_total


def _register_touched_entities(synced: dict, touched: dict[str, set[int]]) -> None:
    key_map = {
        "formation": "formations",
        "prestataire": "prestataires",
        "beneficiaire": "beneficiaires",
        "lieu": "lieux",
        "prestation": "prestations",
        "classe": "classes",
        "inspecteur": "inspecteurs",
        "apprenant": "apprenants",
    }
    for key in (
        "formation",
        "prestataire",
        "beneficiaire",
        "lieu",
        "prestation",
        "classe",
        "inspecteur",
        "apprenant",
    ):
        instance = synced.get(key)
        if instance and getattr(instance, "pk", None):
            touched[key_map[key]].add(instance.pk)


def _update_appels_from_source(
    *,
    source_records_by_call_code: dict[str, dict],
    reference_cache: dict[str, dict],
) -> dict[str, int]:
    update_fields = [
        "classe",
        "classe_label",
        "prestataire",
        "beneficiaire",
        "formation_padesce",
        "fenetre",
        "lieu",
        "nom",
        "is_active",
    ]
    survey_update_fields = ["classe", "apprenant"]
    appels_to_update: list[Appel] = []
    surveys_to_update: list[SatisfactionApprenant] = []
    summary = {
        "appels_updated": 0,
        "appels_deactivated": 0,
        "surveys_linked": 0,
    }

    for appel in Appel.objects.select_related("classe").all():
        source_record = source_records_by_call_code.get(normalize_network_lookup(appel.code))
        if source_record is None:
            if appel.is_active:
                appel.is_active = False
                appels_to_update.append(appel)
                summary["appels_deactivated"] += 1
            continue

        synced = _sync_source_models(source_record, reference_cache)
        classe = synced.get("classe")
        apprenant = synced.get("apprenant")
        changed = False

        source_classe_code = _clean_text(source_record.get("classe_id") or "")
        source_prestataire = _clean_text(source_record.get("prestataire") or "")
        source_beneficiaire = _clean_text(source_record.get("beneficiaire") or "")
        source_formation = _clean_text(source_record.get("formation") or "")
        source_fenetre = _clean_text(source_record.get("fenetre") or "")
        source_lieu = _clean_text(source_record.get("lieu") or "")
        source_nom = _clean_text(source_record.get("nom_individu") or "")

        if classe and appel.classe_id != classe.pk:
            appel.classe = classe
            changed = True
        if source_classe_code and appel.classe_label != source_classe_code:
            appel.classe_label = source_classe_code
            changed = True
        if source_prestataire and appel.prestataire != source_prestataire:
            appel.prestataire = source_prestataire
            changed = True
        if source_beneficiaire and appel.beneficiaire != source_beneficiaire:
            appel.beneficiaire = source_beneficiaire
            changed = True
        if source_formation and appel.formation_padesce != source_formation:
            appel.formation_padesce = source_formation
            changed = True
        if source_fenetre and appel.fenetre != source_fenetre:
            appel.fenetre = source_fenetre
            changed = True
        if source_lieu and appel.lieu != source_lieu:
            appel.lieu = source_lieu
            changed = True
        if source_nom and appel.nom != source_nom:
            appel.nom = source_nom
            changed = True
        if not appel.is_active:
            appel.is_active = True
            changed = True

        if changed:
            appels_to_update.append(appel)
            summary["appels_updated"] += 1

        survey = _related_or_none(appel, "satisfaction_apprenant")
        survey_changed = False
        if survey is not None and classe and survey.classe_id != classe.pk:
            survey.classe = classe
            survey_changed = True
        if survey is not None and apprenant and survey.apprenant_id != apprenant.pk:
            survey.apprenant = apprenant
            survey_changed = True
        if survey is not None and survey_changed:
            surveys_to_update.append(survey)
            summary["surveys_linked"] += 1

    if appels_to_update:
        Appel.objects.bulk_update(appels_to_update, update_fields, batch_size=500)
    if surveys_to_update:
        SatisfactionApprenant.objects.bulk_update(
            surveys_to_update, survey_update_fields, batch_size=500
        )
    return summary


def _deactivate_missing_entities(touched: dict[str, set[int]]) -> dict[str, int]:
    specs = [
        ("apprenants_deactivated", Apprenant, touched["apprenants"]),
        ("classes_deactivated", Classe, touched["classes"]),
        ("prestations_deactivated", Prestation, touched["prestations"]),
        ("formations_deactivated", Formation, touched["formations"]),
        ("prestataires_deactivated", Prestataire, touched["prestataires"]),
        ("beneficiaires_deactivated", Beneficiaire, touched["beneficiaires"]),
        ("lieux_deactivated", Lieu, touched["lieux"]),
        ("inspecteurs_deactivated", Inspecteur, touched["inspecteurs"]),
    ]
    summary: dict[str, int] = {}
    for key, model, touched_ids in specs:
        if touched_ids:
            summary[key] = (
                model.objects.filter(actif=True).exclude(pk__in=touched_ids).update(actif=False)
            )
        else:
            summary[key] = 0
    return summary


def sync_cutoff_reference_data(
    *,
    source_key: str = "cutoff",
    sync_appels: bool = True,
    deactivate_missing: bool = True,
    dry_run: bool = False,
) -> dict:
    source_bundle = build_padesce_source_index(source_key=source_key)
    source_records = list((source_bundle or {}).get("records", {}).values())
    if not source_records:
        raise ValueError(f"Aucun apprenant exploitable trouve dans la source '{source_key}'.")

    summary = _empty_sync_summary(source_key)
    summary["source_records"] = len(source_records)
    summary["dry_run"] = dry_run
    reference_cache = _reference_cache()
    touched = {
        "formations": set(),
        "prestataires": set(),
        "beneficiaires": set(),
        "lieux": set(),
        "prestations": set(),
        "classes": set(),
        "inspecteurs": set(),
        "apprenants": set(),
    }
    source_records_by_call_code = {
        normalize_network_lookup(record.get("code")): record for record in source_records
    }

    with transaction.atomic():
        summary["null_pk_rows_deleted"] = _purge_null_pk_rows()
        for source_record in source_records:
            synced = _sync_source_models(source_record, reference_cache)
            _register_touched_entities(synced, touched)

        summary["synced_formations"] = len(touched["formations"])
        summary["synced_prestataires"] = len(touched["prestataires"])
        summary["synced_beneficiaires"] = len(touched["beneficiaires"])
        summary["synced_lieux"] = len(touched["lieux"])
        summary["synced_prestations"] = len(touched["prestations"])
        summary["synced_classes"] = len(touched["classes"])
        summary["synced_inspecteurs"] = len(touched["inspecteurs"])
        summary["synced_apprenants"] = len(touched["apprenants"])

        if sync_appels:
            summary.update(
                _update_appels_from_source(
                    source_records_by_call_code=source_records_by_call_code,
                    reference_cache=reference_cache,
                )
            )

        if deactivate_missing:
            summary.update(_deactivate_missing_entities(touched))

        if dry_run:
            transaction.set_rollback(True)

    return summary

"""
Migrates existing Appel statuses to the new status vocabulary:
  en_cours / pause / a_rappeler → appel_tente
  termine + has_audio + has_form  → formulaire_avec_audio
  termine + has_form              → formulaire_rempli
  termine                        → appel_reussi
Also migrates AppelFormateur and AppelCGA with same mapping (form presence
checked via score fields for formateur, N/A for CGA → always appel_reussi).
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from App_PADESCE.appels.models import (
    Appel,
    AppelAnswers,
    AppelCGA,
    AppelFormateur,
    APPEL_ANSWER_QUESTION_FIELDS,
)


def _appel_has_form(appel: Appel) -> bool:
    try:
        answers = appel.answers
    except AppelAnswers.DoesNotExist:
        answers = None
    if answers:
        if any(getattr(answers, f, None) is not None for f in APPEL_ANSWER_QUESTION_FIELDS):
            return True
    # Check SatisfactionApprenant
    try:
        sat = appel.satisfaction_apprenant
        if sat and any(getattr(sat, f, None) is not None for f in APPEL_ANSWER_QUESTION_FIELDS):
            return True
    except Exception:
        pass
    return False


def _appel_has_audio(appel: Appel) -> bool:
    name = getattr(getattr(appel, "audio_file", None), "name", "") or ""
    if name:
        return True
    try:
        sat = appel.satisfaction_apprenant
        if sat:
            audio = getattr(sat, "audio_appel", None)
            if audio and getattr(audio, "name", ""):
                return True
    except Exception:
        pass
    return False


def _formateur_has_form(row: AppelFormateur) -> bool:
    return bool(
        getattr(row, "q1_prerequis_apprenants", None) is not None
        or getattr(row, "q2_interaction_apprenants", None) is not None
        or getattr(row, "q3_competences_acquises", None) is not None
        or str(getattr(row, "q4_gestion_administrative", "") or "").strip()
        or str(getattr(row, "q5_gestion_financiere", "") or "").strip()
        or str(getattr(row, "q6_communication", "") or "").strip()
    )


def _formateur_has_audio(row: AppelFormateur) -> bool:
    return bool(getattr(getattr(row, "audio_file", None), "name", "") or "")


LEGACY_TO_TENTE = {"en_cours", "pause", "a_rappeler"}


class Command(BaseCommand):
    help = "Migrate existing call statuses to new vocabulary"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without saving",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        self.stdout.write("=== Migration des statuts d'appels ===")
        if dry_run:
            self.stdout.write(self.style.WARNING("Mode dry-run: aucune modification ne sera sauvegardée."))

        # ── Appel (apprenants) ──────────────────────────────────────────────
        self.stdout.write("\n--- Appels apprenants ---")
        appels = list(
            Appel.objects.filter(
                status__in=["en_cours", "pause", "a_rappeler", "termine"]
            )
            .select_related("answers", "satisfaction_apprenant")
        )
        appel_counts = {"appel_tente": 0, "appel_reussi": 0, "formulaire_rempli": 0, "formulaire_avec_audio": 0}
        appels_to_update = []
        for appel in appels:
            old_status = appel.status
            if old_status in LEGACY_TO_TENTE:
                new_status = "appel_tente"
            else:  # "termine"
                has_form = _appel_has_form(appel)
                has_audio = _appel_has_audio(appel)
                if has_form and has_audio:
                    new_status = "formulaire_avec_audio"
                elif has_form:
                    new_status = "formulaire_rempli"
                else:
                    new_status = "appel_reussi"
            appel_counts[new_status] = appel_counts.get(new_status, 0) + 1
            if not dry_run:
                appel.status = new_status
                appels_to_update.append(appel)

        if not dry_run and appels_to_update:
            with transaction.atomic():
                Appel.objects.bulk_update(appels_to_update, ["status"])

        for status, count in appel_counts.items():
            self.stdout.write(f"  -> {status}: {count}")

        # ── AppelFormateur ──────────────────────────────────────────────────
        self.stdout.write("\n--- Appels formateurs ---")
        formateurs = list(
            AppelFormateur.objects.filter(
                status__in=["en_cours", "pause", "a_rappeler", "termine"]
            )
        )
        form_counts = {"appel_tente": 0, "appel_reussi": 0, "formulaire_rempli": 0, "formulaire_avec_audio": 0}
        formateurs_to_update = []
        for row in formateurs:
            old_status = row.status
            if old_status in LEGACY_TO_TENTE:
                new_status = "appel_tente"
            else:
                has_form = _formateur_has_form(row)
                has_audio = _formateur_has_audio(row)
                if has_form and has_audio:
                    new_status = "formulaire_avec_audio"
                elif has_form:
                    new_status = "formulaire_rempli"
                else:
                    new_status = "appel_reussi"
            form_counts[new_status] = form_counts.get(new_status, 0) + 1
            if not dry_run:
                row.status = new_status
                formateurs_to_update.append(row)

        if not dry_run and formateurs_to_update:
            with transaction.atomic():
                AppelFormateur.objects.bulk_update(formateurs_to_update, ["status"])

        for status, count in form_counts.items():
            self.stdout.write(f"  -> {status}: {count}")

        # ── AppelCGA ────────────────────────────────────────────────────────
        self.stdout.write("\n--- Appels CGA ---")
        cgas = list(
            AppelCGA.objects.filter(
                status__in=["en_cours", "pause", "a_rappeler", "termine"]
            )
        )
        cga_counts = {"appel_tente": 0, "appel_reussi": 0}
        cgas_to_update = []
        for row in cgas:
            if row.status in LEGACY_TO_TENTE:
                new_status = "appel_tente"
            else:
                has_audio = bool(getattr(getattr(row, "audio_file", None), "name", "") or "")
                new_status = "formulaire_avec_audio" if has_audio else "appel_reussi"
            cga_counts[new_status] = cga_counts.get(new_status, 0) + 1
            if not dry_run:
                row.status = new_status
                cgas_to_update.append(row)

        if not dry_run and cgas_to_update:
            with transaction.atomic():
                AppelCGA.objects.bulk_update(cgas_to_update, ["status"])

        for status, count in cga_counts.items():
            self.stdout.write(f"  -> {status}: {count}")

        self.stdout.write(self.style.SUCCESS("\n=== Migration terminee ==="))

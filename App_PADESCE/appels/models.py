import datetime

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from django.utils import timezone
from django.utils.text import slugify

from App_PADESCE.core.models import TimeStampedModel
from App_PADESCE.formations.models import Classe


APPEL_ANSWER_QUESTION_FIELDS = (
    "q1_clarte_exposes",
    "q2_interaction_formateur",
    "q3_maitrise_contenu",
    "q4_salle_adequate",
    "q5_materiel_disponible",
    "q6_organisation_temps",
    "q7_utilite_formation",
    "q8_adequation_besoins",
    "q9_satisfaction_globale",
)

PADESCE_FORM_TRACKING_CUTOFF = datetime.datetime(2026, 3, 9, 0, 0, 0)
CALL_TENTATIVE_STATUSES = ("appel_tente", "en_cours", "pause")
CALL_COMPLETED_STATUSES = ("appel_reussi", "formulaire_rempli", "formulaire_avec_audio", "termine")


def appel_answers_completed_q(prefix: str = "answers__") -> Q:
    lookup_prefix = prefix or ""
    query = Q()
    for field in APPEL_ANSWER_QUESTION_FIELDS:
        query &= Q(**{f"{lookup_prefix}{field}__isnull": False})
    return query


def appel_answers_has_any_answer_q(prefix: str = "answers__") -> Q:
    lookup_prefix = prefix or ""
    query = Q()
    for field in APPEL_ANSWER_QUESTION_FIELDS:
        query |= Q(**{f"{lookup_prefix}{field}__isnull": False})
    return query


def appel_answers_modified_completion_q(prefix: str = "answers__") -> Q:
    lookup_prefix = prefix or ""
    query = appel_answers_completed_q(prefix)
    query &= Q(**{f"{lookup_prefix}modified_by__isnull": False})
    query &= Q(**{f"{lookup_prefix}modified_at__gt": F(f"{lookup_prefix}created_at")})
    return query


def appel_answers_modified_any_answer_q(prefix: str = "answers__") -> Q:
    lookup_prefix = prefix or ""
    query = appel_answers_has_any_answer_q(prefix)
    query &= Q(**{f"{lookup_prefix}modified_by__isnull": False})
    query &= Q(**{f"{lookup_prefix}modified_at__gt": F(f"{lookup_prefix}created_at")})
    return query


def padesce_form_tracking_cutoff():
    return timezone.make_aware(PADESCE_FORM_TRACKING_CUTOFF, timezone.get_current_timezone())


def _short_slug(value: str, default: str, max_len: int = 36) -> str:
    slug = slugify(value) or default
    return slug[:max_len].strip("-") or default


def appel_audio_upload(instance: "Appel", filename: str) -> str:
    now = timezone.now()
    ts = now.strftime("%Y%m%d_%H%M%S")
    nom_slug = _short_slug(instance.nom, "apprenant", max_len=24)
    beneficiaire_slug = _short_slug(instance.beneficiaire, "beneficiaire", max_len=20)
    prestataire_slug = _short_slug(instance.prestataire, "prestataire", max_len=20)
    cohorte_slug = _short_slug(instance.classe_label or instance.fenetre, "cohorte", max_len=16)
    code_slug = _short_slug(instance.code, "code", max_len=12)
    ext = filename.split(".")[-1] if "." in filename else "mp3"
    return f"padesce/{now:%Y}/{now:%m}/{now:%d}/{prestataire_slug}-{beneficiaire_slug}/{code_slug}-{nom_slug}-{cohorte_slug}-{ts}.{ext}"


def answers_have_any_answer(answers) -> bool:
    return bool(answers and any(getattr(answers, field, None) is not None for field in APPEL_ANSWER_QUESTION_FIELDS))


def satisfaction_has_any_answer(satisfaction) -> bool:
    return bool(
        satisfaction and any(getattr(satisfaction, field, None) is not None for field in APPEL_ANSWER_QUESTION_FIELDS)
    )


def appel_has_any_form_data(appel: "Appel") -> bool:
    try:
        answers = appel.answers
    except Exception:
        answers = None
    if answers_have_any_answer(answers):
        return True
    try:
        satisfaction = appel.satisfaction_apprenant
    except Exception:
        satisfaction = None
    return satisfaction_has_any_answer(satisfaction)


def _file_field_has_name(file_field) -> bool:
    return bool(getattr(file_field, "name", "") or "")


def appel_has_any_audio(appel: "Appel") -> bool:
    if _file_field_has_name(getattr(appel, "audio_file", None)):
        return True
    try:
        satisfaction = appel.satisfaction_apprenant
    except Exception:
        satisfaction = None
    return _file_field_has_name(getattr(satisfaction, "audio_appel", None))


def infer_padesce_status(current_status: str, *, has_form: bool, has_audio: bool) -> str:
    normalized_status = str(current_status or "").strip()
    if has_form and has_audio:
        return "formulaire_avec_audio"
    if has_form:
        return "formulaire_rempli"
    if has_audio:
        return "appel_reussi"
    if normalized_status == "en_attente":
        return "en_attente"
    if normalized_status == "a_rappeler":
        return "a_rappeler"
    if normalized_status in CALL_TENTATIVE_STATUSES:
        return "appel_tente"
    if normalized_status in CALL_COMPLETED_STATUSES:
        return "appel_reussi"
    if normalized_status:
        return "appel_tente"
    return "en_attente"


def derive_padesce_status(appel: "Appel") -> str:
    return infer_padesce_status(
        getattr(appel, "status", ""),
        has_form=appel_has_any_form_data(appel),
        has_audio=appel_has_any_audio(appel),
    )


def sync_padesce_status(appel: "Appel", *, save: bool = True) -> str:
    new_status = derive_padesce_status(appel)
    if save and new_status != appel.status:
        appel.status = new_status
        appel.save(update_fields=["status", "updated_at"])
    else:
        appel.status = new_status
    return new_status


class Appel(TimeStampedModel):
    STATUS_CHOICES = [
        ("en_attente", "En attente"),
        ("appel_tente", "Appel Tenté"),
        ("appel_reussi", "Appel Réussi"),
        ("formulaire_rempli", "Formulaire Rempli"),
        ("formulaire_avec_audio", "Formulaire avec Audio"),
        # Anciens statuts (rétrocompatibilité)
        ("en_cours", "En cours"),
        ("pause", "Pause"),
        ("a_rappeler", "A rappeler"),
        ("termine", "Termine"),
    ]

    code = models.CharField(max_length=50, unique=True)
    nom = models.CharField(max_length=255)
    prestataire = models.CharField(max_length=255, blank=True)
    beneficiaire = models.CharField(max_length=255, blank=True)
    lieu = models.CharField(max_length=255, blank=True)
    classe_label = models.CharField(max_length=100, blank=True)
    fenetre = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    classe = models.ForeignKey(Classe, on_delete=models.SET_NULL, null=True, blank=True, related_name="appels")
    telephone1 = models.CharField(max_length=30, blank=True)
    telephone2 = models.CharField(max_length=30, blank=True)
    taux_presence = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="en_attente")
    rappel_at = models.DateTimeField(null=True, blank=True)
    type_formation_declaree = models.TextField(blank=True)
    formation_padesce = models.CharField(max_length=255, blank=True)
    deja_forme = models.BooleanField(default=False)
    flag_pas_forme = models.BooleanField(default=False, verbose_name="N'a pas suivi la formation")
    flag_faux_nom = models.BooleanField(default=False, verbose_name="Faux nom")
    flag_vrai_nom = models.CharField(max_length=255, blank=True, verbose_name="Vrai nom")
    flag_deja_appele = models.BooleanField(default=False, verbose_name="D\u00e9j\u00e0 appel\u00e9")
    flag_numero_double = models.BooleanField(default=False, verbose_name="Num\u00e9ro double")
    audio_file = models.FileField(upload_to=appel_audio_upload, null=True, blank=True, max_length=255)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="appels_lock"
    )
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self) -> str:
        return f"Appel {self.code} - {self.nom}"


class AppelImportArchive(TimeStampedModel):
    appel = models.ForeignKey(
        Appel, on_delete=models.SET_NULL, null=True, blank=True, related_name="import_archives"
    )
    import_mode = models.CharField(max_length=50, blank=True)
    source_code = models.CharField(max_length=50, blank=True)
    snapshot = models.JSONField(default=dict)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Archive import {self.source_code or '-'} ({self.import_mode or 'unknown'})"


def appel_cga_audio_upload(instance: "AppelCGA", filename: str) -> str:
    now = timezone.now()
    ts = now.strftime("%Y%m%d_%H%M%S")
    raison_slug = _short_slug(instance.raison_sociale, "raison-sociale", max_len=28)
    niu_slug = _short_slug(instance.niu, "niu", max_len=16)
    ext = filename.split(".")[-1] if "." in filename else "mp3"
    return f"cga/{now:%Y}/{now:%m}/{now:%d}/{niu_slug}-{raison_slug}-{ts}.{ext}"


def appel_formateur_audio_upload(instance: "AppelFormateur", filename: str) -> str:
    now = timezone.now()
    ts = now.strftime("%Y%m%d_%H%M%S")
    prestataire_slug = _short_slug(instance.prestataire, "prestataire", max_len=24)
    beneficiaire_slug = _short_slug(instance.beneficiaire, "beneficiaire", max_len=20)
    phone_slug = _short_slug(instance.telephone, "telephone", max_len=12)
    ref_slug = _short_slug(instance.reference_code, "session", max_len=20)
    ext = filename.split(".")[-1] if "." in filename else "mp3"
    return (
        f"formateurs/{now:%Y}/{now:%m}/{now:%d}/"
        f"{prestataire_slug}-{beneficiaire_slug}/{ref_slug}-{phone_slug}-{ts}.{ext}"
    )


class AppelCGA(TimeStampedModel):
    STATUS_CHOICES = Appel.STATUS_CHOICES

    numero = models.PositiveIntegerField(null=True, blank=True)
    raison_sociale = models.CharField(max_length=255)
    sigle = models.CharField(max_length=255, blank=True)
    niu = models.CharField(max_length=64, unique=True)
    activite_principale = models.CharField(max_length=255, blank=True)
    regime = models.CharField(max_length=120, blank=True)
    cri = models.CharField(max_length=120, blank=True)
    centre_de_rattachement = models.CharField(max_length=255, blank=True)
    ville = models.CharField(max_length=120, blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="en_attente", db_index=True)
    rappel_at = models.DateTimeField(null=True, blank=True)
    audio_file = models.FileField(upload_to=appel_cga_audio_upload, null=True, blank=True, max_length=255)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="appels_cga_lock"
    )
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["raison_sociale"]
        indexes = [
            models.Index(fields=["raison_sociale"]),
            models.Index(fields=["regime"]),
            models.Index(fields=["cri"]),
            models.Index(fields=["centre_de_rattachement"]),
            models.Index(fields=["ville"]),
        ]

    def __str__(self) -> str:
        return f"CGA {self.niu} - {self.raison_sociale}"


class AppelFormateur(TimeStampedModel):
    STATUS_CHOICES = Appel.STATUS_CHOICES

    reference_code = models.CharField(max_length=120, unique=True)
    numero_seance = models.PositiveIntegerField(null=True, blank=True)
    prestataire = models.CharField(max_length=255, blank=True)
    beneficiaire = models.CharField(max_length=255, blank=True)
    formation = models.TextField(blank=True)
    lieu = models.CharField(max_length=255, blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    cohorte = models.CharField(max_length=100, blank=True)
    date_label = models.CharField(max_length=255, blank=True)
    session_date = models.DateField(null=True, blank=True)
    heure_debut = models.CharField(max_length=30, blank=True)
    heure_fin = models.CharField(max_length=30, blank=True)
    source_contact = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="en_attente", db_index=True)
    rappel_at = models.DateTimeField(null=True, blank=True)
    audio_file = models.FileField(upload_to=appel_formateur_audio_upload, null=True, blank=True, max_length=255)
    q1_prerequis_apprenants = models.PositiveSmallIntegerField(null=True, blank=True)
    q2_interaction_apprenants = models.PositiveSmallIntegerField(null=True, blank=True)
    q3_competences_acquises = models.PositiveSmallIntegerField(null=True, blank=True)
    q4_gestion_administrative = models.TextField(blank=True)
    q5_gestion_financiere = models.TextField(blank=True)
    q6_communication = models.TextField(blank=True)
    commentaires = models.TextField(blank=True)
    recommandations = models.TextField(blank=True)
    satisfaction_completed_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appels_formateurs_lock",
    )
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["session_date", "numero_seance", "telephone"]
        indexes = [
            models.Index(fields=["prestataire"]),
            models.Index(fields=["beneficiaire"]),
            models.Index(fields=["formation"]),
            models.Index(fields=["cohorte"]),
            models.Index(fields=["session_date"]),
            models.Index(fields=["telephone"]),
        ]

    def __str__(self) -> str:
        label = self.telephone or self.source_contact or self.reference_code
        return f"Appel formateur {self.reference_code} - {label}"



class AppelAnswers(TimeStampedModel):
    appel = models.OneToOneField(Appel, on_delete=models.CASCADE, related_name="answers")
    q1_clarte_exposes = models.PositiveSmallIntegerField(null=True, blank=True)
    q2_interaction_formateur = models.PositiveSmallIntegerField(null=True, blank=True)
    q3_maitrise_contenu = models.PositiveSmallIntegerField(null=True, blank=True)
    q4_salle_adequate = models.PositiveSmallIntegerField(null=True, blank=True)
    q5_materiel_disponible = models.PositiveSmallIntegerField(null=True, blank=True)
    q6_organisation_temps = models.PositiveSmallIntegerField(null=True, blank=True)
    q7_utilite_formation = models.PositiveSmallIntegerField(null=True, blank=True)
    q8_adequation_besoins = models.PositiveSmallIntegerField(null=True, blank=True)
    q9_satisfaction_globale = models.PositiveSmallIntegerField(null=True, blank=True)
    commentaire = models.TextField(blank=True, default="RAS")
    recommandations = models.TextField(blank=True, default="RAS")
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="appel_answers_modified"
    )
    modified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Answers for {self.appel}"

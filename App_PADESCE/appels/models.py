import datetime

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.text import slugify

from App_PADESCE.core.models import TimeStampedModel
from App_PADESCE.formations.models import Classe, Prestataire

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
APPEL_SUCCESS_TEXT_FIELDS = ("commentaire", "recommandations")

PADESCE_FORM_TRACKING_CUTOFF = datetime.datetime(2026, 3, 9, 0, 0, 0)
CALL_ACTIVE_STATUSES = ("en_cours", "pause")
CALL_TENTATIVE_STATUSES = ("appel_tente",) + CALL_ACTIVE_STATUSES
CALL_FORM_STATUSES = ("formulaire_rempli", "formulaire_avec_audio")
CALL_SUCCESS_STATUSES = ("appel_reussi",) + CALL_FORM_STATUSES + ("termine",)
CALL_COMPLETED_STATUSES = CALL_SUCCESS_STATUSES
CALL_STARTABLE_STATUSES = ("en_attente", "appel_tente", "appel_reussi", "a_rappeler")
# Les classes atteignent le seuil d'analyse quand un formulaire est sauve
# ou quand une ancienne ligne deja finalisee est au statut "termine".
CALL_ANALYSIS_THRESHOLD_STATUSES = CALL_FORM_STATUSES + ("termine",)


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


def normalize_call_status(value: str) -> str:
    return str(value or "").strip()


def is_call_active_status(status: str) -> bool:
    return normalize_call_status(status) in CALL_ACTIVE_STATUSES


def is_call_attempted_status(status: str) -> bool:
    return normalize_call_status(status) not in {"", "en_attente"}


def is_call_success_status(status: str) -> bool:
    return normalize_call_status(status) in CALL_SUCCESS_STATUSES


def is_call_form_status(status: str) -> bool:
    return normalize_call_status(status) in CALL_FORM_STATUSES


def is_call_startable_status(status: str) -> bool:
    return normalize_call_status(status) in CALL_STARTABLE_STATUSES


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
    return (
        f"padesce/{now:%Y}/{now:%m}/{now:%d}/"
        f"{prestataire_slug}-{beneficiaire_slug}/"
        f"{code_slug}-{nom_slug}-{cohorte_slug}-{ts}.{ext}"
    )


def answers_have_any_answer(answers) -> bool:
    return bool(
        answers
        and any(getattr(answers, field, None) is not None for field in APPEL_ANSWER_QUESTION_FIELDS)
    )


def satisfaction_has_any_answer(satisfaction) -> bool:
    return bool(
        satisfaction
        and any(
            getattr(satisfaction, field, None) is not None for field in APPEL_ANSWER_QUESTION_FIELDS
        )
    )


def _has_meaningful_text_signal(value) -> bool:
    normalized = str(value or "").strip()
    return bool(normalized and normalized.upper() != "RAS")


def answers_have_success_signal(answers) -> bool:
    return bool(
        answers
        and any(
            _has_meaningful_text_signal(getattr(answers, field_name, ""))
            for field_name in APPEL_SUCCESS_TEXT_FIELDS
        )
    )


def satisfaction_has_success_signal(satisfaction) -> bool:
    return bool(
        satisfaction
        and any(
            _has_meaningful_text_signal(getattr(satisfaction, field_name, ""))
            for field_name in APPEL_SUCCESS_TEXT_FIELDS
        )
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


def appel_has_success_signal(appel: "Appel") -> bool:
    if any(
        bool(getattr(appel, field_name, None))
        for field_name in (
            "deja_forme",
            "flag_pas_forme",
            "flag_faux_nom",
            "flag_deja_appele",
            "flag_numero_double",
        )
    ):
        return True
    if _has_meaningful_text_signal(getattr(appel, "flag_vrai_nom", "")):
        return True
    try:
        answers = appel.answers
    except Exception:
        answers = None
    if answers_have_success_signal(answers):
        return True
    try:
        satisfaction = appel.satisfaction_apprenant
    except Exception:
        satisfaction = None
    return satisfaction_has_success_signal(satisfaction)


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


def infer_padesce_status(
    current_status: str, *, has_form: bool, has_audio: bool, has_success_signal: bool = False
) -> str:
    normalized_status = normalize_call_status(current_status)

    # Preserver les statuts actifs et à rappeler
    if normalized_status in CALL_ACTIVE_STATUSES:
        return normalized_status
    if normalized_status == "a_rappeler":
        return "a_rappeler"

    # NOUVELLE LOGIQUE - Priorité aux conditions métier
    # 1. Formulaire + Audio = statut le plus complet
    if has_form and has_audio:
        return "formulaire_avec_audio"

    # 2. Appel démarré mais pas encore décroché = appel tenté
    if normalized_status in ("en_cours", "appel_tente"):
        return "appel_tente"

    # 3. Appel décroché avec audio = appel réussi
    if has_audio and not has_form:
        return "appel_reussi"

    # 4. Formulaire seul = formulaire rempli
    if has_form and not has_audio:
        return "formulaire_rempli"

    # 5. Signal de réussite sans audio/formulaire = appel réussi
    if has_success_signal:
        return "appel_reussi"

    # 6. Statuts par défaut selon état actuel
    if normalized_status == "en_attente":
        return "en_attente"

    # 7. Pour les anciens statuts, conserver la compatibilité
    if normalized_status in CALL_SUCCESS_STATUSES:
        return "appel_reussi"
    if normalized_status in CALL_TENTATIVE_STATUSES:
        return "appel_tente"

    # 8. Par défaut = en attente
    return "en_attente"


def derive_padesce_status(appel: "Appel") -> str:
    return infer_padesce_status(
        getattr(appel, "status", ""),
        has_form=appel_has_any_form_data(appel),
        has_audio=appel_has_any_audio(appel),
        has_success_signal=appel_has_success_signal(appel),
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
    is_active = models.BooleanField(default=True, db_index=True)
    classe = models.ForeignKey(
        Classe, on_delete=models.SET_NULL, null=True, blank=True, related_name="appels"
    )
    telephone1 = models.CharField(max_length=30, blank=True)
    telephone2 = models.CharField(max_length=30, blank=True)
    taux_presence = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(
        max_length=25, choices=STATUS_CHOICES, default="en_attente", db_index=True
    )
    rappel_at = models.DateTimeField(null=True, blank=True)
    type_formation_declaree = models.TextField(blank=True)
    formation_padesce = models.CharField(max_length=255, blank=True)
    deja_forme = models.BooleanField(default=False)
    flag_pas_forme = models.BooleanField(default=False, verbose_name="N'a pas suivi la formation")
    flag_faux_nom = models.BooleanField(default=False, verbose_name="Faux nom")
    flag_vrai_nom = models.CharField(max_length=255, blank=True, verbose_name="Vrai nom")
    flag_deja_appele = models.BooleanField(default=False, verbose_name="D\u00e9j\u00e0 appel\u00e9")
    flag_numero_double = models.BooleanField(default=False, verbose_name="Num\u00e9ro double")
    audio_file = models.FileField(
        upload_to=appel_audio_upload, null=True, blank=True, max_length=255
    )
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appels_lock",
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


def appel_pas_forme_audio_upload(instance: "AppelPasForme", filename: str) -> str:
    now = timezone.now()
    ts = now.strftime("%Y%m%d_%H%M%S")
    nom_slug = _short_slug(instance.nom, "apprenant", max_len=28)
    prestation_slug = _short_slug(instance.prestation_id, "prestation", max_len=18)
    phone_slug = _short_slug(instance.telephone, "telephone", max_len=12)
    ext = filename.split(".")[-1] if "." in filename else "mp3"
    return (
        f"pas-forme/{now:%Y}/{now:%m}/{now:%d}/"
        f"{prestation_slug}-{phone_slug}-{nom_slug}-{ts}.{ext}"
    )


def appel_prestataire_demarrage_audio_upload(
    instance: "AppelPrestataireDemarrage", filename: str
) -> str:
    now = timezone.now()
    ts = now.strftime("%Y%m%d_%H%M%S")
    code_slug = _short_slug(instance.prestataire_code, "prestataire", max_len=18)
    nom_slug = _short_slug(instance.nom_prestataire, "prestataire", max_len=28)
    phone_slug = _short_slug(instance.telephone, "telephone", max_len=12)
    ext = filename.split(".")[-1] if "." in filename else "mp3"
    return (
        f"prestataires-demarrage/{now:%Y}/{now:%m}/{now:%d}/"
        f"{code_slug}-{phone_slug}-{nom_slug}-{ts}.{ext}"
    )


FORMATEUR_SCORE_FIELDS = (
    "q1_prerequis_apprenants",
    "q2_interaction_apprenants",
    "q3_competences_acquises",
)

FORMATEUR_TEXT_FIELDS = (
    "q4_gestion_administrative",
    "q5_gestion_financiere",
    "q6_communication",
    "commentaires",
    "recommandations",
)


def formateur_has_any_form_data(row: "AppelFormateur") -> bool:
    return any(
        getattr(row, field_name, None) not in (None, "")
        for field_name in (*FORMATEUR_SCORE_FIELDS, *FORMATEUR_TEXT_FIELDS)
    ) or bool(getattr(row, "satisfaction_completed_at", None))


def formateur_has_any_audio(row: "AppelFormateur") -> bool:
    f = getattr(row, "audio_file", None)
    if not f or not f.name:
        return False
    try:
        return f.storage.exists(f.name)
    except Exception:
        return False


def derive_formateur_status(row: "AppelFormateur") -> str:
    return infer_padesce_status(
        getattr(row, "status", ""),
        has_form=formateur_has_any_form_data(row),
        has_audio=formateur_has_any_audio(row),
    )


def sync_formateur_status(row: "AppelFormateur", *, save: bool = True) -> str:
    new_status = derive_formateur_status(row)
    if save and new_status != row.status:
        row.status = new_status
        row.save(update_fields=["status", "updated_at"])
    else:
        row.status = new_status
    return new_status


class AppelCGA(TimeStampedModel):
    STATUS_CHOICES = Appel.STATUS_CHOICES
    SOURCE_ENTREPRISE = "entreprise"
    SOURCE_CABINET = "cabinet"
    SOURCE_CHOICES = [
        (SOURCE_ENTREPRISE, "Entreprise"),
        (SOURCE_CABINET, "Cabinet"),
    ]

    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_ENTREPRISE,
        db_index=True,
    )
    numero = models.PositiveIntegerField(null=True, blank=True)
    raison_sociale = models.CharField(max_length=255)
    sigle = models.CharField(max_length=255, blank=True)
    niu = models.CharField(max_length=64, unique=True)
    activite_principale = models.CharField(max_length=255, blank=True)
    regime = models.CharField(max_length=120, blank=True)
    cri = models.CharField(max_length=120, blank=True)
    centre_de_rattachement = models.CharField(max_length=255, blank=True)
    ville = models.CharField(max_length=120, blank=True)
    telephone = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    status = models.CharField(
        max_length=25, choices=STATUS_CHOICES, default="en_attente", db_index=True
    )
    rappel_at = models.DateTimeField(null=True, blank=True)
    audio_file = models.FileField(
        upload_to=appel_cga_audio_upload, null=True, blank=True, max_length=255
    )
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appels_cga_lock",
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    interet = models.CharField(max_length=10, blank=True, verbose_name="Intérêt")
    mauvais_numero = models.CharField(max_length=10, blank=True, verbose_name="Mauvais numéro")
    indisponible = models.CharField(max_length=10, blank=True, verbose_name="Indisponible")

    @property
    def resultat_summary(self) -> str:
        parts = []
        if self.interet == "OUI":
            parts.append("Intéressé")
        elif self.interet == "NON":
            parts.append("Pas intéressé")
        if self.mauvais_numero == "OUI":
            parts.append("Mauvais numéro")
        if self.indisponible == "OUI":
            parts.append("Indisponible")
        return ", ".join(parts)

    class Meta:
        ordering = ["raison_sociale"]
        indexes = [
            models.Index(
                fields=["source", "is_active", "status"], name="appelcga_source_active_idx"
            ),
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
    status = models.CharField(
        max_length=25, choices=STATUS_CHOICES, default="en_attente", db_index=True
    )
    rappel_at = models.DateTimeField(null=True, blank=True)
    audio_file = models.FileField(
        upload_to=appel_formateur_audio_upload, null=True, blank=True, max_length=255
    )
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


class AppelPasForme(TimeStampedModel):
    STATUS_CHOICES = Appel.STATUS_CHOICES
    BOOLEAN_CHOICES = [
        ("OUI", "Oui"),
        ("NON", "Non"),
    ]

    reference_code = models.CharField(max_length=120, unique=True)
    numero = models.PositiveIntegerField(null=True, blank=True)
    nom = models.CharField(max_length=255)
    telephone = models.CharField(max_length=30, blank=True)
    est_forme = models.CharField(max_length=80, blank=True)
    prestation_id = models.CharField(max_length=80, blank=True, db_index=True)
    prestataire = models.CharField(max_length=255, blank=True)
    beneficiaire = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    status = models.CharField(
        max_length=25, choices=STATUS_CHOICES, default="en_attente", db_index=True
    )
    rappel_at = models.DateTimeField(null=True, blank=True)
    audio_file = models.FileField(
        upload_to=appel_pas_forme_audio_upload, null=True, blank=True, max_length=255
    )
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appels_pas_forme_lock",
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    connait_structure = models.CharField(max_length=3, choices=BOOLEAN_CHOICES, blank=True)
    beneficiaire_corrige = models.CharField(max_length=255, blank=True)
    connait_prestataire = models.CharField(max_length=3, choices=BOOLEAN_CHOICES, blank=True)
    prestataire_corrige = models.CharField(max_length=255, blank=True)
    membre_structure = models.CharField(max_length=3, choices=BOOLEAN_CHOICES, blank=True)
    a_assiste_formation = models.CharField(max_length=3, choices=BOOLEAN_CHOICES, blank=True)
    connait_theme = models.CharField(max_length=3, choices=BOOLEAN_CHOICES, blank=True)
    nombre_seances = models.PositiveSmallIntegerField(null=True, blank=True)
    faux_numero = models.CharField(max_length=3, choices=BOOLEAN_CHOICES, blank=True)
    bon_numero = models.CharField(max_length=30, blank=True)
    faux_nom = models.CharField(max_length=3, choices=BOOLEAN_CHOICES, blank=True)
    vrai_nom = models.CharField(max_length=255, blank=True)
    satisfaction_completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["nom"]
        indexes = [
            models.Index(fields=["nom"]),
            models.Index(fields=["telephone"]),
            models.Index(fields=["prestation_id"]),
            models.Index(fields=["prestataire"]),
            models.Index(fields=["beneficiaire"]),
        ]

    def __str__(self) -> str:
        return f"Appel pas forme {self.reference_code} - {self.nom}"


class AppelPasFormeII(TimeStampedModel):
    STATUS_CHOICES = Appel.STATUS_CHOICES

    reference_code = models.CharField(max_length=160, unique=True)
    prestation_id = models.CharField(max_length=80, db_index=True)
    nom = models.CharField(max_length=255)
    telephone = models.CharField(max_length=30, blank=True)
    beneficiaire = models.CharField(max_length=255, blank=True)
    prestataire = models.CharField(max_length=255, blank=True)
    genre = models.CharField(max_length=20, blank=True)
    absent_dans_consolide = models.BooleanField(default=False)
    total_presence = models.PositiveSmallIntegerField(null=True, blank=True)
    total_seances = models.PositiveSmallIntegerField(null=True, blank=True)
    seuil_75 = models.PositiveSmallIntegerField(null=True, blank=True)
    nombre_seances_source = models.PositiveSmallIntegerField(null=True, blank=True)
    forme_final = models.CharField(max_length=80, blank=True)
    nombre_seances_declare = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="en_attente", db_index=True)
    formulaire_rempli_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="appels_pas_forme_ii_lock")
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["prestation_id", "nom"]
        indexes = [models.Index(fields=["prestation_id", "is_active", "status"])]

    def __str__(self):
        return f"Appel pas forme II {self.reference_code} - {self.nom}"


class AppelPrestataireDemarrage(TimeStampedModel):
    STATUS_CHOICES = Appel.STATUS_CHOICES
    BOOLEAN_CHOICES = [
        ("OUI", "Oui"),
        ("NON", "Non"),
    ]
    MOTIF_DOCUMENTS = "documents"
    MOTIF_AUTORISATIONS = "autorisations"
    MOTIF_LOGISTIQUE = "logistique"
    MOTIF_STATUT_PRESTATAIRE = "statut_prestataire"
    MOTIF_CHOICES = [
        (
            MOTIF_DOCUMENTS,
            "Probleme de document (conventions, rapports, listes de beneficiaires, pieces requises)",
        ),
        (MOTIF_AUTORISATIONS, "Attente d'autorisations ou confirmation"),
        (MOTIF_LOGISTIQUE, "Probleme de logistique et lieux de formation"),
        (MOTIF_STATUT_PRESTATAIRE, "Statut du prestataire dans le programme"),
    ]

    reference_code = models.CharField(max_length=120, unique=True)
    numero = models.PositiveIntegerField(null=True, blank=True)
    prestataire_code = models.CharField(max_length=80, blank=True, db_index=True)
    nom_prestataire = models.CharField(max_length=255)
    nom_simplifie = models.CharField(max_length=120, blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    prestataire = models.ForeignKey(
        Prestataire,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appels_demarrage",
    )
    match_method = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    status = models.CharField(
        max_length=25, choices=STATUS_CHOICES, default="en_attente", db_index=True
    )
    rappel_at = models.DateTimeField(null=True, blank=True)
    audio_file = models.FileField(
        upload_to=appel_prestataire_demarrage_audio_upload,
        null=True,
        blank=True,
        max_length=255,
    )
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appels_prestataires_demarrage_lock",
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    prestation_debutee = models.CharField(max_length=3, choices=BOOLEAN_CHOICES, blank=True)
    date_debut_prestation = models.DateField(null=True, blank=True)
    motif_non_demarrage = models.CharField(max_length=40, choices=MOTIF_CHOICES, blank=True)
    commentaire = models.TextField(blank=True)
    faux_numero = models.CharField(max_length=3, choices=BOOLEAN_CHOICES, blank=True)
    bon_numero = models.CharField(max_length=30, blank=True)
    satisfaction_completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["nom_prestataire"]
        indexes = [
            models.Index(fields=["prestataire_code"]),
            models.Index(fields=["nom_prestataire"]),
            models.Index(fields=["telephone"]),
            models.Index(fields=["status", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"Appel prestataire demarrage {self.reference_code} - {self.nom_prestataire}"


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
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appel_answers_modified",
    )
    modified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Answers for {self.appel}"


class CallAlert(TimeStampedModel):
    SOURCE_PADESCE = "padesce"
    SOURCE_CGA = "cga"
    SOURCE_CHOICES = [
        (SOURCE_PADESCE, "PADESCE"),
        (SOURCE_CGA, "CGA"),
    ]

    STATUS_TODO = "todo"
    STATUS_DOING = "doing"
    STATUS_DONE = "done"
    STATUS_CHOICES = [
        (STATUS_TODO, "To Do"),
        (STATUS_DOING, "Doing"),
        (STATUS_DONE, "Done"),
    ]

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="call_alerts_reported",
    )
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, db_index=True)
    alert_types = models.JSONField(default=list, blank=True)
    details = models.TextField(blank=True)
    page_path = models.CharField(max_length=255, blank=True)
    page_title = models.CharField(max_length=255, blank=True)
    call_id = models.CharField(max_length=64, blank=True, db_index=True)
    call_label = models.CharField(max_length=255, blank=True)
    call_status = models.CharField(max_length=40, blank=True)
    last_actions = models.JSONField(default=list, blank=True)
    user_agent = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_TODO,
        db_index=True,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="call_alerts_assigned",
    )
    admin_seen_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="call_alerts_seen",
    )
    admin_seen_at = models.DateTimeField(null=True, blank=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    reporter_seen_at = models.DateTimeField(null=True, blank=True)
    admin_message = models.TextField(blank=True)
    resolution_comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="callalert_status_created_idx"),
            models.Index(
                fields=["reporter", "-updated_at"],
                name="callalert_reporter_updated_idx",
            ),
            models.Index(fields=["source", "status"], name="callalert_source_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_source_display()} alert #{self.pk} by {self.reporter}"

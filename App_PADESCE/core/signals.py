import logging
from typing import Any

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from App_PADESCE.appels.models import Appel, AppelAnswers
from App_PADESCE.core.cache_versions import bump_analysis_cache_version
from App_PADESCE.core.middleware import get_current_user
from App_PADESCE.core.models import AuditLog
from App_PADESCE.environnement.models import EnqueteEnvironnement
from App_PADESCE.presences.models import Presence
from App_PADESCE.satisfaction_apprenants.models import SatisfactionApprenant
from App_PADESCE.satisfaction_formateurs.models import SatisfactionFormateur

logger = logging.getLogger(__name__)


def _log_audit(instance: Any, action: str):
    try:
        AuditLog.objects.create(
            actor=get_current_user(),
            model_name=instance._meta.label_lower,
            object_pk=str(instance.pk),
            object_repr=str(instance),
            action=action,
        )
    except Exception as exc:  # pragma: no cover - ne pas bloquer l'app
        logger.warning("Audit logging failed for %s (%s): %s", instance, action, exc)


def _touch_analysis_runtime_cache(instance: Any):
    label = getattr(getattr(instance, "_meta", None), "label_lower", "")
    scopes = {
        "analysis-dashboard",
        "analysis-general",
        "appels-progress",
    }
    if label:
        scopes.add(f"model:{label}")
    bump_analysis_cache_version(*sorted(scopes))


@receiver(post_save, sender=Presence)
def audit_presence_save(sender, instance: Presence, created: bool, **kwargs):
    _log_audit(instance, "created" if created else "updated")


@receiver(post_delete, sender=Presence)
def audit_presence_delete(sender, instance: Presence, **kwargs):
    _log_audit(instance, "deleted")


@receiver(post_save, sender=SatisfactionApprenant)
def audit_satisfaction_apprenant_save(sender, instance: SatisfactionApprenant, created: bool, **kwargs):
    _log_audit(instance, "created" if created else "updated")
    _touch_analysis_runtime_cache(instance)


@receiver(post_delete, sender=SatisfactionApprenant)
def audit_satisfaction_apprenant_delete(sender, instance: SatisfactionApprenant, **kwargs):
    _log_audit(instance, "deleted")
    _touch_analysis_runtime_cache(instance)


@receiver(post_save, sender=Appel)
def audit_appel_save(sender, instance: Appel, created: bool, **kwargs):
    _touch_analysis_runtime_cache(instance)


@receiver(post_delete, sender=Appel)
def audit_appel_delete(sender, instance: Appel, **kwargs):
    _touch_analysis_runtime_cache(instance)


@receiver(post_save, sender=AppelAnswers)
def audit_appel_answers_save(sender, instance: AppelAnswers, created: bool, **kwargs):
    _touch_analysis_runtime_cache(instance)


@receiver(post_delete, sender=AppelAnswers)
def audit_appel_answers_delete(sender, instance: AppelAnswers, **kwargs):
    _touch_analysis_runtime_cache(instance)


@receiver(post_save, sender=SatisfactionFormateur)
def audit_satisfaction_formateur_save(sender, instance: SatisfactionFormateur, created: bool, **kwargs):
    _log_audit(instance, "created" if created else "updated")


@receiver(post_delete, sender=SatisfactionFormateur)
def audit_satisfaction_formateur_delete(sender, instance: SatisfactionFormateur, **kwargs):
    _log_audit(instance, "deleted")


@receiver(post_save, sender=EnqueteEnvironnement)
def audit_environnement_save(sender, instance: EnqueteEnvironnement, created: bool, **kwargs):
    _log_audit(instance, "created" if created else "updated")


@receiver(post_delete, sender=EnqueteEnvironnement)
def audit_environnement_delete(sender, instance: EnqueteEnvironnement, **kwargs):
    _log_audit(instance, "deleted")

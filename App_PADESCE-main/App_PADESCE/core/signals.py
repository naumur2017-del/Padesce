import logging
from typing import Any

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

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


@receiver(post_save, sender=Presence)
def audit_presence_save(sender, instance: Presence, created: bool, **kwargs):
    _log_audit(instance, "created" if created else "updated")


@receiver(post_delete, sender=Presence)
def audit_presence_delete(sender, instance: Presence, **kwargs):
    _log_audit(instance, "deleted")


@receiver(post_save, sender=SatisfactionApprenant)
def audit_satisfaction_apprenant_save(sender, instance: SatisfactionApprenant, created: bool, **kwargs):
    _log_audit(instance, "created" if created else "updated")


@receiver(post_delete, sender=SatisfactionApprenant)
def audit_satisfaction_apprenant_delete(sender, instance: SatisfactionApprenant, **kwargs):
    _log_audit(instance, "deleted")


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

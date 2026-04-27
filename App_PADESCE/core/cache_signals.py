"""
Signaux Django pour l'invalidation automatique du cache.

Ce module configure des signaux qui invalident automatiquement les caches
lorsque les données sous-jacentes sont modifiées.
"""

import logging

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.appels.models import Appel, AppelAnswers
from App_PADESCE.satisfaction_apprenants.models import SatisfactionApprenant
from App_PADESCE.core.presence_bulk_cache import invalidate_presence_cache
from App_PADESCE.core.dashboard_stats_cache import invalidate_stats_cache

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Apprenant)
def apprenant_saved(sender, instance, created, **kwargs):
    """
    Invalide le cache de présence lorsqu'un apprenant est modifié.
    """
    if created or (
        hasattr(instance, '_dirty_fields') and 
        any(field in instance._dirty_fields for field in ['c1', 'c2', 'c3', 'c4'])
    ):
        invalidate_presence_cache()
        logger.debug(f"Cache présence invalidé suite à modification apprenant {instance.code}")


@receiver(post_save, sender=Appel)
def appel_saved(sender, instance, created, **kwargs):
    """
    Invalide le cache de statistiques lorsqu'un appel est modifié.
    """
    # Invalider seulement si des champs pertinents ont changé
    fields_to_check = ['status', 'classe', 'prestataire', 'beneficiaire']
    
    should_invalidate = created
    if not should_invalidate and hasattr(instance, '_dirty_fields'):
        should_invalidate = any(field in instance._dirty_fields for field in fields_to_check)
    
    if should_invalidate:
        invalidate_stats_cache()
        logger.debug(f"Cache statistiques invalidé suite à modification appel {instance.code}")


@receiver(post_delete, sender=Appel)
def appel_deleted(sender, instance, **kwargs):
    """
    Invalide le cache de statistiques lorsqu'un appel est supprimé.
    """
    invalidate_stats_cache()
    logger.debug(f"Cache statistiques invalidé suite à suppression appel {instance.code}")


@receiver(post_save, sender=AppelAnswers)
def appel_answers_saved(sender, instance, created, **kwargs):
    """
    Invalide le cache de statistiques lorsque les réponses d'un appel sont modifiées.
    """
    # Les réponses affectent les statistiques de satisfaction
    invalidate_stats_cache()
    logger.debug(f"Cache statistiques invalidé suite à modification réponses appel {instance.appel.code}")


@receiver(post_save, sender=SatisfactionApprenant)
def satisfaction_saved(sender, instance, created, **kwargs):
    """
    Invalide le cache de statistiques lorsque la satisfaction est modifiée.
    """
    # La satisfaction affecte directement les statistiques
    invalidate_stats_cache()
    logger.debug(f"Cache statistiques invalidé suite à modification satisfaction {instance.appel.code}")


@receiver(post_delete, sender=SatisfactionApprenant)
def satisfaction_deleted(sender, instance, **kwargs):
    """
    Invalide le cache de statistiques lorsque la satisfaction est supprimée.
    """
    invalidate_stats_cache()
    logger.debug(f"Cache statistiques invalidé suite à suppression satisfaction {instance.appel.code}")


def setup_cache_signals():
    """
    Configure les signaux de cache.
    
    À appeler dans apps.py ou lors de l'initialisation de Django.
    """
    logger.info("Signaux de cache configurés")


# Pour le débogage: compter les invalidations
class CacheInvalidationCounter:
    """
    Compteur d'invalidations de cache pour le monitoring.
    """
    
    def __init__(self):
        self.counts = {
            'presence': 0,
            'stats': 0,
        }
    
    def increment_presence(self):
        self.counts['presence'] += 1
        logger.info(f"Invalidations cache présence: {self.counts['presence']}")
    
    def increment_stats(self):
        self.counts['stats'] += 1
        logger.info(f"Invalidations cache statistiques: {self.counts['stats']}")
    
    def get_counts(self):
        return self.counts.copy()


# Instance globale pour le monitoring
invalidation_counter = CacheInvalidationCounter()


# Wrapper pour les fonctions d'invalidation avec comptage
def invalidate_presence_cache_with_count():
    """Invalide le cache de présence en comptant l'invalidation."""
    invalidate_presence_cache()
    invalidation_counter.increment_presence()


def invalidate_stats_cache_with_count():
    """Invalide le cache de statistiques en comptant l'invalidation."""
    invalidate_stats_cache()
    invalidation_counter.increment_stats()


# Remplacer les fonctions originales pour le monitoring
def patch_invalidation_functions():
    """
    Remplace les fonctions d'invalidation par des versions avec comptage.
    
    À utiliser dans un contexte de développement/debug.
    """
    import App_PADESCE.core.presence_bulk_cache as presence_module
    import App_PADESCE.core.dashboard_stats_cache as stats_module
    
    presence_module.invalidate_presence_cache = invalidate_presence_cache_with_count
    stats_module.invalidate_stats_cache = invalidate_stats_cache_with_count
    
    logger.info("Fonctions d'invalidation patchées avec comptage")

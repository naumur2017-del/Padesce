"""
Cache optimisé pour les statistiques du dashboard.

Ce module pré-calcule et met en cache les statistiques agrégées
utilisées dans le dashboard consultant pour éviter les recalculs coûteux.
"""

import hashlib
import logging
from typing import Dict, List, Optional, Tuple

from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone

from App_PADESCE.appels.models import Appel, is_call_success_status
from App_PADESCE.satisfaction_apprenants.models import SatisfactionApprenant

logger = logging.getLogger(__name__)

# Cache TTL: 30 minutes pour les statistiques
STATS_CACHE_TTL = 30 * 60  # 1800 secondes
STATS_CACHE_KEY_PREFIX = "dashboard_stats"

# Cache version pour invalidation globale
STATS_CACHE_VERSION_KEY = "dashboard_stats_cache_version"


def _get_cache_version() -> str:
    """Obtient la version actuelle du cache pour invalidation."""
    version = cache.get(STATS_CACHE_VERSION_KEY)
    if version is None:
        version = "v1"
        cache.set(STATS_CACHE_VERSION_KEY, version, timeout=None)
    return str(version)


def _invalidate_cache() -> None:
    """Invalide le cache de statistiques global."""
    import time
    version = f"v{int(time.time())}"
    cache.set(STATS_CACHE_VERSION_KEY, version, timeout=None)
    logger.info(f"Cache statistiques invalidé, nouvelle version: {version}")


def _build_cache_key(filters_hash: str, stat_type: str) -> str:
    """Construit une clé de cache unique pour les statistiques."""
    version = _get_cache_version()
    return f"{STATS_CACHE_KEY_PREFIX}_{version}_{stat_type}_{filters_hash}"


def _hash_filters(filters: Dict) -> str:
    """Crée un hash unique pour les filtres appliqués."""
    # Normaliser les filtres pour garantir la cohérence
    normalized_filters = {}
    for key, value in filters.items():
        if value:
            normalized_filters[key] = str(value).strip().lower()
    
    # Trier les clés pour garantir la cohérence
    sorted_items = sorted(normalized_filters.items())
    filter_string = "|".join(f"{k}:{v}" for k, v in sorted_items)
    
    # Hash pour éviter les clés trop longues
    hash_object = hashlib.md5(filter_string.encode('utf-8'))
    return hash_object.hexdigest()


def get_dashboard_stats(filters: Dict = None) -> Dict:
    """
    Récupère les statistiques du dashboard avec cache.
    
    Args:
        filters: Dictionnaire des filtres appliqués (classe, prestation, etc.)
        
    Returns:
        Dict contenant toutes les statistiques calculées
    """
    if filters is None:
        filters = {}
    
    filters_hash = _hash_filters(filters)
    
    # Vérifier le cache
    cache_key = _build_cache_key(filters_hash, "main")
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        logger.debug(f"Cache hit statistiques dashboard pour filtres: {filters_hash[:8]}...")
        return cached_result
    
    # Cache miss: calculer les statistiques
    stats = _calculate_dashboard_stats(filters)
    
    # Mettre en cache
    cache.set(cache_key, stats, timeout=STATS_CACHE_TTL)
    logger.debug(f"Cache miss statistiques: calculé pour filtres: {filters_hash[:8]}...")
    
    return stats


def _calculate_dashboard_stats(filters: Dict) -> Dict:
    """Calcule toutes les statistiques du dashboard."""
    stats = {
        "total_appels": 0,
        "appels_reussis": 0,
        "appels_en_attente": 0,
        "taux_reussite": 0.0,
        "satisfaction_moyenne": 0.0,
        "satisfaction_count": 0,
        "audio_count": 0,
        "form_count": 0,
        "priority_count": 0,
        "fenetre_2_count": 0,
        "fenetre_3_count": 0,
        "presence_stats": {
            "c1_pr": 0, "c1_ab": 0,
            "c2_pr": 0, "c2_ab": 0,
            "c3_pr": 0, "c3_ab": 0,
            "c4_pr": 0, "c4_ab": 0,
        },
        "top_classes": [],
        "top_prestations": [],
    }
    
    try:
        # Base queryset avec filtres
        base_qs = Appel.objects.filter(is_active=True)
        
        # Appliquer les filtres
        if filters.get("classe"):
            base_qs = base_qs.filter(
                Q(classe__code__iexact=filters["classe"]) | 
                Q(classe_label__icontains=filters["classe"])
            )
        if filters.get("prestation"):
            base_qs = base_qs.filter(prestataire__iexact=filters["prestation"])
        if filters.get("beneficiaire"):
            base_qs = base_qs.filter(beneficiaire__iexact=filters["beneficiaire"])
        if filters.get("status"):
            base_qs = base_qs.filter(status=filters["status"])
        
        # Statistiques générales
        stats["total_appels"] = base_qs.count()
        stats["appels_en_attente"] = base_qs.filter(status="en_attente").count()
        
        # Appels réussis (hors en attente)
        completed_qs = base_qs.exclude(status="en_attente")
        stats["appels_reussis"] = sum(
            1 for call in completed_qs if is_call_success_status(call.status)
        )
        
        if stats["total_appels"] > stats["appels_en_attente"]:
            stats["taux_reussite"] = round(
                (stats["appels_reussis"] / (stats["total_appels"] - stats["appels_en_attente"])) * 100, 2
            )
        
        # Statistiques satisfaction
        satisfaction_qs = SatisfactionApprenant.objects.filter(
            appel__in=completed_qs,
            q9_satisfaction_globale__isnull=False
        )
        
        satisfaction_values = satisfaction_qs.values_list('q9_satisfaction_globale', flat=True)
        if satisfaction_values:
            stats["satisfaction_moyenne"] = round(sum(satisfaction_values) / len(satisfaction_values), 1)
            stats["satisfaction_count"] = len(satisfaction_values)
        
        # Statistiques audio et formulaires
        stats["audio_count"] = completed_qs.filter(audio_file__isnull=False).exclude(audio_file="").count()
        
        # Compter les formulaires complets (approximation basée sur les réponses)
        stats["form_count"] = completed_qs.filter(
            answers__isnull=False
        ).distinct().count()
        
        # Fenêtres 2 et 3
        stats["fenetre_2_count"] = 0
        stats["fenetre_3_count"] = 0
        
        # Top classes et prestations
        stats["top_classes"] = list(
            completed_qs.values('classe__code', 'classe_label')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        
        stats["top_prestations"] = list(
            completed_qs.values('prestataire')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        
    except Exception as e:
        logger.error(f"Erreur calcul statistiques dashboard: {e}")
        # Retourner les valeurs par défaut
        pass
    
    return stats


def get_presence_summary_stats(filters: Dict = None) -> Dict:
    """
    Récupère les statistiques résumées de présence.
    
    Args:
        filters: Dictionnaire des filtres appliqués
        
    Returns:
        Dict avec les totaux de présence par contrôle
    """
    if filters is None:
        filters = {}
    
    filters_hash = _hash_filters(filters)
    cache_key = _build_cache_key(filters_hash, "presence")
    
    # Vérifier le cache
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    # Calculer les stats de présence
    presence_stats = {
        "c1_pr": 0, "c1_ab": 0, "c1_empty": 0,
        "c2_pr": 0, "c2_ab": 0, "c2_empty": 0,
        "c3_pr": 0, "c3_ab": 0, "c3_empty": 0,
        "c4_pr": 0, "c4_ab": 0, "c4_empty": 0,
        "total_participants": 0,
    }
    
    try:
        from App_PADESCE.core.presence_bulk_cache import get_bulk_presence_controls
        from App_PADESCE.core.apprenant_lookup import match_apprenants_to_appels
        from App_PADESCE.core.analysis_rules import appel_is_analysis_eligible
        
        # Récupérer les appels éligibles
        base_qs = Appel.objects.filter(is_active=True).exclude(status="en_attente")
        
        # Appliquer les filtres
        if filters.get("classe"):
            base_qs = base_qs.filter(
                Q(classe__code__iexact=filters["classe"]) | 
                Q(classe_label__icontains=filters["classe"])
            )
        if filters.get("prestation"):
            base_qs = base_qs.filter(prestataire__iexact=filters["prestation"])
        
        # Limiter pour éviter les calculs trop longs
        appels_list = list(base_qs[:500])  # Maximum 500 appels
        
        # Récupérer les apprenant_ids
        matched_apprenants = match_apprenants_to_appels(appels_list)
        apprenant_ids = []
        
        for app in appels_list:
            apprenant = matched_apprenants.get(app.pk)
            if apprenant:
                from App_PADESCE.core.apprenant_lookup import get_local_apprenant_identifier
                apprenant_id = get_local_apprenant_identifier(apprenant)
                if apprenant_id:
                    apprenant_ids.append(apprenant_id)
        
        # Récupérer les contrôles de présence en batch
        bulk_controls = get_bulk_presence_controls(apprenant_ids)
        
        # Compter les statistiques
        for apprenant_id, controls in bulk_controls.items():
            presence_stats["total_participants"] += 1
            
            for control in ["c1", "c2", "c3", "c4"]:
                value = controls.get(control, "")
                if value == "PR":
                    presence_stats[f"{control}_pr"] += 1
                elif value == "AB":
                    presence_stats[f"{control}_ab"] += 1
                else:
                    presence_stats[f"{control}_empty"] += 1
        
    except Exception as e:
        logger.error(f"Erreur calcul statistiques présence: {e}")
    
    # Mettre en cache
    cache.set(cache_key, presence_stats, timeout=STATS_CACHE_TTL)
    
    return presence_stats


def invalidate_stats_cache() -> None:
    """
    Invalide manuellement le cache de statistiques.
    
    À appeler lors de modifications importantes des données.
    """
    _invalidate_cache()
    logger.info("Cache statistiques invalidé manuellement")


def get_cache_stats() -> Dict:
    """
    Retourne des statistiques sur l'utilisation du cache.
    """
    version = _get_cache_version()
    
    return {
        "cache_version": version,
        "ttl_seconds": STATS_CACHE_TTL,
        "enabled": True,
        "main_stats_cached": cache.get(_build_cache_key("no_filters", "main")) is not None,
        "presence_stats_cached": cache.get(_build_cache_key("no_filters", "presence")) is not None,
    }


def warm_cache_for_filters(common_filters: List[Dict]) -> int:
    """
    Pré-charge le cache pour des filtres courants.
    
    Args:
        common_filters: Liste de dictionnaires de filtres courants
        
    Returns:
        Nombre d'entrées mises en cache
    """
    count = 0
    
    for filters in common_filters:
        try:
            get_dashboard_stats(filters)
            get_presence_summary_stats(filters)
            count += 2
        except Exception as e:
            logger.warning(f"Erreur warm cache pour filtres {filters}: {e}")
    
    logger.info(f"Cache warmed pour {count} entrées de statistiques")
    return count


def get_common_filters() -> List[Dict]:
    """
    Retourne une liste des filtres couramment utilisés pour le warm-up.
    """
    return [
        {},  # Pas de filtres
        {"fenetre": "2"},
        {"fenetre": "3"},
        {"status": "termine"},
        {"status": "a_rappeler"},
    ]


# Decorator pour invalider automatiquement le cache
def invalidate_stats_cache_on_change(func):
    """
    Décorateur qui invalide le cache de statistiques après modification des données.
    
    À utiliser sur les fonctions qui modifient les données d'appels ou de satisfaction.
    """
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        invalidate_stats_cache()
        return result
    return wrapper

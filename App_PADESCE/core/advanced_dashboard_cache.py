"""
Cache avancé pour les statistiques dashboard avec pré-calculs granulaires.

Ce module étend le cache de base avec des pré-calculs plus détaillés
par filtres, périodes, et agrégations spécifiques.
"""

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from django.core.cache import cache
from django.db.models import Count, Q, Avg, Sum, StdDev
from django.utils import timezone

from App_PADESCE.appels.models import Appel, is_call_success_status
from App_PADESCE.satisfaction_apprenants.models import SatisfactionApprenant

logger = logging.getLogger(__name__)

# Cache TTL: 30 minutes pour statistiques avancées
ADVANCED_STATS_CACHE_TTL = 30 * 60  # 1800 secondes
ADVANCED_STATS_CACHE_KEY_PREFIX = "advanced_dashboard_stats"

# Cache version pour invalidation globale
ADVANCED_STATS_CACHE_VERSION_KEY = "advanced_stats_cache_version"


def _get_cache_version() -> str:
    """Obtient la version actuelle du cache pour invalidation."""
    version = cache.get(ADVANCED_STATS_CACHE_VERSION_KEY)
    if version is None:
        version = "v1"
        cache.set(ADVANCED_STATS_CACHE_VERSION_KEY, version, timeout=None)
    return str(version)


def _invalidate_cache() -> None:
    """Invalide le cache de statistiques avancées."""
    import time
    version = f"v{int(time.time())}"
    cache.set(ADVANCED_STATS_CACHE_VERSION_KEY, version, timeout=None)
    logger.info(f"Cache statistiques avancées invalidé, nouvelle version: {version}")


def _build_cache_key(filters_hash: str, stat_type: str, period: str = "all") -> str:
    """Construit une clé de cache unique pour les statistiques avancées."""
    version = _get_cache_version()
    return f"{ADVANCED_STATS_CACHE_KEY_PREFIX}_{version}_{stat_type}_{period}_{filters_hash}"


def _hash_filters(filters: Dict) -> str:
    """Crée un hash unique pour les filtres appliqués."""
    normalized_filters = {}
    for key, value in filters.items():
        if value:
            normalized_filters[key] = str(value).strip().lower()
    
    sorted_items = sorted(normalized_filters.items())
    filter_string = "|".join(f"{k}:{v}" for k, v in sorted_items)
    hash_object = hashlib.md5(filter_string.encode('utf-8'))
    return hash_object.hexdigest()


def get_advanced_dashboard_stats(filters: Dict = None, period: str = "all") -> Dict:
    """
    Récupère les statistiques avancées du dashboard avec pré-calculs.
    
    Args:
        filters: Dictionnaire des filtres appliqués
        period: Période d'analyse ("all", "7d", "30d", "90d")
        
    Returns:
        Dict contenant les statistiques avancées
    """
    if filters is None:
        filters = {}
    
    filters_hash = _hash_filters(filters)
    cache_key = _build_cache_key(filters_hash, "advanced", period)
    
    # Vérifier le cache
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        logger.debug(f"Cache hit statistiques avancées: {period}, {filters_hash[:8]}...")
        return cached_result
    
    # Cache miss: calculer les statistiques avancées
    stats = _calculate_advanced_stats(filters, period)
    
    # Mettre en cache
    cache.set(cache_key, stats, timeout=ADVANCED_STATS_CACHE_TTL)
    logger.debug(f"Cache miss statistiques avancées: calculé pour {period}")
    
    return stats


def _calculate_advanced_stats(filters: Dict, period: str) -> Dict:
    """Calcule les statistiques avancées avec agrégations détaillées."""
    stats = {
        "period": period,
        "generated_at": timezone.now().isoformat(),
        "filters": filters,
        "overview": {},
        "performance": {},
        "satisfaction": {},
        "temporal": {},
        "quality": {},
        "distribution": {}
    }
    
    try:
        # Base queryset avec filtres et période
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
        
        # Appliquer le filtre de période
        base_qs = _apply_period_filter(base_qs, period)
        
        # Statistiques générales
        total_appels = base_qs.count()
        completed_qs = base_qs.exclude(status="en_attente")
        completed_count = completed_qs.count()
        
        stats["overview"] = {
            "total_appels": total_appels,
            "completed_appels": completed_count,
            "completion_rate": round((completed_count / total_appels * 100), 2) if total_appels > 0 else 0,
            "en_attente": base_qs.filter(status="en_attente").count(),
            "a_rappeler": base_qs.filter(status="a_rappeler").count(),
        }
        
        # Performance par statut
        status_stats = {}
        for status in ['termine', 'a_rappeler', 'en_attente', 'non_joint']:
            count = base_qs.filter(status=status).count()
            status_stats[status] = {
                "count": count,
                "percentage": round((count / total_appels * 100), 2) if total_appels > 0 else 0
            }
        stats["performance"]["by_status"] = status_stats
        
        # Taux de réussite
        successful_calls = sum(
            1 for call in completed_qs if is_call_success_status(call.status)
        )
        stats["performance"]["success_rate"] = round(
            (successful_calls / completed_count * 100), 2
        ) if completed_count > 0 else 0
        
        # Statistiques de satisfaction
        satisfaction_qs = SatisfactionApprenant.objects.filter(
            appel__in=completed_qs,
            q9_satisfaction_globale__isnull=False
        )
        
        if satisfaction_qs.exists():
            satisfaction_values = satisfaction_qs.values_list('q9_satisfaction_globale', flat=True)
            
            stats["satisfaction"] = {
                "average_score": round(sum(satisfaction_values) / len(satisfaction_values), 1),
                "response_count": len(satisfaction_values),
                "response_rate": round((len(satisfaction_values) / completed_count * 100), 2),
                "distribution": _calculate_score_distribution(satisfaction_values),
                "score_by_question": _calculate_satisfaction_by_question(satisfaction_qs)
            }
        else:
            stats["satisfaction"] = {
                "average_score": 0,
                "response_count": 0,
                "response_rate": 0,
                "distribution": {},
                "score_by_question": {}
            }
        
        # Statistiques temporelles
        stats["temporal"] = _calculate_temporal_stats(base_qs, period)
        
        # Statistiques de qualité des données
        stats["quality"] = _calculate_data_quality_stats(base_qs)
        
        # Distribution par prestataire et bénéficiaire
        stats["distribution"] = _calculate_distribution_stats(base_qs)
        
    except Exception as e:
        logger.error(f"Erreur calcul statistiques avancées: {e}")
        # Retourner les valeurs par défaut
        pass
    
    return stats


def _apply_period_filter(queryset, period: str):
    """Applique le filtre de période au queryset."""
    if period == "all":
        return queryset
    elif period == "7d":
        cutoff = timezone.now() - timedelta(days=7)
        return queryset.filter(created_at__gte=cutoff)
    elif period == "30d":
        cutoff = timezone.now() - timedelta(days=30)
        return queryset.filter(created_at__gte=cutoff)
    elif period == "90d":
        cutoff = timezone.now() - timedelta(days=90)
        return queryset.filter(created_at__gte=cutoff)
    else:
        return queryset


def _calculate_score_distribution(scores: List[int]) -> Dict:
    """Calcule la distribution des scores de satisfaction."""
    distribution = {i: 0 for i in range(1, 6)}  # Scores de 1 à 5
    
    for score in scores:
        if 1 <= score <= 5:
            distribution[score] += 1
    
    total = len(scores)
    if total > 0:
        for score in distribution:
            distribution[score] = round((distribution[score] / total * 100), 1)
    
    return distribution


def _calculate_satisfaction_by_question(satisfaction_qs) -> Dict:
    """Calcule les scores moyens par question de satisfaction."""
    questions = [
        'q1_clarte_exposes',
        'q2_interaction_formateur', 
        'q3_maitrise_contenu',
        'q4_salle_adequate',
        'q5_materiel_disponible',
        'q6_organisation_temps',
        'q7_utilite_formation',
        'q8_adequation_besoins',
        'q9_satisfaction_globale'
    ]
    
    scores_by_question = {}
    
    for question in questions:
        values = satisfaction_qs.values_list(question, flat=True).filter(**{f"{question}__isnull": False})
        if values:
            scores_by_question[question] = round(sum(values) / len(values), 1)
        else:
            scores_by_question[question] = 0
    
    return scores_by_question


def _calculate_temporal_stats(queryset, period: str) -> Dict:
    """Calcule les statistiques temporelles."""
    temporal_stats = {
        "period": period,
        "daily_volume": {},
        "peak_days": {},
        "trend": "stable"
    }
    
    try:
        # Volume quotidien (pour les 30 derniers jours max)
        if period in ["30d", "90d", "all"]:
            daily_counts = queryset.extra({
                'day': "date(created_at)"
            }).values('day').annotate(count=Count('id')).order_by('day')
            
            # Limiter aux 30 derniers jours pour éviter trop de données
            recent_daily = list(daily_counts)[-30:] if period == "all" else list(daily_counts)
            
            temporal_stats["daily_volume"] = {
                str(item['day']): item['count'] for item in recent_daily
            }
            
            # Calculer les jours de pointe
            if recent_daily:
                max_count = max(item['count'] for item in recent_daily)
                peak_days = [item for item in recent_daily if item['count'] == max_count]
                temporal_stats["peak_days"] = {
                    "max_volume": max_count,
                    "days": [str(item['day']) for item in peak_days]
                }
                
                # Détecter la tendance simple
                if len(recent_daily) >= 7:
                    recent_week = recent_daily[-7:]
                    earlier_week = recent_daily[-14:-7] if len(recent_daily) >= 14 else recent_daily[:-7]
                    
                    if earlier_week:
                        recent_avg = sum(item['count'] for item in recent_week) / len(recent_week)
                        earlier_avg = sum(item['count'] for item in earlier_week) / len(earlier_week)
                        
                        if recent_avg > earlier_avg * 1.1:
                            temporal_stats["trend"] = "increasing"
                        elif recent_avg < earlier_avg * 0.9:
                            temporal_stats["trend"] = "decreasing"
                        else:
                            temporal_stats["trend"] = "stable"
    
    except Exception as e:
        logger.error(f"Erreur calcul statistiques temporelles: {e}")
    
    return temporal_stats


def _calculate_data_quality_stats(queryset) -> Dict:
    """Calcule les statistiques de qualité des données."""
    quality_stats = {
        "data_completeness": {},
        "flag_analysis": {},
        "contact_quality": {}
    }
    
    total = queryset.count()
    if total == 0:
        return quality_stats
    
    # Complétude des données
    fields_to_check = ['nom', 'telephone1', 'telephone2', 'prestataire', 'beneficiaire', 'classe_label']
    
    for field in fields_to_check:
        filled_count = queryset.exclude(**{f"{field}__isnull": True}).exclude(**{f"{field}": ""}).count()
        quality_stats["data_completeness"][field] = {
            "filled": filled_count,
            "missing": total - filled_count,
            "completeness_rate": round((filled_count / total * 100), 2)
        }
    
    # Analyse des flags
    flags_to_check = ['flag_faux_nom', 'flag_numero_double', 'flag_pas_forme']
    
    for flag in flags_to_check:
        flagged_count = queryset.filter(**{flag: 1}).count()
        quality_stats["flag_analysis"][flag] = {
            "flagged": flagged_count,
            "rate": round((flagged_count / total * 100), 2)
        }
    
    # Qualité des contacts
    with_phone = queryset.filter(
        Q(telephone1__isnull=False) & Q(telephone1__ne='') |
        Q(telephone2__isnull=False) & Q(telephone2__ne='')
    ).count()
    
    quality_stats["contact_quality"] = {
        "with_phone": with_phone,
        "without_phone": total - with_phone,
        "contact_rate": round((with_phone / total * 100), 2)
    }
    
    return quality_stats


def _calculate_distribution_stats(queryset) -> Dict:
    """Calcule les statistiques de distribution."""
    distribution_stats = {
        "by_prestataire": {},
        "by_beneficiaire": {},
        "by_classe": {},
        "top_combinations": []
    }
    
    try:
        # Distribution par prestataire
        prestataire_stats = queryset.values('prestataire').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        distribution_stats["by_prestataire"] = {
            item['prestataire']: item['count'] for item in prestataire_stats
        }
        
        # Distribution par bénéficiaire
        beneficiaire_stats = queryset.values('beneficiaire').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        distribution_stats["by_beneficiaire"] = {
            item['beneficiaire']: item['count'] for item in beneficiaire_stats
        }
        
        # Distribution par classe
        classe_stats = queryset.values('classe_label').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        distribution_stats["by_classe"] = {
            item['classe_label']: item['count'] for item in classe_stats
        }
        
        # Top combinaisons prestataire+bénéficiaire
        combo_stats = queryset.values('prestataire', 'beneficiaire').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        distribution_stats["top_combinations"] = [
            {
                "prestataire": item['prestataire'],
                "beneficiaire": item['beneficiaire'],
                "count": item['count']
            }
            for item in combo_stats
        ]
    
    except Exception as e:
        logger.error(f"Erreur calcul statistiques distribution: {e}")
    
    return distribution_stats


def invalidate_advanced_stats_cache() -> None:
    """Invalide manuellement le cache de statistiques avancées."""
    _invalidate_cache()
    logger.info("Cache statistiques avancées invalidé manuellement")


def get_cache_health_check() -> Dict:
    """Retourne un état de santé du cache."""
    version = _get_cache_version()
    
    return {
        "cache_version": version,
        "ttl_seconds": ADVANCED_STATS_CACHE_TTL,
        "enabled": True,
        "last_check": timezone.now().isoformat(),
        "cache_keys_count": len([k for k in cache.keys() if ADVANCED_STATS_CACHE_KEY_PREFIX in str(k)])
    }


# Decorator pour invalidation automatique
def invalidate_advanced_cache_on_change(func):
    """Décorateur qui invalide le cache avancé après modification des données."""
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        invalidate_advanced_stats_cache()
        return result
    return wrapper

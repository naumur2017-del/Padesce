"""
Optimisation des requêtes avec bulk processing.

Ce module implémente des optimisations de requêtes pour réduire
le nombre d'appels à la base de données et améliorer les performances.
"""

import hashlib
import logging
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Any

from django.db import transaction
from django.db.models import Count, Q, Prefetch
from django.core.cache import cache

from App_PADESCE.appels.models import Appel, AppelAnswers, SatisfactionApprenant
from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.presences.models import Presence

logger = logging.getLogger(__name__)


class BulkQueryOptimizer:
    """Optimiseur de requêtes bulk pour les performances."""
    
    def __init__(self):
        self.cache_ttl = 15 * 60  # 15 minutes
        self.cache_key_prefix = "bulk_query_optimization"
    
    def get_cache_key(self, operation: str, params: Dict = None) -> str:
        """Génère une clé de cache pour les opérations bulk."""
        if params is None:
            params = {}
        
        # Normaliser les paramètres
        normalized_params = {k: str(v).lower() for k, v in params.items() if v}
        param_string = "|".join(f"{k}:{v}" for k, v in sorted(normalized_params.items()))
        
        hash_object = hashlib.md5(f"{operation}_{param_string}".encode('utf-8'))
        return f"{self.cache_key_prefix}_{operation}_{hash_object.hexdigest()}"
    
    def bulk_get_presence_controls_optimized(self, appel_ids: List[int]) -> Dict[int, Dict]:
        """
        Récupère les contrôles de présence en utilisant une seule requête bulk
        au lieu d'appels individuels.
        
        Args:
            appel_ids: Liste des IDs des appels
            
        Returns:
            Dictionnaire {appel_id: {c1, c2, c3, c4}}
        """
        cache_key = self.get_cache_key("presence_controls", {"appel_ids": ",".join(map(str, sorted(appel_ids)))})
        
        # Vérifier le cache
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Cache hit bulk presence controls: {len(appel_ids)} appels")
            return cached_result
        
        # Requête bulk optimisée
        try:
            with transaction.atomic():
                # Utiliser une seule requête pour récupérer toutes les présences
                presences = Presence.objects.filter(
                    apprenant_id__in=appel_ids
                ).values(
                    'apprenant_id',
                    'c1',
                    'c2', 
                    'c3',
                    'c4'
                )
                
                # Organiser les résultats par appel_id
                result = {}
                for presence in presences:
                    appel_id = presence['apprenant_id']
                    result[appel_id] = {
                        'c1': presence['c1'],
                        'c2': presence['c2'],
                        'c3': presence['c3'],
                        'c4': presence['c4'],
                        'taux_presence_control': self._calculate_presence_rate(presence),
                        'has_participation': any(
                            marker == "PR" for marker in [
                                presence['c1'], presence['c2'], presence['c3'], presence['c4']
                            ]
                        )
                    }
                
                # Mettre en cache
                cache.set(cache_key, result, timeout=self.cache_ttl)
                logger.debug(f"Cache miss bulk presence controls: {len(result)} appels")
                
                return result
                
        except Exception as e:
            logger.error(f"Erreur bulk presence controls: {e}")
            return {}
    
    def _calculate_presence_rate(self, presence: Dict) -> float:
        """Calcule le taux de présence pour un contrôle."""
        markers = [presence['c1'], presence['c2'], presence['c3'], presence['c4']]
        
        # Compter les présences (P) et absences (A)
        presence_count = sum(1 for marker in markers if marker and marker.upper() == 'P')
        total_count = sum(1 for marker in markers if marker and marker.upper() in ['P', 'A'])
        
        if total_count == 0:
            return 0.0
        
        return round((presence_count / total_count) * 100, 2)
    
    def bulk_get_appel_answers_optimized(self, appel_ids: List[int]) -> Dict[int, AppelAnswers]:
        """
        Récupère les réponses d'appels en une seule requête.
        
        Args:
            appel_ids: Liste des IDs des appels
            
        Returns:
            Dictionnaire {appel_id: AppelAnswers}
        """
        cache_key = self.get_cache_key("appel_answers", {"appel_ids": ",".join(map(str, sorted(appel_ids)))})
        
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Cache hit bulk appel answers: {len(appel_ids)} appels")
            return cached_result
        
        try:
            # Requête bulk avec prefetch pour éviter N+1
            answers = AppelAnswers.objects.filter(
                appel_id__in=appel_ids
            ).select_related(
                'modified_by'
            ).prefetch_related(
                Prefetch('appel', queryset=Appel.objects.filter(is_active=True))
            )
            
            # Organiser par appel_id
            result = {answer.appel_id: answer for answer in answers}
            
            cache.set(cache_key, result, timeout=self.cache_ttl)
            logger.debug(f"Cache miss bulk appel answers: {len(result)} appels")
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur bulk appel answers: {e}")
            return {}
    
    def bulk_get_satisfaction_optimized(self, appel_ids: List[int]) -> Dict[int, SatisfactionApprenant]:
        """
        Récupère les satisfactions en une seule requête optimisée.
        """
        cache_key = self.get_cache_key("satisfaction", {"appel_ids": ",".join(map(str, sorted(appel_ids)))})
        
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Cache hit bulk satisfaction: {len(appel_ids)} appels")
            return cached_result
        
        try:
            # Requête bulk avec prefetch optimisé
            satisfactions = SatisfactionApprenant.objects.filter(
                appel_id__in=appel_ids
            ).select_related(
                'enqueteur'
            ).prefetch_related(
                Prefetch('appel', queryset=Appel.objects.filter(is_active=True))
            )
            
            result = {sat.appel_id: sat for sat in satisfactions}
            
            cache.set(cache_key, result, timeout=self.cache_ttl)
            logger.debug(f"Cache miss bulk satisfaction: {len(result)} appels")
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur bulk satisfaction: {e}")
            return {}
    
    def optimize_appel_queryset_with_prefetch(self, base_queryset):
        """
        Optimise le queryset d'appels avec prefetch_related au lieu de select_related massif.
        
        Args:
            base_queryset: Queryset de base des appels
            
        Returns:
            Queryset optimisé avec prefetch_related
        """
        try:
            # Remplacer select_related massif par prefetch_related ciblé
            optimized_queryset = base_queryset.filter(is_active=True).prefetch_related(
                Prefetch('classe', queryset=Appel.objects.none()),
                Prefetch('answers', queryset=AppelAnswers.objects.all()),
                Prefetch('satisfaction_apprenant', queryset=SatisfactionApprenant.objects.all()),
                Prefetch('answers__modified_by', queryset=Appel.objects.none()),
                Prefetch('satisfaction_apprenant__enqueteur', queryset=Appel.objects.none()),
            )
            
            logger.debug("Queryset optimisé avec prefetch_related")
            return optimized_queryset
            
        except Exception as e:
            logger.error(f"Erreur optimisation queryset: {e}")
            return base_queryset
    
    def bulk_match_apprenants_optimized(self, appels: List[Appel]) -> Dict[int, Apprenant]:
        """
        Version optimisée du matching apprenants-appels.
        
        Args:
            appels: Liste des appels à matcher
            
        Returns:
            Dictionnaire {appel_id: Apprenant}
        """
        if not appels:
            return {}
        
        # Extraire les critères de recherche
        search_criteria = []
        for appel in appels:
            criteria = {
                'appel_id': appel.id,
                'nom': appel.nom,
                'telephone1': appel.telephone1,
                'telephone2': appel.telephone2,
                'prestataire': appel.prestataire,
                'beneficiaire': appel.beneficiaire,
            }
            search_criteria.append(criteria)
        
        cache_key = self.get_cache_key("apprenant_matching", {
            "criteria_count": len(search_criteria),
            "first_nom": search_criteria[0]['nom'] if search_criteria else "",
        })
        
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Cache hit bulk apprenant matching: {len(appels)} appels")
            return cached_result
        
        try:
            # Requête bulk pour tous les apprenants potentiels
            all_phone_numbers = []
            all_names = []
            
            for criteria in search_criteria:
                if criteria['telephone1']:
                    all_phone_numbers.append(criteria['telephone1'])
                if criteria['telephone2']:
                    all_phone_numbers.append(criteria['telephone2'])
                if criteria['nom']:
                    all_names.append(criteria['nom'])
            
            # Requête unique pour tous les apprenants
            apprenants = Apprenant.objects.filter(
                Q(telephone1__in=all_phone_numbers) |
                Q(telephone2__in=all_phone_numbers) |
                Q(nom_complet__in=all_names)
            ).values(
                'id',
                'nom_complet',
                'telephone1',
                'telephone2',
                'prestataire',
                'beneficiaire'
            )
            
            # Créer un index de recherche
            apprenant_index = defaultdict(list)
            for apprenant in apprenants:
                apprenant_index[apprenant['id']] = apprenant
            
            # Matcher les appels avec les apprenants
            result = {}
            for criteria in search_criteria:
                matched_apprenant = self._find_best_match(criteria, apprenant_index)
                if matched_apprenant:
                    result[criteria['appel_id']] = matched_apprenant
            
            cache.set(cache_key, result, timeout=self.cache_ttl)
            logger.debug(f"Cache miss bulk apprenant matching: {len(result)} matchs")
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur bulk apprenant matching: {e}")
            return {}
    
    def _find_best_match(self, criteria: Dict, apprenant_index: Dict) -> Dict:
        """Trouve le meilleur apprenant correspondant aux critères."""
        matches = []
        
        for apprenant_id, apprenant in apprenant_index.items():
            score = 0
            
            # Score pour le nom
            if criteria['nom'] and apprenant['nom_complet']:
                if criteria['nom'].lower() in apprenant['nom_complet'].lower():
                    score += 3
                elif apprenant['nom_complet'].lower() in criteria['nom'].lower():
                    score += 2
            
            # Score pour les téléphones
            if criteria['telephone1']:
                if criteria['telephone1'] == apprenant['telephone1']:
                    score += 5
                elif criteria['telephone1'] == apprenant['telephone2']:
                    score += 3
            
            if criteria['telephone2']:
                if criteria['telephone2'] == apprenant['telephone2']:
                    score += 3
                elif criteria['telephone2'] == apprenant['telephone1']:
                    score += 2
            
            # Score pour prestataire/bénéficiaire
            if criteria['prestataire'] and apprenant['prestataire']:
                if criteria['prestataire'].lower() == apprenant['prestataire'].lower():
                    score += 2
            
            if criteria['beneficiaire'] and apprenant['beneficiaire']:
                if criteria['beneficiaire'].lower() == apprenant['beneficiaire'].lower():
                    score += 2
            
            if score > 0:
                matches.append((score, apprenant))
        
        # Retourner le meilleur match
        if matches:
            matches.sort(key=lambda x: x[0], reverse=True)
            return matches[0][1]
        
        return {}
    
    def invalidate_bulk_cache(self, operation: str = None):
        """Invalide le cache bulk pour une opération spécifique ou tout."""
        if operation:
            # Invalider seulement une opération spécifique
            keys_pattern = f"{self.cache_key_prefix}_{operation}_*"
            try:
                cache_keys = cache.keys(keys_pattern)
                for key in cache_keys:
                    cache.delete(key)
                logger.info(f"Cache bulk invalidé pour l'opération: {operation}")
            except Exception:
                # Fallback: vider tout le cache
                cache.clear()
                logger.info("Cache bulk entièrement vidé (fallback)")
        else:
            # Invalider tout le cache bulk
            try:
                keys_pattern = f"{self.cache_key_prefix}_*"
                cache_keys = cache.keys(keys_pattern)
                for key in cache_keys:
                    cache.delete(key)
                logger.info("Cache bulk entièrement invalidé")
            except Exception:
                cache.clear()
                logger.info("Cache bulk entièrement vidé (fallback)")
    
    def get_bulk_cache_stats(self) -> Dict:
        """Retourne des statistiques sur le cache bulk."""
        try:
            keys_pattern = f"{self.cache_key_prefix}_*"
            cache_keys = cache.keys(keys_pattern)
            
            stats = {
                'total_cached_operations': len(cache_keys),
                'operations': defaultdict(int),
                'cache_health': 'healthy'
            }
            
            for key in cache_keys:
                key_str = str(key)
                if '_presence_controls_' in key_str:
                    stats['operations']['presence_controls'] += 1
                elif '_appel_answers_' in key_str:
                    stats['operations']['appel_answers'] += 1
                elif '_satisfaction_' in key_str:
                    stats['operations']['satisfaction'] += 1
                elif '_apprenant_matching_' in key_str:
                    stats['operations']['apprenant_matching'] += 1
            
            if stats['total_cached_operations'] > 100:
                stats['cache_health'] = 'warning'
            elif stats['total_cached_operations'] > 500:
                stats['cache_health'] = 'critical'
            
            return stats
            
        except Exception as e:
            logger.error(f"Erreur statistiques cache bulk: {e}")
            return {'error': str(e)}


# Instance globale de l'optimiseur
bulk_optimizer = BulkQueryOptimizer()


def get_bulk_presence_controls(appel_ids: List[int]) -> Dict[int, Dict]:
    """Wrapper pour l'accès au bulk optimizer."""
    return bulk_optimizer.bulk_get_presence_controls_optimized(appel_ids)


def get_bulk_appel_answers(appel_ids: List[int]) -> Dict[int, AppelAnswers]:
    """Wrapper pour l'accès au bulk optimizer."""
    return bulk_optimizer.bulk_get_appel_answers_optimized(appel_ids)


def get_bulk_satisfaction(appel_ids: List[int]) -> Dict[int, SatisfactionApprenant]:
    """Wrapper pour l'accès au bulk optimizer."""
    return bulk_optimizer.bulk_get_satisfaction_optimized(appel_ids)


def optimize_appel_queryset(base_queryset):
    """Wrapper pour l'optimisation de queryset."""
    return bulk_optimizer.optimize_appel_queryset_with_prefetch(base_queryset)


def bulk_match_apprenants(appels: List[Appel]) -> Dict[int, Apprenant]:
    """Wrapper pour le matching bulk d'apprenants."""
    return bulk_optimizer.bulk_match_apprenants_optimized(appels)


def invalidate_bulk_cache(operation: str = None):
    """Wrapper pour l'invalidation du cache bulk."""
    bulk_optimizer.invalidate_bulk_cache(operation)


def get_bulk_cache_stats() -> Dict:
    """Wrapper pour les statistiques du cache bulk."""
    return bulk_optimizer.get_bulk_cache_stats()

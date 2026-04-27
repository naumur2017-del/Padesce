"""
Module de monitoring et A/B testing pour les optimisations.

Ce module fournit des outils pour mesurer les performances,
comparer les différentes stratégies de cache et générer des rapports.
"""

import time
import logging
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from functools import wraps
from collections import defaultdict

from django.core.cache import cache
from django.db import connection
from django.conf import settings

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Moniteur de performance avec A/B testing."""
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self.experiments = {}
        self.start_time = None
        self.request_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
    
    def start_timing(self, operation: str) -> str:
        """Démarre le chronométrage pour une opération."""
        timing_id = f"{operation}_{int(time.time())}"
        self.start_time = time.time()
        return timing_id
    
    def end_timing(self, timing_id: str, metadata: Dict = None) -> float:
        """Termine le chronométrage et enregistre la métrique."""
        if self.start_time is None:
            return 0.0
        
        duration = time.time() - self.start_time
        
        metric = {
            'timestamp': datetime.now().isoformat(),
            'duration': duration,
            'operation': timing_id.split('_')[0],
            'metadata': metadata or {}
        }
        
        self.metrics[timing_id.split('_')[0]].append(metric)
        self.start_time = None
        
        return duration
    
    def record_cache_hit(self, cache_type: str):
        """Enregistre un cache hit."""
        self.cache_hits += 1
        logger.debug(f"Cache hit: {cache_type}")
    
    def record_cache_miss(self, cache_type: str):
        """Enregistre un cache miss."""
        self.cache_misses += 1
        logger.debug(f"Cache miss: {cache_type}")
    
    def get_cache_hit_rate(self) -> float:
        """Calcule le taux de cache hit."""
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return (self.cache_hits / total) * 100
    
    def get_performance_stats(self, operation: str = None) -> Dict:
        """Retourne les statistiques de performance."""
        if operation:
            if operation not in self.metrics:
                return {'error': f'No metrics for operation: {operation}'}
            
            durations = [m['duration'] for m in self.metrics[operation]]
            if not durations:
                return {'error': f'No duration data for operation: {operation}'}
            
            return {
                'operation': operation,
                'count': len(durations),
                'avg_duration': statistics.mean(durations),
                'min_duration': min(durations),
                'max_duration': max(durations),
                'median_duration': statistics.median(durations),
                'std_deviation': statistics.stdev(durations) if len(durations) > 1 else 0,
                'total_duration': sum(durations),
                'cache_hit_rate': self.get_cache_hit_rate()
            }
        
        # Statistiques globales
        all_stats = {}
        for op_name, metrics in self.metrics.items():
            if metrics:
                durations = [m['duration'] for m in metrics]
                all_stats[op_name] = {
                    'count': len(durations),
                    'avg_duration': statistics.mean(durations),
                    'min_duration': min(durations),
                    'max_duration': max(durations),
                    'median_duration': statistics.median(durations),
                    'std_deviation': statistics.stdev(durations) if len(durations) > 1 else 0,
                    'total_duration': sum(durations)
                }
        
        return {
            'global_stats': all_stats,
            'cache_stats': {
                'hits': self.cache_hits,
                'misses': self.cache_misses,
                'hit_rate': self.get_cache_hit_rate()
            },
            'total_operations': sum(len(metrics) for metrics in self.metrics.values())
        }
    
    def reset_metrics(self):
        """Réinitialise toutes les métriques."""
        self.metrics.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        logger.info("Métriques de performance réinitialisées")


# Instance globale du moniteur
performance_monitor = PerformanceMonitor()


def monitor_performance(operation: str = None, metadata: Dict = None):
    """
    Décorateur pour monitorer la performance d'une fonction.
    
    Usage:
        @monitor_performance('dashboard_load', {'user_id': request.user.id})
        def my_function():
            # Code à monitorer
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            timing_id = performance_monitor.start_timing(operation or func.__name__)
            
            try:
                result = func(*args, **kwargs)
                
                # Vérifier si le résultat vient du cache
                if hasattr(result, '_from_cache'):
                    if result._from_cache:
                        performance_monitor.record_cache_hit(operation or func.__name__)
                    else:
                        performance_monitor.record_cache_miss(operation or func.__name__)
                
                return result
                
            except Exception as e:
                performance_monitor.end_timing(timing_id, {'error': str(e)})
                raise
        
        return wrapper
    return decorator


def ab_test(experiment_name: str, control_group: str = 'control'):
    """
    Décorateur pour A/B testing.
    
    Args:
        experiment_name: Nom de l'expérience
        control_group: Groupe de contrôle ('control', 'variant_a', 'variant_b')
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Déterminer le groupe pour cette requête
            group = kwargs.get('_ab_group', control_group)
            
            # Enregistrer l'expérience
            if experiment_name not in performance_monitor.experiments:
                performance_monitor.experiments[experiment_name] = {
                    'name': experiment_name,
                    'start_time': datetime.now().isoformat(),
                    'groups': defaultdict(list)
                }
            
            performance_monitor.experiments[experiment_name]['groups'][group].append({
                'timestamp': datetime.now().isoformat(),
                'function': func.__name__,
                'args_count': len(args),
                'kwargs_keys': list(kwargs.keys())
            })
            
            # Ajouter le groupe au contexte
            kwargs['_ab_experiment'] = experiment_name
            kwargs['_ab_group'] = group
            
            timing_id = performance_monitor.start_timing(f"ab_{experiment_name}_{group}")
            
            try:
                result = func(*args, **kwargs)
                duration = performance_monitor.end_timing(timing_id, {
                    'experiment': experiment_name,
                    'group': group
                })
                
                return result
                
            except Exception as e:
                performance_monitor.end_timing(timing_id, {
                    'experiment': experiment_name,
                    'group': group,
                    'error': str(e)
                })
                raise
        
        return wrapper
    return decorator


class DatabaseQueryMonitor:
    """Moniteur spécifique pour les requêtes base de données."""
    
    def __init__(self):
        self.query_stats = defaultdict(list)
        self.slow_queries = []
        self.slow_query_threshold = 1.0  # 1 seconde
    
    def log_query(self, sql: str, duration: float, params: Tuple = None):
        """Enregistre une requête SQL."""
        query_info = {
            'timestamp': datetime.now().isoformat(),
            'sql': sql[:200] + '...' if len(sql) > 200 else sql,
            'duration': duration,
            'params': str(params)[:100] if params else None,
            'is_slow': duration > self.slow_query_threshold
        }
        
        # Identifier le type de requête pour le regroupement
        query_lower = sql.lower()
        if 'select' in query_lower:
            if 'from appels_appel' in query_lower:
                query_type = 'dashboard_select'
            elif 'from apprenants_apprenant' in query_lower:
                query_type = 'apprenant_select'
            else:
                query_type = 'other_select'
        elif 'insert' in query_lower:
            query_type = 'insert'
        elif 'update' in query_lower:
            query_type = 'update'
        elif 'delete' in query_lower:
            query_type = 'delete'
        else:
            query_type = 'other'
        
        self.query_stats[query_type].append(query_info)
        
        if duration > self.slow_query_threshold:
            self.slow_queries.append(query_info)
            logger.warning(f"Requête lente détectée: {duration:.2f}s - {sql[:100]}...")
    
    def get_query_stats(self) -> Dict:
        """Retourne les statistiques des requêtes."""
        stats = {}
        
        for query_type, queries in self.query_stats.items():
            if queries:
                durations = [q['duration'] for q in queries]
                stats[query_type] = {
                    'count': len(queries),
                    'avg_duration': statistics.mean(durations),
                    'min_duration': min(durations),
                    'max_duration': max(durations),
                    'total_duration': sum(durations),
                    'slow_queries': len([q for q in queries if q['is_slow']])
                }
        
        return {
            'query_stats': stats,
            'slow_queries': self.slow_queries[-10:],  # 10 dernières requêtes lentes
            'total_queries': sum(len(queries) for queries in self.query_stats.values()),
            'slow_query_threshold': self.slow_query_threshold
        }


# Instance globale du moniteur de requêtes
query_monitor = DatabaseQueryMonitor()


def generate_performance_report() -> Dict:
    """Génère un rapport de performance complet."""
    logger.info("Génération du rapport de performance...")
    
    # Statistiques de performance
    perf_stats = performance_monitor.get_performance_stats()
    
    # Statistiques des requêtes
    query_stats = query_monitor.get_query_stats()
    
    # Statistiques des expériences A/B
    ab_results = {}
    for exp_name, exp_data in performance_monitor.experiments.items():
        total_participants = sum(len(group) for group in exp_data['groups'].values())
        ab_results[exp_name] = {
            'name': exp_data['name'],
            'start_time': exp_data['start_time'],
            'total_participants': total_participants,
            'groups': {group: len(participants) for group, participants in exp_data['groups'].items()}
        }
    
    # Statistiques du cache
    cache_stats = performance_monitor.get_cache_hit_rate()
    
    # Recommandations
    recommendations = []
    
    # Analyser les performances
    for operation, stats in perf_stats.get('global_stats', {}).items():
        if stats['avg_duration'] > 2.0:  # 2 secondes
            recommendations.append({
                'type': 'performance',
                'priority': 'high',
                'operation': operation,
                'message': f"Opération {operation} lente: {stats['avg_duration']:.2f}s en moyenne",
                'suggestion': 'Considérer l\'optimisation ou le cache'
            })
    
    # Analyser les requêtes lentes
    slow_query_count = len(query_stats.get('slow_queries', []))
    if slow_query_count > 5:
        recommendations.append({
            'type': 'database',
            'priority': 'high',
            'message': f"{slow_query_count} requêtes lentes détectées",
            'suggestion': 'Optimiser les indexes ou revoir les requêtes'
        })
    
    # Analyser le taux de cache
    if cache_stats < 70:  # Moins de 70% de cache hits
        recommendations.append({
            'type': 'cache',
            'priority': 'medium',
            'message': f"Taux de cache bas: {cache_stats:.1f}%",
            'suggestion': 'Augmenter les TTL ou améliorer les stratégies de cache'
        })
    
    return {
        'timestamp': datetime.now().isoformat(),
        'performance_stats': perf_stats,
        'query_stats': query_stats,
        'ab_test_results': ab_results,
        'cache_hit_rate': cache_stats,
        'recommendations': recommendations,
        'summary': {
            'total_operations': perf_stats.get('total_operations', 0),
            'total_queries': query_stats.get('total_queries', 0),
            'slow_queries': slow_query_count,
            'avg_response_time': statistics.mean([
                stats.get('avg_duration', 0) 
                for stats in perf_stats.get('global_stats', {}).values()
            ]) if perf_stats.get('global_stats') else 0,
            'cache_efficiency': cache_stats
        }
    }


def reset_performance_monitoring():
    """Réinitialise tous les moniteurs de performance."""
    performance_monitor.reset_metrics()
    query_monitor = DatabaseQueryMonitor()  # Réinitialiser l'instance
    
    logger.info("Monitoring de performance réinitialisé")


def get_real_time_metrics() -> Dict:
    """Retourne des métriques en temps réel."""
    return {
        'current_cache_hit_rate': performance_monitor.get_cache_hit_rate(),
        'recent_operations': list(performance_monitor.metrics.items())[-5:],
        'active_experiments': list(performance_monitor.experiments.keys()),
        'slow_queries_count': len(query_monitor.slow_queries)
    }


# Context processor pour Django templates
def performance_context(request):
    """Ajoute les métriques de performance au contexte des templates."""
    return {
        'performance_monitor': {
            'cache_hit_rate': performance_monitor.get_cache_hit_rate(),
            'total_operations': performance_monitor.request_count,
            'slow_queries_count': len(query_monitor.slow_queries),
            'active_experiments': list(performance_monitor.experiments.keys())
        }
    }


# Middleware pour le monitoring automatique
class PerformanceMonitoringMiddleware:
    """Middleware Django pour le monitoring automatique des performances."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        start_time = time.time()
        
        response = self.get_response(request)
        
        # Calculer la durée
        duration = time.time() - start_time
        
        # Enregistrer la métrique
        performance_monitor.request_count += 1
        
        # Ajouter les headers de performance pour le débogage
        if settings.DEBUG:
            response['X-Response-Time'] = str(duration)
            response['X-Cache-Hit-Rate'] = str(performance_monitor.get_cache_hit_rate())
        
        return response


def setup_performance_monitoring():
    """Configure le monitoring de performance."""
    logger.info("Configuration du monitoring de performance...")
    
    # Activer le monitoring des requêtes si en mode DEBUG
    if settings.DEBUG:
        # Configuration du logging des requêtes lentes
        from django.conf import settings
        
        # Ajouter les handlers de logging
        if not any(isinstance(handler, logging.FileHandler) for handler in logger.handlers):
            file_handler = logging.FileHandler('performance_queries.log')
            file_handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        logger.info("Monitoring de performance configuré")

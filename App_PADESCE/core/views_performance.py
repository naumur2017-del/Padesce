"""
Views pour le monitoring et les rapports de performance.

Ces vues fournissent des interfaces pour visualiser les métriques
de performance, les statistiques de cache et les rapports A/B testing.
"""

import logging
from datetime import datetime, timedelta
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET

from App_PADESCE.core.performance_monitor import (
    generate_performance_report,
    get_real_time_metrics,
    reset_performance_monitoring
)
from App_PADESCE.core.database_indexes import check_index_status
from App_PADESCE.core.bulk_query_optimizer import get_bulk_cache_stats
from App_PADESCE.core.advanced_dashboard_cache import get_cache_health_check
from App_PADESCE.core.template_cache_utils import get_template_cache_stats

logger = logging.getLogger(__name__)


@login_required
@require_GET
def performance_dashboard(request):
    """
    Vue principale du dashboard de performance.
    
    Affiche les métriques en temps réel, les statistiques de cache,
    et les recommandations d'optimisation.
    """
    try:
        # Métriques en temps réel
        real_time_metrics = get_real_time_metrics()
        
        # Statistiques des caches
        bulk_cache_stats = get_bulk_cache_stats()
        advanced_cache_health = get_cache_health_check()
        template_cache_stats = get_template_cache_stats()
        
        # Statistiques des indexes
        index_status = check_index_status()
        
        # Rapport de performance
        performance_report = generate_performance_report()
        
        context = {
            'page_title': 'Dashboard Performance',
            'real_time_metrics': real_time_metrics,
            'bulk_cache_stats': bulk_cache_stats,
            'advanced_cache_health': advanced_cache_health,
            'template_cache_stats': template_cache_stats,
            'index_status': index_status,
            'performance_report': performance_report,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        
        return render(request, 'core/performance_dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Erreur dashboard performance: {e}")
        return render(request, 'core/performance_error.html', {
            'error': str(e),
            'page_title': 'Erreur Performance'
        })


@login_required
@require_GET
def performance_api_metrics(request):
    """
    API pour récupérer les métriques de performance en temps réel.
    
    Retourne les données au format JSON pour les graphiques
    et les dashboards externes.
    """
    try:
        real_time_metrics = get_real_time_metrics()
        bulk_cache_stats = get_bulk_cache_stats()
        advanced_cache_health = get_cache_health_check()
        
        return JsonResponse({
            'success': True,
            'data': {
                'real_time_metrics': real_time_metrics,
                'bulk_cache_stats': bulk_cache_stats,
                'advanced_cache_health': advanced_cache_health,
                'timestamp': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Erreur API métriques: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_GET
def performance_api_history(request):
    """
    API pour récupérer l'historique des performances.
    
    Paramètres:
    - hours: Nombre d'heures d'historique (défaut: 24)
    - operation: Opération spécifique à filtrer
    """
    try:
        from App_PADESCE.core.performance_monitor import performance_monitor
        
        hours = int(request.GET.get('hours', 24))
        operation = request.GET.get('operation')
        
        # Récupérer l'historique des métriques
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Filtrer par opération si spécifiée
        if operation:
            if operation in performance_monitor.metrics:
                metrics = performance_monitor.metrics[operation]
            else:
                metrics = []
        else:
            # Retourner toutes les opérations
            metrics = []
            for op_name, op_metrics in performance_monitor.metrics.items():
                for metric in op_metrics:
                    metric['operation'] = op_name
                    metrics.append(metric)
        
        # Filtrer par date
        filtered_metrics = [
            metric for metric in metrics
            if datetime.fromisoformat(metric['timestamp']) >= cutoff_time
        ]
        
        # Grouper par opération
        history = {}
        for metric in filtered_metrics:
            op_name = metric['operation']
            if op_name not in history:
                history[op_name] = []
            history[op_name].append({
                'timestamp': metric['timestamp'],
                'duration': metric['duration'],
                'metadata': metric.get('metadata', {})
            })
        
        return JsonResponse({
            'success': True,
            'data': {
                'history': history,
                'hours': hours,
                'operation': operation,
                'total_records': len(filtered_metrics)
            }
        })
        
    except Exception as e:
        logger.error(f"Erreur API historique: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_GET
def performance_api_ab_tests(request):
    """
    API pour récupérer les résultats des tests A/B.
    
    Retourne les données des expériences en cours avec
    les statistiques de performance par groupe.
    """
    try:
        from App_PADESCE.core.performance_monitor import performance_monitor
        
        if not hasattr(performance_monitor, 'experiments'):
            return JsonResponse({
                'success': True,
                'data': {
                    'experiments': {},
                    'message': 'Aucun test A/B en cours'
                }
            })
        
        # Analyser les résultats des expériences
        experiments_data = {}
        for exp_name, exp_data in performance_monitor.experiments.items():
            experiments_data[exp_name] = {
                'name': exp_data['name'],
                'start_time': exp_data['start_time'],
                'groups': {}
            }
            
            for group_name, participants in exp_data['groups'].items():
                # Calculer les statistiques de performance pour ce groupe
                group_metrics = []
                for participant in participants:
                    # Trouver les métriques correspondantes
                    participant_metrics = []
                    for op_name, op_metrics in performance_monitor.metrics.items():
                        for metric in op_metrics:
                            if (metric.get('metadata', {}).get('experiment') == exp_name and
                                metric.get('metadata', {}).get('group') == group_name):
                                participant_metrics.append(metric)
                    
                    if participant_metrics:
                        avg_duration = sum(m['duration'] for m in participant_metrics) / len(participant_metrics)
                        group_metrics.append({
                            'participant_count': len(participant_metrics),
                            'avg_duration': avg_duration,
                            'min_duration': min(m['duration'] for m in participant_metrics),
                            'max_duration': max(m['duration'] for m in participant_metrics)
                        })
                
                experiments_data[exp_name]['groups'][group_name] = {
                    'participant_count': len(participants),
                    'metrics': group_metrics
                }
        
        return JsonResponse({
            'success': True,
            'data': {
                'experiments': experiments_data,
                'total_experiments': len(performance_monitor.experiments)
            }
        })
        
    except Exception as e:
        logger.error(f"Erreur API A/B tests: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_GET
def performance_api_database(request):
    """
    API pour récupérer les statistiques de la base de données.
    
    Retourne les informations sur les indexes, les requêtes lentes,
    et l'utilisation des ressources.
    """
    try:
        from App_PADESCE.core.database_indexes import analyze_database_indexes
        
        # Analyser la base de données
        analysis = analyze_database_indexes()
        
        return JsonResponse({
            'success': True,
            'data': {
                'index_analysis': analysis,
                'recommendations': analysis.get('recommendations', []),
                'unused_indexes': analysis.get('analysis', {}).get('unused_indexes', [])
            }
        })
        
    except Exception as e:
        logger.error(f"Erreur API base de données: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def performance_reset_metrics(request):
    """
    Vue pour réinitialiser les métriques de performance.
    
    Accessible uniquement aux superutilisateurs.
    """
    try:
        reset_type = request.POST.get('reset_type', 'all')
        
        if reset_type == 'all':
            reset_performance_monitoring()
            message = "Toutes les métriques ont été réinitialisées"
        elif reset_type == 'experiments':
            from App_PADESCE.core.performance_monitor import performance_monitor
            performance_monitor.experiments.clear()
            message = "Les expériences A/B ont été réinitialisées"
        else:
            message = "Type de réinitialisation non reconnu"
        
        return JsonResponse({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        logger.error(f"Erreur réinitialisation métriques: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_GET
def performance_export_report(request):
    """
    Exporte le rapport de performance au format CSV.
    
    Paramètres:
    - format: Format d'export (csv, json)
    - hours: Nombre d'heures d'historique
    """
    try:
        export_format = request.GET.get('format', 'csv')
        hours = int(request.GET.get('hours', 24))
        
        # Récupérer le rapport
        report = generate_performance_report()
        
        if export_format == 'json':
            response = JsonResponse(report, json_dumps_params={'indent': 2})
            response['Content-Disposition'] = f'attachment; filename="performance_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json"'
            return response
        
        elif export_format == 'csv':
            import csv
            from django.http import HttpResponse
            
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="performance_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
            
            writer = csv.writer(response)
            
            # En-tête CSV
            writer.writerow([
                'Timestamp', 'Operation', 'Duration', 'Cache Hit Rate', 
                'Metadata', 'Error'
            ])
            
            # Données du rapport
            for operation, stats in report.get('performance_stats', {}).items():
                if operation != 'global_stats':
                    for metric in stats:
                        writer.writerow([
                            metric.get('timestamp', ''),
                            operation,
                            metric.get('duration', ''),
                            metric.get('cache_hit_rate', ''),
                            str(metric.get('metadata', {})),
                            metric.get('error', '')
                        ])
            
            return response
        
        else:
            return JsonResponse({
                'success': False,
                'error': f'Format non supporté: {export_format}'
            }, status=400)
        
    except Exception as e:
        logger.error(f"Erreur export rapport: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

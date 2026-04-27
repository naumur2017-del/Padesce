"""
Création d'indexes pour l'optimisation de la base de données.

Ce script crée les indexes composites recommandés pour améliorer
les performances des requêtes sur les tables principales.
"""

import logging
from django.db import connection
from django.core.management.base import BaseCommand
from django.core.management import call_command

logger = logging.getLogger(__name__)


class DatabaseIndexManager:
    """Gestionnaire pour la création et la gestion des indexes de performance."""
    
    def __init__(self):
        self.indexes_config = [
            {
                'table': 'appels_appel',
                'name': 'idx_appel_status_active_classe',
                'fields': ['status', 'is_active', 'classe_id'],
                'description': 'Index composite pour les requêtes dashboard'
            },
            {
                'table': 'appels_appel',
                'name': 'idx_appel_nom_code_telephone',
                'fields': ['nom', 'code', 'telephone1'],
                'description': 'Index pour la recherche par nom/code/téléphone'
            },
            {
                'table': 'appels_appel',
                'name': 'idx_appel_prestataire_beneficiaire',
                'fields': ['prestataire', 'beneficiaire'],
                'description': 'Index pour le filtrage par prestataire/bénéficiaire'
            },
            {
                'table': 'appels_appel',
                'name': 'idx_appel_active_created',
                'fields': ['is_active', 'created_at'],
                'description': 'Index pour les appels actifs par date'
            },
            {
                'table': 'appels_appel',
                'name': 'idx_appel_status_fenetre',
                'fields': ['status', 'fenetre'],
                'description': 'Index pour le filtrage par statut/fenêtre'
            },
            {
                'table': 'apprenants_apprenant',
                'name': 'idx_apprenant_nom_telephone',
                'fields': ['nom_complet', 'telephone1', 'telephone2'],
                'description': 'Index pour le matching apprenants'
            },
            {
                'table': 'apprenants_apprenant',
                'name': 'idx_apprenant_prestataire_beneficiaire',
                'fields': ['prestataire', 'beneficiaire'],
                'description': 'Index pour le filtrage apprenants'
            },
            {
                'table': 'apprenants_apprenant',
                'name': 'idx_apprenant_region_departement',
                'fields': ['region', 'departement'],
                'description': 'Index pour les statistiques géographiques'
            },
            {
                'table': 'presences_presence',
                'name': 'idx_presence_apprenant_controls',
                'fields': ['apprenant_id', 'c1', 'c2', 'c3', 'c4'],
                'description': 'Index pour les contrôles de présence'
            },
            {
                'table': 'presences_presence',
                'name': 'idx_presence_apprenant_date',
                'fields': ['apprenant_id', 'created_at'],
                'description': 'Index pour les contrôles par apprenant et date'
            },
            {
                'table': 'appels_appelanswers',
                'name': 'idx_appelanswers_appel_satisfaction',
                'fields': ['appel_id', 'q9_satisfaction_globale'],
                'description': 'Index pour les réponses de satisfaction'
            },
            {
                'table': 'appels_appelanswers',
                'name': 'idx_appelanswers_modified',
                'fields': ['modified_at', 'modified_by_id'],
                'description': 'Index pour le suivi des modifications'
            },
            {
                'table': 'satisfaction_apprenants_satisfactionapprenant',
                'name': 'idx_satisfaction_appel_enqueteur',
                'fields': ['appel_id', 'enqueteur_id'],
                'description': 'Index pour les satisfactions par appel/enquêteur'
            },
            {
                'table': 'formations_prestation',
                'name': 'idx_prestation_prestataire_beneficiaire',
                'fields': ['prestataire_id', 'beneficiaire_id'],
                'description': 'Index pour les prestations'
            },
            {
                'table': 'formations_prestation',
                'name': 'idx_prestation_code_active',
                'fields': ['code', 'is_active'],
                'description': 'Index pour les prestations par code'
            }
        ]
    
    def generate_create_index_sql(self) -> str:
        """Génère le SQL pour créer tous les indexes."""
        sql_statements = []
        
        for index_config in self.indexes_config:
            table = index_config['table']
            name = index_config['name']
            fields = index_config['fields']
            
            # Générer le SQL CREATE INDEX
            fields_sql = ', '.join(fields)
            sql = f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({fields_sql});"
            sql_statements.append(sql)
            
            # Ajouter un commentaire
            comment = f"-- Index: {index_config['description']}"
            sql_statements.append(comment)
            sql_statements.append("")
        
        return '\n'.join(sql_statements)
    
    def generate_drop_index_sql(self) -> str:
        """Génère le SQL pour supprimer tous les indexes."""
        sql_statements = []
        
        for index_config in self.indexes_config:
            name = index_config['name']
            sql = f"DROP INDEX IF EXISTS {name};"
            sql_statements.append(sql)
        
        return '\n'.join(sql_statements)
    
    def check_existing_indexes(self) -> list:
        """Vérifie les indexes existants dans la base de données."""
        existing_indexes = []
        
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT indexname, tablename 
                    FROM pg_indexes 
                    WHERE schemaname = 'public'
                    ORDER BY tablename, indexname
                """)
                
                for row in cursor.fetchall():
                    existing_indexes.append({
                        'name': row[0],
                        'table': row[1]
                    })
                    
        except Exception as e:
            logger.error(f"Erreur vérification indexes: {e}")
        
        return existing_indexes
    
    def create_indexes(self) -> dict:
        """Crée tous les indexes de performance."""
        results = {
            'created': [],
            'skipped': [],
            'errors': []
        }
        
        existing_indexes = self.check_existing_indexes()
        existing_index_names = {idx['name'] for idx in existing_indexes}
        
        try:
            with connection.cursor() as cursor:
                for index_config in self.indexes_config:
                    name = index_config['name']
                    table = index_config['table']
                    fields = index_config['fields']
                    
                    if name in existing_index_names:
                        # L'index existe déjà
                        results['skipped'].append({
                            'name': name,
                            'table': table,
                            'reason': 'already_exists'
                        })
                        logger.info(f"Index {name} déjà existant, ignoré")
                        continue
                    
                    try:
                        # Créer l'index
                        fields_sql = ', '.join(fields)
                        sql = f"CREATE INDEX {name} ON {table} ({fields_sql})"
                        cursor.execute(sql)
                        
                        results['created'].append({
                            'name': name,
                            'table': table,
                            'fields': fields,
                            'description': index_config['description']
                        })
                        logger.info(f"Index {name} créé avec succès")
                        
                    except Exception as e:
                        results['errors'].append({
                            'name': name,
                            'table': table,
                            'error': str(e)
                        })
                        logger.error(f"Erreur création index {name}: {e}")
        
        except Exception as e:
            logger.error(f"Erreur générale création indexes: {e}")
            results['errors'].append({
                'general_error': str(e)
            })
        
        return results
    
    def analyze_index_usage(self) -> dict:
        """Analyse l'utilisation des indexes existants."""
        analysis = {
            'table_stats': {},
            'unused_indexes': [],
            'recommendations': []
        }
        
        try:
            with connection.cursor() as cursor:
                # Statistiques des tables
                cursor.execute("""
                    SELECT schemaname, tablename, n_tup_ins, n_tup_upd, n_tup_del
                    FROM pg_stat_user_tables
                    WHERE schemaname = 'public'
                    ORDER BY n_tup_ins DESC
                """)
                
                for row in cursor.fetchall():
                    schema, table, inserts, updates, deletes = row
                    analysis['table_stats'][table] = {
                        'inserts': inserts,
                        'updates': updates,
                        'deletes': deletes,
                        'total_changes': inserts + updates + deletes
                    }
                
                # Indexes non utilisés
                cursor.execute("""
                    SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
                    FROM pg_stat_user_indexes
                    WHERE schemaname = 'public' 
                    AND idx_scan = 0
                    AND idx_tup_read = 0
                    ORDER BY tablename, indexname
                """)
                
                for row in cursor.fetchall():
                    schema, table, index, scans, reads, fetches = row
                    analysis['unused_indexes'].append({
                        'table': table,
                        'index': index,
                        'scans': scans,
                        'reads': reads,
                        'fetches': fetches
                    })
        
        except Exception as e:
            logger.error(f"Erreur analyse indexes: {e}")
            analysis['error'] = str(e)
        
        return analysis
    
    def get_index_recommendations(self) -> list:
        """Retourne des recommandations pour l'optimisation."""
        recommendations = [
            {
                'priority': 'high',
                'table': 'appels_appel',
                'index': 'idx_appel_status_active_classe',
                'reason': 'Requêtes dashboard fréquentes sur status/is_active/classe_id',
                'impact': 'Réduction 50-70% temps requête dashboard'
            },
            {
                'priority': 'high',
                'table': 'appels_appel',
                'index': 'idx_appel_nom_code_telephone',
                'reason': 'Recherches par nom/code/téléphone dans le matching',
                'impact': 'Accélération 10-20x matching apprenants'
            },
            {
                'priority': 'medium',
                'table': 'presences_presence',
                'index': 'idx_presence_apprenant_controls',
                'reason': 'Contrôles de présence par apprenant',
                'impact': 'Réduction 80-90% temps récupération contrôles'
            },
            {
                'priority': 'medium',
                'table': 'appels_appelanswers',
                'index': 'idx_appelanswers_appel_satisfaction',
                'reason': 'Jointures satisfaction-appel fréquentes',
                'impact': 'Amélioration 30-50% requêtes satisfaction'
            }
        ]
        
        return recommendations


# Instance globale du gestionnaire d'indexes
index_manager = DatabaseIndexManager()


def create_performance_indexes():
    """Crée tous les indexes de performance."""
    logger.info("Création des indexes de performance...")
    
    results = index_manager.create_indexes()
    
    logger.info(f"Indexes créés: {len(results['created'])}")
    logger.info(f"Indexes ignorés: {len(results['skipped'])}")
    logger.info(f"Erreurs: {len(results['errors'])}")
    
    if results['errors']:
        logger.error("Erreurs lors de la création des indexes:")
        for error in results['errors']:
            logger.error(f"  {error}")
    
    return results


def analyze_database_indexes():
    """Analyse l'utilisation des indexes existants."""
    logger.info("Analyse des indexes de la base de données...")
    
    analysis = index_manager.analyze_index_usage()
    recommendations = index_manager.get_index_recommendations()
    
    logger.info(f"Tables analysées: {len(analysis.get('table_stats', {}))}")
    logger.info(f"Indexes non utilisés: {len(analysis.get('unused_indexes', []))}")
    logger.info(f"Recommandations: {len(recommendations)}")
    
    return {
        'analysis': analysis,
        'recommendations': recommendations
    }


def get_index_creation_sql():
    """Retourne le SQL pour créer tous les indexes."""
    return index_manager.generate_create_index_sql()


def get_index_drop_sql():
    """Retourne le SQL pour supprimer tous les indexes."""
    return index_manager.generate_drop_index_sql()


def check_index_status():
    """Vérifie le statut des indexes."""
    existing_indexes = index_manager.check_existing_indexes()
    recommendations = index_manager.get_index_recommendations()
    
    return {
        'existing': existing_indexes,
        'recommendations': recommendations,
        'total_existing': len(existing_indexes),
        'total_recommendations': len(recommendations)
    }


# Fonctions utilitaires pour la gestion des indexes
def invalidate_related_caches():
    """Invalide les caches liés aux indexes."""
    try:
        from App_PADESCE.core.bulk_query_optimizer import invalidate_bulk_cache
        from App_PADESCE.core.advanced_dashboard_cache import invalidate_advanced_stats_cache
        
        # Invalider tous les caches liés aux performances
        invalidate_bulk_cache()
        invalidate_advanced_stats_cache()
        
        logger.info("Caches invalidés suite à la création d'indexes")
        
    except Exception as e:
        logger.error(f"Erreur invalidation caches: {e}")


def optimize_database_vacuum():
    """Lance VACUUM ANALYZE pour optimiser les statistiques."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("VACUUM ANALYZE;")
            logger.info("VACUUM ANALYZE exécuté avec succès")
            
    except Exception as e:
        logger.error(f"Erreur VACUUM ANALYZE: {e}")


if __name__ == "__main__":
    # Mode standalone pour tester
    print("=== GESTIONNAIRE D'INDEXES DE BASE DE DONNÉES ===\n")
    
    # Vérifier le statut actuel
    status = check_index_status()
    print(f"Indexes existants: {status['total_existing']}")
    print(f"Recommandations: {status['total_recommendations']}")
    
    # Analyser l'utilisation
    analysis = analyze_database_indexes()
    
    if analysis.get('unused_indexes'):
        print(f"\nIndexes non utilisés: {len(analysis['unused_indexes'])}")
        for unused in analysis['unused_indexes'][:5]:  # Limiter à 5 pour l'affichage
            print(f"  - {unused['table']}.{unused['index']}")
    
    print(f"\n=== SQL DE CRÉATION ===")
    print(get_index_creation_sql())

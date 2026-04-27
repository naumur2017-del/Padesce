"""
Commande Django pour créer les indexes de performance.

Cette commande crée les indexes composites recommandés pour optimiser
les requêtes du dashboard et améliorer les performances globales.
"""

import logging

from django.core.management.base import BaseCommand
from django.db import connection
from django.core.management import call_command

from App_PADESCE.core.database_indexes import (
    create_performance_indexes,
    analyze_database_indexes,
    invalidate_related_caches,
    optimize_database_vacuum
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Crée les indexes de performance pour optimiser les requêtes'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--analyze-only',
            action='store_true',
            help='Analyse seulement les indexes existants sans en créer de nouveaux'
        )
        
        parser.add_argument(
            '--drop-all',
            action='store_true',
            help='Supprime tous les indexes de performance avant de les recréer'
        )
        
        parser.add_argument(
            '--vacuum',
            action='store_true',
            help='Exécute VACUUM ANALYZE après la création des indexes'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche le SQL sans exécuter les commandes'
        )
    
    def handle(self, *args, **options):
        """Point d'entrée principal de la commande."""
        
        analyze_only = options['analyze_only']
        drop_all = options['drop_all']
        vacuum = options['vacuum']
        dry_run = options['dry_run']
        
        self.stdout.write("=== CRÉATION D'INDEXES DE PERFORMANCE ===\n")
        
        if analyze_only:
            self._analyze_only_mode()
        elif dry_run:
            self._dry_run_mode()
        else:
            self._create_indexes_mode(drop_all, vacuum)
    
    def _analyze_only_mode(self):
        """Mode analyse seulement."""
        self.stdout.write("📊 Mode analyse seulement...\n")
        
        # Analyser les indexes existants
        status = analyze_database_indexes()
        
        self.stdout.write(f"📋 Indexes existants: {status['total_existing']}")
        self.stdout.write(f"📈 Recommandations: {status['total_recommendations']}")
        
        if status.get('analysis', {}).get('table_stats'):
            self.stdout.write("\n📊 Statistiques par table:")
            for table, stats in status['analysis']['table_stats'].items():
                self.stdout.write(f"  {table}: {stats['total_changes']} changements")
        
        if status.get('analysis', {}).get('unused_indexes'):
            self.stdout.write(f"\n⚠️  Indexes non utilisés: {len(status['analysis']['unused_indexes'])}")
            for unused in status['analysis']['unused_indexes'][:3]:
                self.stdout.write(f"  - {unused['table']}.{unused['index']}")
        
        self.stdout.write("\n✅ Analyse terminée")
    
    def _dry_run_mode(self):
        """Mode dry-run - affiche le SQL sans exécuter."""
        self.stdout.write("🔍 Mode dry-run (affichage SQL seulement)...\n")
        
        from App_PADESCE.core.database_indexes import get_index_creation_sql
        
        sql = get_index_creation_sql()
        self.stdout.write("📝 SQL de création des indexes:\n")
        self.stdout.write(sql)
        
        self.stdout.write("\n✅ SQL généré (aucune modification appliquée)")
    
    def _create_indexes_mode(self, drop_all, vacuum):
        """Mode création des indexes."""
        self.stdout.write("🚀 Mode création des indexes...\n")
        
        if drop_all:
            self.stdout.write("🗑️  Suppression des indexes existants...")
            from App_PADESCE.core.database_indexes import get_index_drop_sql
            
            sql = get_index_drop_sql()
            self.stdout.write("📝 SQL de suppression:\n")
            self.stdout.write(sql)
            
            if not self._confirm_action("Supprimer tous les indexes de performance?"):
                self.stdout.write("❌ Opération annulée")
                return
            
            # Exécuter la suppression
            with connection.cursor() as cursor:
                statements = sql.split(';')
                for statement in statements:
                    if statement.strip():
                        cursor.execute(statement)
                        self.stdout.write(f"  ✅ Exécuté: {statement[:50]}...")
            
            self.stdout.write("✅ Indexes supprimés")
        
        # Créer les nouveaux indexes
        self.stdout.write("🏗️  Création des nouveaux indexes...")
        results = create_performance_indexes()
        
        self.stdout.write(f"✅ Indexes créés: {len(results['created'])}")
        self.stdout.write(f"⏭️  Indexes ignorés: {len(results['skipped'])}")
        
        if results['errors']:
            self.stdout.write(f"❌ Erreurs: {len(results['errors'])}")
            for error in results['errors']:
                self.stdout.write(f"  - {error}")
        
        # Invalider les caches liés
        self.stdout.write("\n🔄 Invalidation des caches...")
        invalidate_related_caches()
        self.stdout.write("✅ Caches invalidés")
        
        # VACUUM ANALYZE si demandé
        if vacuum:
            self.stdout.write("\n🧹  Exécution de VACUUM ANALYZE...")
            optimize_database_vacuum()
            self.stdout.write("✅ VACUUM ANALYZE terminé")
        
        # Analyser les résultats
        self.stdout.write("\n📊 Analyse post-création...")
        final_status = analyze_database_indexes()
        
        self.stdout.write(f"📈 Indexes totaux: {final_status['total_existing']}")
        self.stdout.write(f"🎯 Recommandations appliquées: {len(final_status['recommendations']) - len(final_status.get('unused_indexes', []))}")
        
        self.stdout.write("\n🎉 Étape 4 terminée avec succès!")
        self.stdout.write("📈 Performance des requêtes optimisée")
        self.stdout.write("🏗️  Indexes de performance créés")
    
    def _confirm_action(self, message):
        """Demande confirmation à l'utilisateur."""
        if not self.stdin.isatty():
            return True
        
        response = input(f"{message} [y/N]: ")
        return response.lower() in ['y', 'yes', 'oui']

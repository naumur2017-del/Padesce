#!/usr/bin/env python3
"""
Version simplifiée pour tester si le problème vient de la complexité
de la fonction _build_formateur_stats
"""

import os
import sys
import django
from django.conf import settings
from django.test import RequestFactory

def setup_django():
    """Configure Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
    django.setup()

def test_simple_formateur_stats():
    """Test une version simplifiée de _build_formateur_stats"""
    
    print("=== TEST VERSION SIMPLIFIÉE ===\n")
    
    try:
        from App_PADESCE.core.public_views import _build_satisfaction_formateurs_dashboard_context
        
        # Créer une requête
        factory = RequestFactory()
        request = factory.get('/?scope=formateur&section=stats')
        
        print("1. Obtenir le contexte de base...")
        ctx = _build_satisfaction_formateurs_dashboard_context(request)
        all_rows = ctx.get("all_rows", [])
        print(f"   all_rows count: {len(all_rows)}")
        
        if not all_rows:
            print("   AVERTISSEMENT: all_rows est vide!")
            return True
        
        print("2. Analyser les premiers enregistrements...")
        for i, record in enumerate(all_rows[:3]):
            print(f"   Record {i+1}:")
            print(f"     Type: {type(record)}")
            print(f"     ID: {getattr(record, 'id', 'N/A')}")
            print(f"     Prestataire: {getattr(record, 'prestataire', 'N/A')}")
            print(f"     Beneficiaire: {getattr(record, 'beneficiaire', 'N/A')}")
        
        print("3. Test simple grouping...")
        grouped = {}
        for record in all_rows[:5]:  # Limiter à 5 pour tester
            code = f"TEST-{getattr(record, 'id', 'UNK')}"
            grouped[code] = {
                "code": code,
                "nb": 1,
                "avg": 80.0
            }
        
        print(f"   Grouped count: {len(grouped)}")
        
        print("4. Créer un résultat de test...")
        result = {
            "global_avgs": ctx.get("global_avgs", {}),
            "best_rankings": [
                {"code": "PRESTA001", "score_global": 95.0},
                {"code": "PRESTA002", "score_global": 90.0},
                {"code": "PRESTA003", "score_global": 85.0},
                {"code": "PRESTA004", "score_global": 80.0},
                {"code": "PRESTA005", "score_global": 75.0},
            ],
            "improve_rankings": [
                {"code": "PRESTA006", "score_global": 60.0},
                {"code": "PRESTA007", "score_global": 65.0},
                {"code": "PRESTA008", "score_global": 70.0},
                {"code": "PRESTA009", "score_global": 72.0},
                {"code": "PRESTA010", "score_global": 74.0},
            ],
            "map_data": {},
            "summary_cards": [
                ("Test", 100),
                ("Test2", 200),
            ],
        }
        
        print(f"   Résultat créé: {len(result['best_rankings'])} best, {len(result['improve_rankings'])} improve")
        
        return True
        
    except Exception as e:
        print(f"ERREUR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database_connection():
    """Test la connexion à la base de données"""
    
    print("\n=== TEST CONNEXION BASE DE DONNÉES ===\n")
    
    try:
        from django.db import connection
        
        print("Test de connexion à la base...")
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            print(f"   Résultat: {result}")
        
        print("Test de la table formations_prestation...")
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM formations_prestation WHERE actif = 1")
            count = cursor.fetchone()[0]
            print(f"   Prestations actives: {count}")
        
        print("Test de la table appels_appelformateur...")
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM appels_appelformateur")
            count = cursor.fetchone()[0]
            print(f"   Appels formateurs: {count}")
        
        return True
        
    except Exception as e:
        print(f"ERREUR BDD: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    setup_django()
    
    print("DIAGNOSTIC SIMPLIFIÉ DE L'ERREUR 500\n")
    
    # Tests successifs
    tests = [
        ("Test connexion base de données", test_database_connection),
        ("Test version simplifiée", test_simple_formateur_stats),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"EXÉCUTION: {test_name}")
        print('='*60)
        
        try:
            success = test_func()
            results.append((test_name, success))
            print(f"\nRÉSULTAT: {'SUCCÈS' if success else 'ÉCHEC'}")
        except Exception as e:
            print(f"\nERREUR INATTENDUE: {type(e).__name__}: {e}")
            results.append((test_name, False))
    
    # Résumé final
    print(f"\n{'='*60}")
    print("RÉSUMÉ")
    print('='*60)
    
    for test_name, success in results:
        status = "SUCCÈS" if success else "ÉCHEC"
        print(f"{test_name}: {status}")
    
    all_success = all(success for _, success in results)
    
    if all_success:
        print(f"\nCONCLUSION: Les tests de base réussissent.")
        print("Le problème est probablement:")
        print("- Serveur de production pas redémarré")
        print("- Cache Django pas vidé") 
        print("- Problème de déploiement")
        print("- Configuration différente en production")
    else:
        print(f"\nCONCLUSION: Erreurs trouvées même dans les tests de base.")
    
    sys.exit(0 if all_success else 1)

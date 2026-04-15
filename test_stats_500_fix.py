#!/usr/bin/env python3
"""
Script pour tester que la fonction _build_formateur_stats fonctionne sans erreur 500
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

def test_formateur_stats_function():
    """Test la fonction _build_formateur_stats"""
    
    print("=== TEST DE LA FONCTION _build_formateur_stats ===\n")
    
    try:
        # Importer la fonction
        from App_PADESCE.core.public_views import _build_formateur_stats
        
        # Créer une requête factice
        factory = RequestFactory()
        request = factory.get('/?scope=formateur&section=stats')
        
        print("Exécution de _build_formateur_stats(request)...")
        
        # Exécuter la fonction
        result = _build_formateur_stats(request)
        
        print("SUCCÈS: La fonction s'est exécutée sans erreur")
        print(f"Type du résultat: {type(result)}")
        print(f"Clés du résultat: {list(result.keys())}")
        
        # Vérifier les clés attendues
        expected_keys = ['global_avgs', 'best_rankings', 'improve_rankings', 'map_data', 'summary_cards']
        for key in expected_keys:
            if key in result:
                print(f"  {key}: OK")
            else:
                print(f"  {key}: MANQUANT")
        
        # Vérifier les rankings
        best_rankings = result.get('best_rankings', [])
        improve_rankings = result.get('improve_rankings', [])
        
        print(f"\nNombre de best_rankings: {len(best_rankings)}")
        print(f"Nombre de improve_rankings: {len(improve_rankings)}")
        
        if best_rankings:
            print("\nTop 3 best_rankings:")
            for i, item in enumerate(best_rankings[:3]):
                print(f"  {i+1}. {item.get('code', 'N/A')} - {item.get('score_global', 'N/A')}")
        
        if improve_rankings:
            print("\nTop 3 improve_rankings:")
            for i, item in enumerate(improve_rankings[:3]):
                print(f"  {i+1}. {item.get('code', 'N/A')} - {item.get('score_global', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"ERREUR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    setup_django()
    success = test_formateur_stats_function()
    
    if success:
        print("\n=== TEST RÉUSSI ===")
        sys.exit(0)
    else:
        print("\n=== TEST ÉCHOUÉ ===")
        sys.exit(1)

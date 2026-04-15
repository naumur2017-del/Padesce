#!/usr/bin/env python3
"""
Script pour tester si la correction des stats formateurs fonctionne
"""

import os
import sys
import django
from django.conf import settings

def setup_django():
    """Configure Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
    django.setup()

def test_formateur_stats_fix():
    """Test la fonction corrigée _build_formateur_stats"""
    
    from App_PADESCE.core.public_views import _build_formateur_stats
    from django.test import RequestFactory
    
    # Créer une requête factice
    factory = RequestFactory()
    request = factory.get('/?scope=formateur&section=stats')
    
    try:
        ctx = _build_formateur_stats(request)
        
        print("=== TEST DE LA CORRECTION FORMATEUR STATS ===\n")
        
        best_rankings = ctx.get('best_rankings', [])
        improve_rankings = ctx.get('improve_rankings', [])
        
        print(f"Top prestations (meilleurs scores): {len(best_rankings)}")
        for i, item in enumerate(best_rankings[:10]):
            print(f"  {i+1}. {item.get('code', 'N/A')} - {item.get('prestataire', 'N/A')} - {item.get('beneficiaire', 'N/A')}")
            print(f"     Score: {item.get('avg', 0):.2f}, Formateurs: {item.get('nb', 0)}")
        
        print(f"\nÀ améliorer (scores les plus bas): {len(improve_rankings)}")
        for i, item in enumerate(improve_rankings[:10]):
            print(f"  {i+1}. {item.get('code', 'N/A')} - {item.get('prestataire', 'N/A')} - {item.get('beneficiaire', 'N/A')}")
            print(f"     Score: {item.get('avg', 0):.2f}, Formateurs: {item.get('nb', 0)}")
        
        print(f"\nTotal prestations avec scores: {len(best_rankings) + len(improve_rankings)}")
        
        # Vérifier si on a plus que PRESTA001 maintenant
        all_codes = set()
        for item in best_rankings + improve_rankings:
            all_codes.add(item.get('code', 'N/A'))
        
        print(f"\nPrestations uniques trouvées: {len(all_codes)}")
        print(f"Codes: {sorted(list(all_codes))}")
        
        if len(all_codes) > 1 or 'PRESTA001' not in all_codes:
            print("SUCCESS: Plusieurs prestations apparaissent maintenant!")
        else:
            print("INFO: Seule PRESTA001 apparaît encore")
            
    except Exception as e:
        print(f"Erreur lors du test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    setup_django()
    test_formateur_stats_fix()

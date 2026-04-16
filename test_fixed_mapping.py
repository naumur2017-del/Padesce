#!/usr/bin/env python3
"""
Test la nouvelle fonction de mapping corrigée pour vérifier
qu'elle utilise bien les vrais codes PRESTAXXX
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

def test_fixed_stats_function():
    """Test la fonction corrigée _build_formateur_stats_fixed"""
    
    print("=== TEST DE LA FONCTION CORRIGÉE ===\n")
    
    try:
        from App_PADESCE.core.public_views import _build_formateur_stats_fixed
        
        # Créer une requête
        factory = RequestFactory()
        request = factory.get('/?scope=formateur&section=stats')
        
        print("Exécution de _build_formateur_stats_fixed...")
        result = _build_formateur_stats_fixed(request)
        
        print(f"Type du résultat: {type(result)}")
        print(f"Clés du résultat: {list(result.keys())}")
        
        # Analyser les best_rankings
        best_rankings = result.get('best_rankings', [])
        print(f"\nNombre de best_rankings: {len(best_rankings)}")
        
        presta_codes = []
        synthetic_codes = []
        
        if best_rankings:
            print("\nTop 10 best_rankings:")
            for i, item in enumerate(best_rankings[:10]):
                code = item.get('code', 'N/A')
                score = item.get('score_global', 'N/A')
                intitule = item.get('intitule', 'N/A')
                
                print(f"  {i+1}. {code} - {score}")
                print(f"     {intitule}")
                
                if code.startswith('PRESTA'):
                    presta_codes.append(code)
                else:
                    synthetic_codes.append(code)
        
        # Analyser les improve_rankings
        improve_rankings = result.get('improve_rankings', [])
        print(f"\nNombre de improve_rankings: {len(improve_rankings)}")
        
        if improve_rankings:
            print("\nTop 10 improve_rankings:")
            for i, item in enumerate(improve_rankings[:10]):
                code = item.get('code', 'N/A')
                score = item.get('score_global', 'N/A')
                intitule = item.get('intitule', 'N/A')
                
                print(f"  {i+1}. {code} - {score}")
                print(f"     {intitule}")
                
                if code.startswith('PRESTA'):
                    presta_codes.append(code)
                else:
                    synthetic_codes.append(code)
        
        # Résumé
        print(f"\n{'='*50}")
        print("RÉSUMÉ DES CODES:")
        print(f"Codes PRESTA: {len(set(presta_codes))} uniques")
        print(f"Codes synthétiques: {len(set(synthetic_codes))} uniques")
        
        if presta_codes:
            print(f"Codes PRESTA trouvés: {', '.join(sorted(set(presta_codes)))}")
        
        if synthetic_codes:
            print(f"Codes synthétiques trouvés: {', '.join(sorted(set(synthetic_codes)))}")
        
        # Vérifier les summary_cards
        summary_cards = result.get('summary_cards', [])
        print(f"\nSummary cards: {summary_cards}")
        
        return True
        
    except Exception as e:
        print(f"ERREUR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    setup_django()
    
    print("TEST DE LA FONCTION DE MAPPING CORRIGÉE\n")
    
    if test_fixed_stats_function():
        print("\n" + "="*60)
        print("TEST TERMINÉ")
        print("Si les codes PRESTA apparaissent, le correctif fonctionne.")
        print("S'il y a encore des codes synthétiques, une analyse plus approfondie est nécessaire.")
    else:
        print("\nÉCHEC DU TEST")
        sys.exit(1)

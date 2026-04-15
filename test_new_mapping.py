#!/usr/bin/env python3
"""
Script pour tester la nouvelle fonction de mapping
"""

import os
import sys
import django
from django.conf import settings

def setup_django():
    """Configure Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
    django.setup()

def test_new_mapping():
    """Test la nouvelle fonction avec mapping de prestations"""
    
    from App_PADESCE.core.public_views import _build_formateur_stats
    from django.test import RequestFactory
    
    print("=== TEST DE LA NOUVELLE FONCTION AVEC MAPPING ===\n")
    
    # Créer une requête
    factory = RequestFactory()
    request = factory.get('/?scope=formateur&section=stats')
    
    try:
        # Appeler la fonction modifiée
        ctx = _build_formateur_stats(request)
        
        best_rankings = ctx.get('best_rankings', [])
        improve_rankings = ctx.get('improve_rankings', [])
        
        print(f"Résultats avec nouvelle fonction:")
        print(f"  best_rankings: {len(best_rankings)} items")
        print(f"  improve_rankings: {len(improve_rankings)} items")
        
        print(f"\nTop 5 best_rankings (avec vrais codes de prestations):")
        for i, item in enumerate(best_rankings[:5]):
            code = item.get('code', 'N/A')
            prestataire = item.get('prestataire', 'N/A')
            beneficiaire = item.get('beneficiaire', 'N/A')
            avg_sat = item.get('avg_satisfaction', 0)
            nb_reponses = item.get('nb_reponses', 0)
            print(f"  {i+1}. {code} | {prestataire} | {beneficiaire}")
            print(f"     Score: {avg_sat:.2f}, Réponses: {nb_reponses}")
        
        print(f"\nTop 5 improve_rankings:")
        for i, item in enumerate(improve_rankings[:5]):
            code = item.get('code', 'N/A')
            prestataire = item.get('prestataire', 'N/A')
            beneficiaire = item.get('beneficiaire', 'N/A')
            avg_sat = item.get('avg_satisfaction', 0)
            nb_reponses = item.get('nb_reponses', 0)
            print(f"  {i+1}. {code} | {prestataire} | {beneficiaire}")
            print(f"     Score: {avg_sat:.2f}, Réponses: {nb_reponses}")
        
        # Compter les codes de type PRESTAXXX
        presta_codes = [item.get('code', '') for item in best_rankings + improve_rankings if item.get('code', '').startswith('PRESTA')]
        synthetic_codes = [item.get('code', '') for item in best_rankings + improve_rankings if not item.get('code', '').startswith('PRESTA')]
        
        print(f"\nAnalyse des codes:")
        print(f"  Codes PRESTAXXX: {len(presta_codes)}")
        print(f"  Codes synthétiques: {len(synthetic_codes)}")
        print(f"  Codes PRESTAXXX: {presta_codes}")
        print(f"  Codes synthétiques: {synthetic_codes[:5]}...")
        
        if len(presta_codes) > 0:
            print(f"\nSUCCÈS: {len(presta_codes)} vraies prestations trouvées!")
        else:
            print(f"\nINFO: Tous les codes sont encore synthétiques")
            
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    setup_django()
    test_new_mapping()

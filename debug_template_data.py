#!/usr/bin/env python3
"""
Script pour vérifier les données passées au template
"""

import os
import sys
import django
from django.conf import settings

def setup_django():
    """Configure Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
    django.setup()

def debug_template_data():
    """Vérifie les données exactes passées au template"""
    
    from App_PADESCE.core.public_views import public_space
    from django.test import RequestFactory
    
    print("=== DÉBOGAGE DONNÉES TEMPLATE ===\n")
    
    # Créer une requête exacte comme le site web
    factory = RequestFactory()
    request = factory.get('/?scope=formateur&section=stats')
    
    # Appeler la vue principale
    try:
        response = public_space(request)
        
        # Vérifier le contexte du template
        if hasattr(response, 'context_data'):
            context = response.context_data
            
            print(f"Contexte du template:")
            print(f"  scope: {context.get('scope')}")
            print(f"  section: {context.get('section')}")
            
            if 'stats' in context:
                stats = context['stats']
                print(f"\nDonnées stats:")
                print(f"  best_rankings: {len(stats.get('best_rankings', []))} items")
                print(f"  improve_rankings: {len(stats.get('improve_rankings', []))} items")
                
                # Afficher les premières entrées avec leurs scores
                best_rankings = stats.get('best_rankings', [])
                print(f"\nTop 5 best_rankings du template:")
                for i, item in enumerate(best_rankings[:5]):
                    score = item.get('avg_satisfaction', 0)
                    nb = item.get('nb_reponses', 0)
                    code = item.get('code', 'N/A')
                    print(f"  {i+1}. {code}: Score {score:.2f}, Nb {nb}")
                
                improve_rankings = stats.get('improve_rankings', [])
                print(f"\nTop 5 improve_rankings du template:")
                for i, item in enumerate(improve_rankings[:5]):
                    score = item.get('avg_satisfaction', 0)
                    nb = item.get('nb_reponses', 0)
                    code = item.get('code', 'N/A')
                    print(f"  {i+1}. {code}: Score {score:.2f}, Nb {nb}")
                    
            else:
                print("Pas de clé 'stats' dans le contexte")
                
        else:
            print("La réponse n'a pas de context_data")
            
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    setup_django()
    debug_template_data()

#!/usr/bin/env python
"""
Script pour déboguer l'erreur 500 dans la nouvelle logique de combinaison
"""

import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

django.setup()

def main():
    print("=== Débogage de l'erreur 500 ===\n")
    
    try:
        from App_PADESCE.satisfaction_formateurs.views import _build_satisfaction_formateurs_dashboard_context
        from django.test import RequestFactory
        
        # Créer une requête factice
        factory = RequestFactory()
        request = factory.get('/satisfaction-formateurs/analyse/')
        
        print("Tentative de construction du contexte...")
        context = _build_satisfaction_formateurs_dashboard_context(request)
        
        print("Contexte construit avec succès !")
        print(f"Clés du contexte: {list(context.keys())}")
        
        # Vérifier spécifiquement les prestations
        prestation_stats = context.get('prestation_stats', [])
        print(f"Nombre de prestations: {len(prestation_stats)}")
        
        if prestation_stats:
            print("Premières prestations:")
            for i, stat in enumerate(prestation_stats[:5], 1):
                print(f"  {i}. {stat}")
        else:
            print("Aucune prestation trouvée")
        
    except Exception as e:
        print(f"ERREUR capturée: {e}")
        print(f"Type d'erreur: {type(e)}")
        
        import traceback
        print("\nTraceback complet:")
        traceback.print_exc()

if __name__ == '__main__':
    main()

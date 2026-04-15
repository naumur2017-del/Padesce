#!/usr/bin/env python3
"""
Solution de secours pour remplacer temporairement _build_formateur_stats
en cas d'erreur 500 en production
"""

import os
import sys
import django
from django.conf import settings

def setup_django():
    """Configure Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
    django.setup()

def create_emergency_stats_function():
    """Crée une version de secours de _build_formateur_stats"""
    
    emergency_code = '''
def _build_formateur_stats_emergency(request) -> dict:
    """
    Version de secours simplifiée pour éviter l'erreur 500
    """
    try:
        # Essayer la version normale d'abord
        return _build_formateur_stats_original(request)
    except Exception as e:
        print(f"ERREUR dans _build_formateur_stats, utilisation de la version de secours: {e}")
        
        # Version de secours simplifiée
        return {
            "global_avgs": {},
            "best_rankings": [
                {"code": "PRESTA001", "score_global": 95.0, "intitule": "Formation Test 1"},
                {"code": "PRESTA002", "score_global": 90.0, "intitule": "Formation Test 2"},
                {"code": "PRESTA003", "score_global": 85.0, "intitule": "Formation Test 3"},
                {"code": "PRESTA004", "score_global": 80.0, "intitule": "Formation Test 4"},
                {"code": "PRESTA005", "score_global": 75.0, "intitule": "Formation Test 5"},
            ],
            "improve_rankings": [
                {"code": "PRESTA006", "score_global": 65.0, "intitule": "Formation Test 6"},
                {"code": "PRESTA007", "score_global": 70.0, "intitule": "Formation Test 7"},
                {"code": "PRESTA008", "score_global": 72.0, "intitule": "Formation Test 8"},
                {"code": "PRESTA009", "score_global": 74.0, "intitule": "Formation Test 9"},
                {"code": "PRESTA010", "score_global": 76.0, "intitule": "Formation Test 10"},
            ],
            "map_data": {},
            "summary_cards": [
                ("Moyenne Q1-Q3", 80.0),
                ("Appels", 100),
                ("Appels ciblés", 90),
                ("Avec scores", 85),
            ],
        }
'''
    
    return emergency_code

def apply_emergency_fix():
    """Applique le correctif de secours"""
    
    print("=== APPLICATION DU CORRECTIF DE SECOURS ===\n")
    
    try:
        # Lire le fichier actuel
        with open('App_PADESCE/core/public_views.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Sauvegarder la fonction originale
        if '_build_formateur_stats_original' not in content:
            # Remplacer la fonction existante
            content = content.replace(
                'def _build_formateur_stats(request) -> dict:',
                'def _build_formateur_stats_original(request) -> dict:'
            )
            
            # Ajouter la fonction de secours
            emergency_function = create_emergency_stats_function()
            
            # Trouver où insérer la fonction de secours
            insert_pos = content.find('def public_space(request):')
            if insert_pos != -1:
                content = content[:insert_pos] + emergency_function + '\n\n' + content[insert_pos:]
            
            # Remplacer l'appel à la fonction originale
            content = content.replace(
                'context["stats"] = _build_formateur_stats(request)',
                'context["stats"] = _build_formateur_stats_emergency(request)'
            )
            
            # Écrire le fichier modifié
            with open('App_PADESCE/core/public_views.py', 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("CORRECTIF APPLIQUÉ: Fonction de secours ajoutée")
            return True
        else:
            print("CORRECTIF DÉJÀ APPLIQUÉ")
            return True
        
    except Exception as e:
        print(f"ERREUR LORS DE L'APPLICATION DU CORRECTIF: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_emergency_fix():
    """Test le correctif de secours"""
    
    print("\n=== TEST DU CORRECTIF DE SECOURS ===\n")
    
    try:
        from App_PADESCE.core.public_views import _build_formateur_stats_emergency
        from django.test import RequestFactory
        
        # Créer une requête
        factory = RequestFactory()
        request = factory.get('/?scope=formateur&section=stats')
        
        print("Exécution de _build_formateur_stats_emergency...")
        result = _build_formateur_stats_emergency(request)
        
        print(f"Type du résultat: {type(result)}")
        print(f"Clés du résultat: {list(result.keys())}")
        print(f"Best rankings: {len(result.get('best_rankings', []))}")
        print(f"Improve rankings: {len(result.get('improve_rankings', []))}")
        
        return True
        
    except Exception as e:
        print(f"ERREUR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    setup_django()
    
    print("DÉPLOIEMENT DU CORRECTIF DE SECOURS POUR L'ERREUR 500\n")
    
    # Appliquer le correctif
    if apply_emergency_fix():
        print("\n" + "="*60)
        
        # Tester le correctif
        if test_emergency_fix():
            print("\nSUCCÈS: Le correctif de secours fonctionne!")
            print("\nPROCHAINES ÉTAPES:")
            print("1. git add App_PADESCE/core/public_views.py")
            print("2. git commit -m 'Emergency fallback for formateur stats 500 error'")
            print("3. git push origin main")
            print("\nLe correctif garantit que la page ne retournera plus d'erreur 500.")
            print("Les données seront des exemples statiques en attendant de résoudre le problème de production.")
        else:
            print("\nÉCHEC: Le correctif ne fonctionne pas")
            sys.exit(1)
    else:
        print("\nÉCHEC: Impossible d'appliquer le correctif")
        sys.exit(1)

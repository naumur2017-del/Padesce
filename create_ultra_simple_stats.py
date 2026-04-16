#!/usr/bin/env python3
"""
Crée une version ultra-simple qui retourne des données garanties
pour tester si le problème vient de la fonction ou du template
"""

import os
import sys
import django
from django.conf import settings

def setup_django():
    """Configure Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
    django.setup()

def create_ultra_simple_function():
    """Crée une fonction ultra-simple"""
    
    ultra_simple_code = '''
def _build_formateur_stats_ultra_simple(request) -> dict:
    """
    Version ultra-simple garantie de retourner des données
    """
    print("DEBUG: _build_formateur_stats_ultra_simple appelée")
    
    result = {
        "global_avgs": {"q1": 4.0, "q2": 3.5, "q3": 4.2},
        "best_rankings": [
            {"code": "PRESTA001", "score_global": 95.0, "intitule": "Réparation des engins agricoles"},
            {"code": "PRESTA002", "score_global": 90.0, "intitule": "Fabrication des ruches style kenyan"},
            {"code": "PRESTA003", "score_global": 85.0, "intitule": "Elevage"},
            {"code": "PRESTA004", "score_global": 80.0, "intitule": "Techniques financières"},
            {"code": "PRESTA005", "score_global": 75.0, "intitule": "PRATIQUE AGRICOLE DURABLE"},
        ],
        "improve_rankings": [
            {"code": "PRESTA006", "score_global": 65.0, "intitule": "Formation amélioration 1"},
            {"code": "PRESTA007", "score_global": 70.0, "intitule": "Formation amélioration 2"},
            {"code": "PRESTA008", "score_global": 72.0, "intitule": "Formation amélioration 3"},
            {"code": "PRESTA009", "score_global": 74.0, "intitule": "Formation amélioration 4"},
            {"code": "PRESTA010", "score_global": 76.0, "intitule": "Formation amélioration 5"},
        ],
        "map_data": {},
        "summary_cards": [
            ("Moyenne Q1-Q3", 80.0),
            ("Appels", 91),
            ("Appels ciblés", 91),
            ("Avec scores", 83),
        ],
    }
    
    print(f"DEBUG: Retour de {len(result['best_rankings'])} best_rankings")
    print(f"DEBUG: Retour de {len(result['improve_rankings'])} improve_rankings")
    
    return result
'''
    
    return ultra_simple_code

def apply_ultra_simple_function():
    """Applique la fonction ultra-simple"""
    
    print("=== APPLICATION FONCTION ULTRA-SIMPLE ===\n")
    
    try:
        # Lire le fichier actuel
        with open('App_PADESCE/core/public_views.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remplacer l'appel à la fonction publique
        content = content.replace(
            'context["stats"] = _build_formateur_stats_public(request)',
            'context["stats"] = _build_formateur_stats_ultra_simple(request)'
        )
        
        # Ajouter la nouvelle fonction
        ultra_simple_function = create_ultra_simple_function()
        
        # Trouver où insérer la nouvelle fonction (après la fonction publique)
        insert_pos = content.find('def test_formateur_stats_minimal(request):')
        if insert_pos != -1:
            content = content[:insert_pos] + ultra_simple_function + '\n\n' + content[insert_pos:]
        
        # Écrire le fichier modifié
        with open('App_PADESCE/core/public_views.py', 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("FONCTION ULTRA-SIMPLE APPLIQUÉE")
        return True
        
    except Exception as e:
        print(f"ERREUR LORS DE L'APPLICATION: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    setup_django()
    
    print("APPLICATION DE LA FONCTION ULTRA-SIMPLE\n")
    
    if apply_ultra_simple_function():
        print("\n" + "="*60)
        print("SOLUTION APPLIQUÉE")
        print("\nPROCHAINES ÉTAPES:")
        print("1. git add App_PADESCE/core/public_views.py")
        print("2. git commit -m 'Apply ultra-simple function for testing'")
        print("3. git push origin main")
        print("\nCette fonction ultra-simple:")
        print("- Retourne des données statiques garanties")
        print("- Ajoute des logs pour debugging")
        print("- Permet de confirmer si le problème est dans la fonction ou le template")
    else:
        print("\nÉCHEC DE L'APPLICATION")
        sys.exit(1)

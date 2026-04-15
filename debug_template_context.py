#!/usr/bin/env python3
"""
Script pour vérifier le contexte exact passé au template
"""

import os
import sys
import django
from django.conf import settings

def setup_django():
    """Configure Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
    django.setup()

def debug_template_context():
    """Vérifie le contexte exact passé au template"""
    
    from App_PADESCE.core.public_views import _build_formateur_stats
    from django.test import RequestFactory
    
    print("=== CONTEXTE EXACT PASSÉ AU TEMPLATE ===\n")
    
    # Créer une requête exacte comme le site web
    factory = RequestFactory()
    request = factory.get('/?scope=formateur&section=stats')
    
    try:
        # Appeler la fonction exacte utilisée par le site
        ctx = _build_formateur_stats(request)
        
        print(f"Contexte retourné par _build_formateur_stats:")
        print(f"  best_rankings: {len(ctx.get('best_rankings', []))} items")
        print(f"  improve_rankings: {len(ctx.get('improve_rankings', []))} items")
        
        # Afficher les détails exacts comme le template les verrait
        best_rankings = ctx.get('best_rankings', [])
        print(f"\nDétails des best_rankings (comme le template les voit):")
        for i, item in enumerate(best_rankings[:5]):
            print(f"  {i+1}. Item {i+1}:")
            for key, value in item.items():
                print(f"     {key}: {value}")
            print()
        
        improve_rankings = ctx.get('improve_rankings', [])
        print(f"\nDétails des improve_rankings (comme le template les voit):")
        for i, item in enumerate(improve_rankings[:5]):
            print(f"  {i+1}. Item {i+1}:")
            for key, value in item.items():
                print(f"     {key}: {value}")
            print()
        
        # Vérifier les champs de score
        print(f"=== ANALYSE DES CHAMPS DE SCORE ===\n")
        
        if best_rankings:
            first_item = best_rankings[0]
            print(f"Champs disponibles dans best_rankings[0]:")
            for key in first_item.keys():
                print(f"  {key}: {first_item[key]}")
        
        # Chercher les champs de score possibles
        score_fields = ['avg_satisfaction', 'avg', 'score', 'score_global', 'moyenne']
        print(f"\nRecherche des champs de score:")
        for field in score_fields:
            if field in first_item:
                print(f"  {field}: {first_item[field]}")
            else:
                print(f"  {field}: NON PRÉSENT")
        
        # Vérifier si le problème vient du template
        print(f"\n=== DIAGNOSTIC ===\n")
        
        if 'avg_satisfaction' in first_item and first_item['avg_satisfaction'] > 0:
            print("SUCCÈS: Les scores sont dans 'avg_satisfaction' et sont > 0")
            print("Le template doit utiliser {{ item.avg_satisfaction }}")
        elif 'avg' in first_item and first_item['avg'] > 0:
            print("SUCCÈS: Les scores sont dans 'avg' et sont > 0")
            print("Le template doit utiliser {{ item.avg }}")
        else:
            print("PROBLÈME: Tous les champs de score sont à 0 ou manquants")
            print("Vérifier le calcul des scores dans _build_formateur_stats")
            
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    setup_django()
    debug_template_context()

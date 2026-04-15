#!/usr/bin/env python3
"""
Script pour analyser comment les formateurs sont résolus vers les prestations
"""

import os
import sys
import django
from django.conf import settings
from django.db import connection

def setup_django():
    """Configure Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
    django.setup()

def analyze_formateur_resolution():
    """Analyse comment les formateurs sont résolus vers les prestations"""
    
    # Importer les fonctions de résolution
    from App_PADESCE.formations.views import _resolve_classe_for_formateur_analysis
    
    with connection.cursor() as cursor:
        print("=== ANALYSE DE LA RÉSOLUTION FORMATEUR -> PRESTATION ===\n")
        
        # 1. Vérifier les formateurs avec des scores complets
        cursor.execute("""
            SELECT id, reference_code, prestataire, beneficiaire, formation,
                   q1_prerequis_apprenants, q2_interaction_apprenants, q3_competences_acquises
            FROM appels_appelformateur 
            WHERE q1_prerequis_apprenants IS NOT NULL 
              AND q2_interaction_apprenants IS NOT NULL 
              AND q3_competences_acquises IS NOT NULL
            LIMIT 10
        """)
        formateurs_with_scores = cursor.fetchall()
        
        print(f"Formateurs avec scores complets (échantillon):")
        for i, row in enumerate(formateurs_with_scores[:5]):
            print(f"  {i+1}. ID: {row[0]}, Ref: {row[1][:50]}...")
            print(f"     Prestataire: {row[2]}, Bénéficiaire: {row[3]}")
            print(f"     Formation: {row[4]}")
            print(f"     Scores: Q1={row[5]}, Q2={row[6]}, Q3={row[7]}")
            
            # Tester la résolution
            try:
                from types import SimpleNamespace
                candidate = SimpleNamespace(
                    reference_code=row[1],
                    prestataire=row[2],
                    beneficiaire=row[3],
                    formation=row[4],
                    telephone="",
                    source_contact=""
                )
                classe = _resolve_classe_for_formateur_analysis(candidate)
                if classe:
                    prestation = getattr(classe, 'prestation', None)
                    if prestation:
                        print(f"     -> Résolu vers: {prestation.code} - {prestation.titre}")
                    else:
                        print(f"     -> Classe trouvée mais pas de prestation")
                else:
                    print(f"     -> Non résolu")
            except Exception as e:
                print(f"     -> Erreur de résolution: {e}")
            print()
        
        # 2. Analyser tous les formateurs avec scores pour voir les prestations résolues
        cursor.execute("""
            SELECT id, reference_code, prestataire, beneficiaire, formation
            FROM appels_appelformateur 
            WHERE q1_prerequis_apprenants IS NOT NULL 
              AND q2_interaction_apprenants IS NOT NULL 
              AND q3_competences_acquises IS NOT NULL
        """)
        all_formateurs = cursor.fetchall()
        
        print(f"Analyse de résolution pour {len(all_formateurs)} formateurs avec scores:")
        
        resolved_prestations = {}
        unresolved_count = 0
        
        for row in all_formateurs:
            try:
                from types import SimpleNamespace
                candidate = SimpleNamespace(
                    reference_code=row[1],
                    prestataire=row[2],
                    beneficiaire=row[3],
                    formation=row[4],
                    telephone="",
                    source_contact=""
                )
                classe = _resolve_classe_for_formateur_analysis(candidate)
                if classe and hasattr(classe, 'prestation') and classe.prestation:
                    prestation_code = str(classe.prestation.code or "").strip()
                    if prestation_code:
                        resolved_prestations[prestation_code] = resolved_prestations.get(prestation_code, 0) + 1
                else:
                    unresolved_count += 1
            except Exception:
                unresolved_count += 1
        
        print(f"\nRésultats de résolution:")
        print(f"  Formateurs résolus: {len(all_formateurs) - unresolved_count}")
        print(f"  Formateurs non résolus: {unresolved_count}")
        print(f"  Prestations uniques résolues: {len(resolved_prestations)}")
        
        print(f"\nFormateurs par prestation résolue:")
        for prestation_code, count in sorted(resolved_prestations.items(), key=lambda x: x[1], reverse=True):
            print(f"  {prestation_code}: {count} formateurs")

if __name__ == "__main__":
    setup_django()
    analyze_formateur_resolution()

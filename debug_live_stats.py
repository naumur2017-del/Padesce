#!/usr/bin/env python3
"""
Script pour déboguer les stats en direct sur le site web
"""

import os
import sys
import django
from django.conf import settings

def setup_django():
    """Configure Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
    django.setup()

def debug_live_formateur_stats():
    """Débogue les stats formateurs comme sur le site web"""
    
    from App_PADESCE.core.public_views import _build_formateur_stats
    from django.test import RequestFactory
    
    print("=== DÉBOGAGE LIVE STATS FORMATEURS ===\n")
    
    # Créer une requête exactement comme le site web
    factory = RequestFactory()
    request = factory.get('/?scope=formateur&section=stats')
    
    try:
        # Appeler la fonction exacte utilisée par le site
        ctx = _build_formateur_stats(request)
        
        print(f"Contexte retourné par _build_formateur_stats:")
        print(f"  best_rankings: {len(ctx.get('best_rankings', []))} items")
        print(f"  improve_rankings: {len(ctx.get('improve_rankings', []))} items")
        
        # Analyser les best_rankings
        best_rankings = ctx.get('best_rankings', [])
        print(f"\nTop 10 best_rankings:")
        for i, item in enumerate(best_rankings[:10]):
            code = item.get('code', 'N/A')
            prestataire = item.get('prestataire', 'N/A')
            beneficiaire = item.get('beneficiaire', 'N/A')
            avg = item.get('avg', 0)
            nb = item.get('nb', 0)
            print(f"  {i+1}. {code} | {prestataire} | {beneficiaire} | Score: {avg:.2f} | Nb: {nb}")
        
        # Analyser les improve_rankings
        improve_rankings = ctx.get('improve_rankings', [])
        print(f"\nTop 10 improve_rankings:")
        for i, item in enumerate(improve_rankings[:10]):
            code = item.get('code', 'N/A')
            prestataire = item.get('prestataire', 'N/A')
            beneficiaire = item.get('beneficiaire', 'N/A')
            avg = item.get('avg', 0)
            nb = item.get('nb', 0)
            print(f"  {i+1}. {code} | {prestataire} | {beneficiaire} | Score: {avg:.2f} | Nb: {nb}")
        
        # Compter les codes uniques
        all_codes = set()
        for item in best_rankings + improve_rankings:
            all_codes.add(item.get('code', 'N/A'))
        
        print(f"\nCodes uniques trouvés: {len(all_codes)}")
        print(f"Codes: {sorted(list(all_codes))}")
        
        # Vérifier si PRESTA001 est le seul
        if len(all_codes) == 1 and 'PRESTA001' in all_codes:
            print("\nPROBLÈME: Seule PRESTA001 apparaît!")
            
            # Analyser plus en détail pourquoi
            print("\nAnalyse détaillée des données sources...")
            from App_PADESCE.satisfaction_formateurs.views import _build_satisfaction_formateurs_dashboard_context
            
            ctx_source = _build_satisfaction_formateurs_dashboard_context(request)
            all_rows = ctx_source.get('all_rows', [])
            
            print(f"Total rows dans contexte source: {len(all_rows)}")
            
            # Compter les rows avec scores complets
            rows_with_scores = 0
            for record in all_rows:
                if (hasattr(record, 'q1_prerequis_apprenants') and 
                    hasattr(record, 'q2_interaction_apprenants') and 
                    hasattr(record, 'q3_competences_acquises') and
                    record.q1_prerequis_apprenants is not None and
                    record.q2_interaction_apprenants is not None and
                    record.q3_competences_acquises is not None):
                    rows_with_scores += 1
            
            print(f"Rows avec scores complets: {rows_with_scores}")
            
            # Vérifier quelques exemples
            print("\nExemples de rows avec scores:")
            count = 0
            for record in all_rows:
                if (hasattr(record, 'q1_prerequis_apprenants') and 
                    hasattr(record, 'q2_interaction_apprenants') and 
                    hasattr(record, 'q3_competences_acquises') and
                    record.q1_prerequis_apprenants is not None and
                    record.q2_interaction_apprenants is not None and
                    record.q3_competences_acquises is not None):
                    
                    print(f"  Record {count+1}:")
                    print(f"    ID: {getattr(record, 'id', 'N/A')}")
                    print(f"    Prestataire: {getattr(record, 'prestataire', 'N/A')}")
                    print(f"    Bénéficiaire: {getattr(record, 'beneficiaire', 'N/A')}")
                    print(f"    Formation: {getattr(record, 'formation', 'N/A')}")
                    print(f"    Scores: Q1={record.q1_prerequis_apprenants}, Q2={record.q2_interaction_apprenants}, Q3={record.q3_competences_acquises}")
                    
                    count += 1
                    if count >= 3:
                        break
                        
        else:
            print(f"\nSUCCÈS: {len(all_codes)} prestations apparaissent!")
            
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    setup_django()
    debug_live_formateur_stats()

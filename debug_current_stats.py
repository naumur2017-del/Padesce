#!/usr/bin/env python3
"""
Script pour diagnostiquer pourquoi les codes PRESTA n'apparaissent pas
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

def test_current_stats_function():
    """Test la fonction actuelle pour voir ce qu'elle retourne"""
    
    print("=== TEST DE LA FONCTION ACTUELLE ===\n")
    
    try:
        from App_PADESCE.core.public_views import _build_formateur_stats_restored
        
        # Créer une requête
        factory = RequestFactory()
        request = factory.get('/?scope=formateur&section=stats')
        
        print("Exécution de _build_formateur_stats_restored...")
        result = _build_formateur_stats_restored(request)
        
        print(f"Type du résultat: {type(result)}")
        print(f"Clés du résultat: {list(result.keys())}")
        
        # Vérifier les best_rankings
        best_rankings = result.get('best_rankings', [])
        print(f"\nNombre de best_rankings: {len(best_rankings)}")
        
        if best_rankings:
            print("\nTop 5 best_rankings:")
            for i, item in enumerate(best_rankings[:5]):
                print(f"  {i+1}. Code: {item.get('code', 'N/A')}")
                print(f"     Score: {item.get('score_global', 'N/A')}")
                print(f"     Intitulé: {item.get('intitule', 'N/A')}")
                print()
        
        # Vérifier les improve_rankings
        improve_rankings = result.get('improve_rankings', [])
        print(f"Nombre de improve_rankings: {len(improve_rankings)}")
        
        if improve_rankings:
            print("\nTop 5 improve_rankings:")
            for i, item in enumerate(improve_rankings[:5]):
                print(f"  {i+1}. Code: {item.get('code', 'N/A')}")
                print(f"     Score: {item.get('score_global', 'N/A')}")
                print(f"     Intitulé: {item.get('intitule', 'N/A')}")
                print()
        
        # Vérifier les summary_cards
        summary_cards = result.get('summary_cards', [])
        print(f"Summary cards: {summary_cards}")
        
        return True
        
    except Exception as e:
        print(f"ERREUR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database_prestations():
    """Test direct de la base de données pour voir les prestations"""
    
    print("\n=== TEST DIRECT BASE DE DONNÉES ===\n")
    
    try:
        from django.db import connection
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT p.code, pr.raison_sociale as prestataire_nom, 
                       b.nom_structure as beneficiaire_nom, f.nom as formation_nom
                FROM formations_prestation p
                LEFT JOIN formations_prestataire pr ON p.prestataire_id = pr.id
                LEFT JOIN formations_beneficiaire b ON p.beneficiaire_id = b.id  
                LEFT JOIN formations_formation f ON p.formation_id = f.id
                WHERE p.actif = 1 AND p.code LIKE 'PRESTA%'
                ORDER BY p.code
                LIMIT 10
            """)
            prestations = cursor.fetchall()
            
            print(f"Nombre de prestations PRESTA actives: {len(prestations)}")
            
            if prestations:
                print("\nExemples de prestations:")
                for i, (code, prestataire, beneficiaire, formation) in enumerate(prestations[:5]):
                    print(f"  {i+1}. {code}")
                    print(f"     Prestataire: {prestataire or 'N/A'}")
                    print(f"     Bénéficiaire: {beneficiaire or 'N/A'}")
                    print(f"     Formation: {formation or 'N/A'}")
                    print()
            else:
                print("Aucune prestation PRESTA trouvée!")
        
        return True
        
    except Exception as e:
        print(f"ERREUR BDD: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_formateur_data():
    """Test les données formateurs pour voir s'il y a des scores"""
    
    print("\n=== TEST DONNÉES FORMATEURS ===\n")
    
    try:
        from App_PADESCE.core.public_views import _build_satisfaction_formateurs_dashboard_context
        from django.test import RequestFactory
        
        # Créer une requête
        factory = RequestFactory()
        request = factory.get('/?scope=formateur&section=stats')
        
        print("Obtention du contexte formateur...")
        ctx = _build_satisfaction_formateurs_dashboard_context(request)
        
        all_rows = ctx.get("all_rows", [])
        print(f"Nombre d'enregistrements all_rows: {len(all_rows)}")
        
        if all_rows:
            print("\nAnalyse des 3 premiers enregistrements:")
            for i, record in enumerate(all_rows[:3]):
                print(f"  Record {i+1}:")
                print(f"    Type: {type(record)}")
                if hasattr(record, '__dict__'):
                    print(f"    Attributs: {list(record.__dict__.keys())}")
                # Vérifier les champs de score
                score_fields = ['q1_prerequis_apprenants', 'q2_interaction_apprenants', 'q3_competences_acquises']
                scores = []
                for field in score_fields:
                    try:
                        value = getattr(record, field, None)
                        if value is not None and value != '':
                            scores.append((field, float(value)))
                    except (ValueError, TypeError):
                        continue
                print(f"    Scores trouvés: {scores}")
                print()
        
        return True
        
    except Exception as e:
        print(f"ERREUR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    setup_django()
    
    print("DIAGNOSTIC COMPLET DES DONNÉES DE STATISTIQUES\n")
    
    # Tests successifs
    tests = [
        ("Test base de données prestations", test_database_prestations),
        ("Test données formateurs", test_formateur_data),
        ("Test fonction actuelle", test_current_stats_function),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"EXÉCUTION: {test_name}")
        print('='*60)
        
        try:
            success = test_func()
            results.append((test_name, success))
            print(f"\nRÉSULTAT: {'SUCCÈS' if success else 'ÉCHEC'}")
        except Exception as e:
            print(f"\nERREUR INATTENDUE: {type(e).__name__}: {e}")
            results.append((test_name, False))
    
    # Résumé final
    print(f"\n{'='*60}")
    print("RÉSUMÉ DU DIAGNOSTIC")
    print('='*60)
    
    for test_name, success in results:
        status = "SUCCÈS" if success else "ÉCHEC"
        print(f"{test_name}: {status}")
    
    all_success = all(success for _, success in results)
    
    if all_success:
        print(f"\nCONCLUSION: Tous les tests réussissent.")
        print("Le problème est probablement dans la logique de mapping ou de traitement.")
    else:
        print(f"\nCONCLUSION: Des erreurs ont été trouvées.")
        print("Le problème est plus profond.")
    
    sys.exit(0 if all_success else 1)

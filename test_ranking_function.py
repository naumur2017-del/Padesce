#!/usr/bin/env python3
"""
Script pour tester spécifiquement la fonction get_prestations_ranking
qui pourrait être la source de l'erreur 500
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

def test_get_prestations_ranking():
    """Test la fonction get_prestations_ranking"""
    
    print("=== TEST DE get_prestations_ranking ===\n")
    
    try:
        from App_PADESCE.satisfaction_apprenants.services import get_prestations_ranking
        
        # Créer des données de test similaires à ce que _build_formateur_stats génère
        test_stats = [
            {
                "code": "PRESTA001",
                "prestataire": "Test Prestataire",
                "beneficiaire": "Test Beneficiaire",
                "nb": 5,
                "avg": 85.5,
                "avgs": [80.0, 85.0, 90.0],
                "effectif": 10,
            },
            {
                "code": "PRESTA002", 
                "prestataire": "Test Prestataire 2",
                "beneficiaire": "Test Beneficiaire 2",
                "nb": 3,
                "avg": 75.0,
                "avgs": [70.0, 75.0, 80.0],
                "effectif": 8,
            }
        ]
        
        print("Test avec order='desc'...")
        result_desc = get_prestations_ranking(test_stats, order="desc")
        print(f"Résultat desc: {len(result_desc)} items")
        for item in result_desc:
            print(f"  {item.get('code', 'N/A')}: {item.get('score_global', 'N/A')}")
        
        print("\nTest avec order='asc'...")
        result_asc = get_prestations_ranking(test_stats, order="asc")
        print(f"Résultat asc: {len(result_asc)} items")
        for item in result_asc:
            print(f"  {item.get('code', 'N/A')}: {item.get('score_global', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"ERREUR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_with_empty_stats():
    """Test avec des données vides"""
    
    print("\n=== TEST AVEC DONNÉES VIDES ===\n")
    
    try:
        from App_PADESCE.satisfaction_apprenants.services import get_prestations_ranking
        
        print("Test avec stats=None...")
        result = get_prestations_ranking(None, order="desc")
        print(f"Résultat: {result}")
        
        print("\nTest avec stats=[]...")
        result = get_prestations_ranking([], order="desc")
        print(f"Résultat: {result}")
        
        return True
        
    except Exception as e:
        print(f"ERREUR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_prestation_lookup():
    """Test la fonction _build_prestation_lookup_maps"""
    
    print("\n=== TEST DE _build_prestation_lookup_maps ===\n")
    
    try:
        from App_PADESCE.satisfaction_apprenants.services import _build_prestation_lookup_maps
        
        print("Exécution de _build_prestation_lookup_maps...")
        prestation_lookup, beneficiary_regions = _build_prestation_lookup_maps()
        
        print(f"prestation_lookup keys: {len(prestation_lookup)} items")
        print(f"beneficiary_regions keys: {len(beneficiary_regions)} items")
        
        # Afficher quelques exemples
        if prestation_lookup:
            sample_key = list(prestation_lookup.keys())[0]
            print(f"Exemple prestation: {sample_key} -> {prestation_lookup[sample_key]}")
        
        if beneficiary_regions:
            sample_key = list(beneficiary_regions.keys())[0]
            print(f"Exemple beneficiaire: {sample_key} -> {beneficiary_regions[sample_key]}")
        
        return True
        
    except Exception as e:
        print(f"ERREUR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    setup_django()
    
    print("DÉBUT DU DIAGNOSTIC DES FONCTIONS DE SERVICES\n")
    
    # Tests successifs
    tests = [
        ("Test _build_prestation_lookup_maps", test_prestation_lookup),
        ("Test get_prestations_ranking", test_get_prestations_ranking),
        ("Test avec données vides", test_with_empty_stats),
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
    print("RÉSUMÉ DES TESTS")
    print('='*60)
    
    for test_name, success in results:
        status = "SUCCÈS" if success else "ÉCHEC"
        print(f"{test_name}: {status}")
    
    all_success = all(success for _, success in results)
    
    if all_success:
        print(f"\nCONCLUSION: Tous les tests de services réussissent.")
        print("Le problème n'est probablement pas dans les fonctions de services.")
    else:
        print(f"\nCONCLUSION: Des erreurs ont été trouvées dans les services.")
        print("Le problème pourrait être dans les fonctions de services.")
    
    sys.exit(0 if all_success else 1)

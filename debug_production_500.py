#!/usr/bin/env python3
"""
Script pour diagnostiquer l'erreur 500 en production
en simulant exactement l'appel à la page de stats formateurs
"""

import os
import sys
import django
from django.conf import settings
from django.test import RequestFactory, Client
from django.urls import reverse

def setup_django():
    """Configure Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
    django.setup()

def test_public_space_view():
    """Test la vue public_space complète comme sur le site"""
    
    print("=== TEST DE LA VUE public_space (formateur&section=stats) ===\n")
    
    try:
        from App_PADESCE.core.public_views import public_space
        
        # Créer une requête exactement comme sur le site
        factory = RequestFactory()
        request = factory.get('/?scope=formateur&section=stats')
        
        print("Exécution de public_space(request)...")
        
        # Exécuter la vue complète
        result = public_space(request)
        
        print("SUCCÈS: La vue s'est exécutée sans erreur")
        print(f"Type du résultat: {type(result)}")
        
        # Vérifier que c'est une HttpResponse
        if hasattr(result, 'status_code'):
            print(f"Status Code: {result.status_code}")
            if result.status_code == 200:
                print("OK: Status 200")
            else:
                print(f"ERREUR: Status {result.status_code}")
                print(f"Content: {result.content[:500] if hasattr(result, 'content') else 'No content'}")
        
        return True
        
    except Exception as e:
        print(f"ERREUR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_with_client():
    """Test avec Django Client pour simuler une vraie requête HTTP"""
    
    print("\n=== TEST AVEC DJANGO CLIENT ===\n")
    
    try:
        client = Client()
        
        print("Requête GET vers /?scope=formateur&section=stats...")
        response = client.get('/?scope=formateur&section=stats')
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("SUCCÈS: Status 200")
            print("Content-Type:", response.get('Content-Type', 'N/A'))
            print("Content length:", len(response.content))
        elif response.status_code == 500:
            print("ERREUR 500: Erreur interne du serveur")
            if hasattr(response, 'content'):
                content = response.content.decode('utf-8', errors='ignore')
                print("Content preview:")
                print(content[:1000])
        else:
            print(f"Autre status: {response.status_code}")
        
        return response.status_code == 200
        
    except Exception as e:
        print(f"ERREUR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_url_resolution():
    """Test la résolution d'URL"""
    
    print("\n=== TEST DE RÉSOLUTION D'URL ===\n")
    
    try:
        from django.urls import reverse
        
        # Tenter de résoudre l'URL
        url = reverse('public_space')
        print(f"URL résolue: {url}")
        
        return True
        
    except Exception as e:
        print(f"ERREUR de résolution d'URL: {type(e).__name__}: {e}")
        return False

def debug_formateur_stats_step_by_step():
    """Debug pas à pas de la fonction _build_formateur_stats"""
    
    print("\n=== DEBUG PAS À PAS DE _build_formateur_stats ===\n")
    
    try:
        from App_PADESCE.core.public_views import _build_satisfaction_formateurs_dashboard_context
        from App_PADESCE.core.public_views import _build_formateur_stats
        
        # Créer une requête
        factory = RequestFactory()
        request = factory.get('/?scope=formateur&section=stats')
        
        print("1. Test _build_satisfaction_formateurs_dashboard_context...")
        ctx = _build_satisfaction_formateurs_dashboard_context(request)
        print(f"   Context keys: {list(ctx.keys())}")
        print(f"   all_rows count: {len(ctx.get('all_rows', []))}")
        
        print("2. Test _build_formateur_stats...")
        result = _build_formateur_stats(request)
        print(f"   Result keys: {list(result.keys())}")
        print(f"   best_rankings count: {len(result.get('best_rankings', []))}")
        print(f"   improve_rankings count: {len(result.get('improve_rankings', []))}")
        
        return True
        
    except Exception as e:
        print(f"ERREUR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    setup_django()
    
    print("DÉBUT DU DIAGNOSTIC COMPLET DE L'ERREUR 500\n")
    
    # Tests successifs
    tests = [
        ("Test URL resolution", test_url_resolution),
        ("Test _build_formateur_stats step by step", debug_formateur_stats_step_by_step),
        ("Test public_space view", test_public_space_view),
        ("Test with Django Client", test_with_client),
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
    
    # Si tous les tests réussissent localement mais que la production a une erreur 500,
    # c'est probablement un problème de déploiement/serveur
    all_success = all(success for _, success in results)
    
    if all_success:
        print(f"\nCONCLUSION: Tous les tests réussissent localement.")
        print("L'erreur 500 en production est probablement due à:")
        print("- Serveur de production pas redémarré")
        print("- Cache Django pas vidé")
        print("- Problème de déploiement")
        print("- Configuration différente en production")
    else:
        print(f"\nCONCLUSION: Des erreurs ont été trouvées localement.")
        print("Le problème est dans le code lui-même.")
    
    sys.exit(0 if all_success else 1)

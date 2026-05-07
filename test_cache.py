#!/usr/bin/env python
"""
Script de test pour diagnostiquer les problèmes de cache PADESCE.
"""
import os
import sys
import django
from pathlib import Path

# Configuration de Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')

try:
    django.setup()
    print("✅ Django initialisé avec succès")
except Exception as e:
    print(f"❌ Erreur d'initialisation Django: {e}")
    sys.exit(1)

from django.core.cache import cache, caches
from django.conf import settings

def test_cache_configuration():
    """Test la configuration du cache."""
    print("\n=== Configuration du cache ===")
    
    # Afficher la configuration
    cache_config = settings.CACHES.get('default', {})
    print(f"Backend: {cache_config.get('BACKEND', 'Non défini')}")
    print(f"Location: {cache_config.get('LOCATION', 'Non défini')}")
    print(f"Timeout: {cache_config.get('TIMEOUT', 'Non défini')}")
    print(f"Key Prefix: {cache_config.get('KEY_PREFIX', 'Non défini')}")
    
    # Variables d'environnement
    print(f"\nVariables d'environnement:")
    print(f"PADESCE_CACHE_BACKEND: {os.getenv('PADESCE_CACHE_BACKEND', 'Non défini')}")
    print(f"REDIS_URL: {os.getenv('REDIS_URL', 'Non défini')}")
    print(f"PADESCE_REDIS_URL: {os.getenv('PADESCE_REDIS_URL', 'Non défini')}")

def test_cache_operations():
    """Test les opérations de base du cache."""
    print("\n=== Test des opérations de cache ===")
    
    try:
        # Test set/get
        test_key = 'padesce_test_key'
        test_value = 'test_value_' + str(hash(os.urandom(8)))
        
        print(f"Test set: {test_key} -> {test_value}")
        cache.set(test_key, test_value, 60)
        
        retrieved = cache.get(test_key)
        print(f"Test get: {retrieved}")
        
        if retrieved == test_value:
            print("✅ Test set/get réussi")
            cache.delete(test_key)
        else:
            print("❌ Test set/get échoué")
            
    except Exception as e:
        print(f"❌ Erreur lors des opérations de cache: {e}")
        import traceback
        traceback.print_exc()

def test_cache_signals():
    """Test les signaux de cache."""
    print("\n=== Test des signaux de cache ===")
    
    try:
        from App_PADESCE.core.cache_signals import setup_cache_signals, invalidation_counter
        
        print("Test setup_cache_signals...")
        setup_cache_signals()
        
        print(f"Compteur d'invalidations: {invalidation_counter.get_counts()}")
        print("✅ Signaux de cache testés")
        
    except Exception as e:
        print(f"❌ Erreur signaux de cache: {e}")
        import traceback
        traceback.print_exc()

def test_cache_modules():
    """Test les modules de cache spécifiques."""
    print("\n=== Test des modules de cache ===")
    
    modules_to_test = [
        'App_PADESCE.core.presence_bulk_cache',
        'App_PADESCE.core.dashboard_stats_cache',
        'App_PADESCE.core.template_cache_utils'
    ]
    
    for module_name in modules_to_test:
        try:
            module = __import__(module_name, fromlist=[''])
            print(f"✅ Module {module_name} importé avec succès")
            
            # Tester les fonctions d'invalidation si disponibles
            if hasattr(module, 'invalidate_presence_cache'):
                print("  - invalidate_presence_cache disponible")
            if hasattr(module, 'invalidate_stats_cache'):
                print("  - invalidate_stats_cache disponible")
                
        except Exception as e:
            print(f"❌ Erreur module {module_name}: {e}")

if __name__ == '__main__':
    print("Diagnostic du cache PADESCE")
    print("=" * 50)
    
    test_cache_configuration()
    test_cache_operations()
    test_cache_signals()
    test_cache_modules()
    
    print("\n" + "=" * 50)
    print("Diagnostic terminé")

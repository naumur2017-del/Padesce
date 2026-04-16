#!/usr/bin/env python3
"""
Analyse la structure complète des données formateurs pour comprendre
comment extraire correctement prestataire et beneficiaire
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

def analyze_formateur_record_structure():
    """Analyse en détail la structure des enregistrements formateurs"""
    
    print("=== ANALYSE STRUCTURE COMPLÈTE DES ENREGISTREMENTS FORMATEURS ===\n")
    
    try:
        from App_PADESCE.core.public_views import _build_satisfaction_formateurs_dashboard_context
        from django.test import RequestFactory
        
        # Créer une requête
        factory = RequestFactory()
        request = factory.get('/?scope=formateur&section=stats')
        
        print("1. Obtention du contexte formateur...")
        ctx = _build_satisfaction_formateurs_dashboard_context(request)
        all_rows = ctx.get("all_rows", [])
        print(f"   Nombre d'enregistrements: {len(all_rows)}")
        
        print("\n2. Analyse détaillée des enregistrements...")
        for i, record in enumerate(all_rows[:3]):
            print(f"\n   Record {i+1}:")
            print(f"     Type: {type(record)}")
            
            if isinstance(record, dict):
                print(f"     Clés du dictionnaire: {list(record.keys())}")
                print("     Contenu des clés:")
                for key, value in record.items():
                    print(f"       {key}: {repr(value)}")
            else:
                # Si c'est un objet
                print(f"     Attributs: {dir(record)}")
                for attr in dir(record):
                    if not attr.startswith('_'):
                        try:
                            value = getattr(record, attr)
                            print(f"       {attr}: {repr(value)}")
                        except Exception as e:
                            print(f"       {attr}: Erreur ({e})")
        
        return True
        
    except Exception as e:
        print(f"ERREUR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_formateur_record_value_function():
    """Test la fonction _formateur_record_value pour voir comment elle extrait les données"""
    
    print("\n=== TEST FONCTION _formateur_record_value ===\n")
    
    try:
        from App_PADESCE.core.public_views import _build_satisfaction_formateurs_dashboard_context, _formateur_record_value
        from django.test import RequestFactory
        
        # Créer une requête
        factory = RequestFactory()
        request = factory.get('/?scope=formateur&section=stats')
        
        print("1. Obtention du contexte...")
        ctx = _build_satisfaction_formateurs_dashboard_context(request)
        all_rows = ctx.get("all_rows", [])
        
        if not all_rows:
            print("Aucun enregistrement à analyser")
            return True
        
        print("2. Test d'extraction avec _formateur_record_value...")
        record = all_rows[0]
        
        # Tester différents champs
        test_fields = ['prestataire', 'beneficiaire', 'formation', 'classe', 'prestation']
        
        for field in test_fields:
            try:
                value = _formateur_record_value(record, field, "DEFAULT")
                print(f"   {field}: {repr(value)}")
            except Exception as e:
                print(f"   {field}: Erreur ({e})")
        
        return True
        
    except Exception as e:
        print(f"ERREUR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def analyze_classe_resolution():
    """Analyse comment la fonction _resolve_formateur_classe fonctionne"""
    
    print("\n=== ANALYSE RÉSOLUTION CLASSE ===\n")
    
    try:
        from App_PADESCE.core.public_views import _build_satisfaction_formateurs_dashboard_context, _resolve_formateur_classe
        from django.test import RequestFactory
        
        # Créer une requête
        factory = RequestFactory()
        request = factory.get('/?scope=formateur&section=stats')
        
        print("1. Obtention du contexte...")
        ctx = _build_satisfaction_formateurs_dashboard_context(request)
        all_rows = ctx.get("all_rows", [])
        
        if not all_rows:
            print("Aucun enregistrement à analyser")
            return True
        
        print("2. Test de résolution de classe...")
        resolution_cache = {}
        
        for i, record in enumerate(all_rows[:3]):
            print(f"\n   Record {i+1}:")
            try:
                classe = _resolve_formateur_classe(record, resolution_cache)
                print(f"     Classe: {classe}")
                print(f"     Type classe: {type(classe)}")
                
                if hasattr(classe, 'prestation'):
                    prestation = getattr(classe, 'prestation', None)
                    print(f"     Prestation: {prestation}")
                    if prestation:
                        print(f"       Code prestation: {getattr(prestation, 'code', 'N/A')}")
                        print(f"       Type prestation: {type(prestation)}")
                        
                        # Vérifier si la prestation a des relations
                        if hasattr(prestation, 'prestataire'):
                            prestataire_obj = getattr(prestation, 'prestataire', None)
                            print(f"       Prestataire object: {prestataire_obj}")
                            if prestataire_obj:
                                print(f"         Nom prestataire: {getattr(prestataire_obj, 'raison_sociale', 'N/A')}")
                        
                        if hasattr(prestation, 'beneficiaire'):
                            beneficiaire_obj = getattr(prestation, 'beneficiaire', None)
                            print(f"       Bénéficiaire object: {beneficiaire_obj}")
                            if beneficiaire_obj:
                                print(f"         Nom bénéficiaire: {getattr(beneficiaire_obj, 'nom_structure', 'N/A')}")
                        
                        if hasattr(prestation, 'formation'):
                            formation_obj = getattr(prestation, 'formation', None)
                            print(f"       Formation object: {formation_obj}")
                            if formation_obj:
                                print(f"         Nom formation: {getattr(formation_obj, 'nom', 'N/A')}")
                
            except Exception as e:
                print(f"     Erreur résolution: {e}")
                import traceback
                traceback.print_exc()
        
        return True
        
    except Exception as e:
        print(f"ERREUR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    setup_django()
    
    print("ANALYSE APPROFONDIE DE LA STRUCTURE DES DONNÉES FORMATEURS\n")
    
    # Tests successifs
    tests = [
        ("Structure des enregistrements", analyze_formateur_record_structure),
        ("Test _formateur_record_value", test_formateur_record_value_function),
        ("Analyse résolution classe", analyze_classe_resolution),
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
    print("RÉSUMÉ DE L'ANALYSE")
    print('='*60)
    
    for test_name, success in results:
        status = "SUCCÈS" if success else "ÉCHEC"
        print(f"{test_name}: {status}")
    
    sys.exit(0)

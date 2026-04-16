#!/usr/bin/env python3
"""
Analyse pourquoi seulement certains enregistrements ont une classe résolue
et comment améliorer le mapping pour tous les enregistrements
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

def analyze_classe_resolution_patterns():
    """Analyse les patterns de résolution de classe"""
    
    print("=== ANALYSE DES PATTERNS DE RÉSOLUTION DE CLASSE ===\n")
    
    try:
        from App_PADESCE.core.public_views import _build_satisfaction_formateurs_dashboard_context, _resolve_formateur_classe
        from django.test import RequestFactory
        
        # Créer une requête
        factory = RequestFactory()
        request = factory.get('/?scope=formateur&section=stats')
        
        print("1. Obtention du contexte...")
        ctx = _build_satisfaction_formateurs_dashboard_context(request)
        all_rows = ctx.get("all_rows", [])
        
        print(f"   Nombre total d'enregistrements: {len(all_rows)}")
        
        # Analyser tous les enregistrements
        resolved_count = 0
        unresolved_count = 0
        resolved_prestations = []
        unresolved_records = []
        
        resolution_cache = {}
        
        for i, record in enumerate(all_rows):
            try:
                classe = _resolve_formateur_classe(record, resolution_cache)
                
                if classe is not None:
                    resolved_count += 1
                    prestation = getattr(classe, "prestation", None)
                    if prestation:
                        code = getattr(prestation, "code", None)
                        resolved_prestations.append({
                            'record_index': i,
                            'record_id': getattr(record, 'id', None),
                            'code': code,
                            'formation': _formateur_record_value(record, "formation", ""),
                            'prestataire': _formateur_record_value(record, "prestataire", ""),
                            'beneficiaire': _formateur_record_value(record, "beneficiaire", ""),
                        })
                else:
                    unresolved_count += 1
                    unresolved_records.append({
                        'record_index': i,
                        'record_id': getattr(record, 'id', None),
                        'formation': _formateur_record_value(record, "formation", ""),
                        'prestataire': _formateur_record_value(record, "prestataire", ""),
                        'beneficiaire': _formateur_record_value(record, "beneficiaire", ""),
                    })
                    
            except Exception as e:
                unresolved_count += 1
                print(f"   Erreur résolution record {i}: {e}")
        
        print(f"\n2. Statistiques de résolution:")
        print(f"   Enregistrements résolus: {resolved_count}")
        print(f"   Enregistrements non résolus: {unresolved_count}")
        print(f"   Taux de résolution: {resolved_count/len(all_rows)*100:.1f}%")
        
        print(f"\n3. Exemples d'enregistrements résolus:")
        for item in resolved_prestations[:5]:
            print(f"   Record {item['record_index']} (ID: {item['record_id']}):")
            print(f"     Code: {item['code']}")
            print(f"     Formation: '{item['formation']}'")
            print(f"     Prestataire: '{item['prestataire']}'")
            print(f"     Bénéficiaire: '{item['beneficiaire']}'")
            print()
        
        print(f"\n4. Exemples d'enregistrements non résolus:")
        for item in unresolved_records[:5]:
            print(f"   Record {item['record_index']} (ID: {item['record_id']}):")
            print(f"     Formation: '{item['formation']}'")
            print(f"     Prestataire: '{item['prestataire']}'")
            print(f"     Bénéficiaire: '{item['beneficiaire']}'")
            print()
        
        return True
        
    except Exception as e:
        print(f"ERREUR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_formation_based_mapping():
    """Test un mapping basé uniquement sur les noms de formation"""
    
    print("\n=== TEST MAPPING BASÉ SUR LES FORMATIONS ===\n")
    
    try:
        from django.db import connection
        
        # Obtenir toutes les formations avec leurs prestations
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT f.nom as formation_nom, p.code as prestation_code, 
                       pr.raison_sociale as prestataire_nom, b.nom_structure as beneficiaire_nom
                FROM formations_formation f
                LEFT JOIN formations_prestation p ON f.id = p.formation_id
                LEFT JOIN formations_prestataire pr ON p.prestataire_id = pr.id
                LEFT JOIN formations_beneficiaire b ON p.beneficiaire_id = b.id
                WHERE p.actif = 1
                ORDER BY f.nom
            """)
            formation_prestations = cursor.fetchall()
        
        print(f"Nombre de formations avec prestations: {len(formation_prestations)}")
        
        # Créer un mapping formation -> prestation
        formation_mapping = {}
        for formation_nom, prestation_code, prestataire_nom, beneficiaire_nom in formation_prestations:
            formation_nom_clean = str(formation_nom or "").strip().lower()
            if formation_nom_clean and prestation_code:
                if formation_nom_clean not in formation_mapping:
                    formation_mapping[formation_nom_clean] = []
                formation_mapping[formation_nom_clean].append({
                    'code': prestation_code,
                    'prestataire': prestataire_nom,
                    'beneficiaire': beneficiaire_nom
                })
        
        print(f"Mapping créé avec {len(formation_mapping)} formations uniques")
        
        # Tester avec quelques exemples de formations non résolues
        test_formations = [
            "Apiculture",
            "Trafnsformation of chocolate bar and paste",
            "EMPOWER FEMALES DROPOUTS",
            "Small Ruminants",
            "transformation of cocoa"
        ]
        
        print("\nTest de mapping par formation:")
        for formation in test_formations:
            formation_clean = formation.lower()
            matches = []
            
            # Recherche exacte
            if formation_clean in formation_mapping:
                matches = formation_mapping[formation_clean]
            else:
                # Recherche partielle
                for key, prestations in formation_mapping.items():
                    if formation_clean in key or key in formation_clean:
                        matches.extend(prestations)
                        break
            
            if matches:
                print(f"  '{formation}' -> {len(matches)} correspondance(s)")
                for match in matches[:3]:
                    print(f"    {match['code']} - {match['prestataire']}")
            else:
                print(f"  '{formation}' -> Aucune correspondance")
        
        return True
        
    except Exception as e:
        print(f"ERREUR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    setup_django()
    
    print("ANALYSE APPROFONDIE DE LA RÉSOLUTION ET MAPPING\n")
    
    # Tests successifs
    tests = [
        ("Analyse patterns de résolution", analyze_classe_resolution_patterns),
        ("Test mapping par formation", test_formation_based_mapping),
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

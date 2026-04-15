#!/usr/bin/env python3
"""
Script pour analyser pourquoi le mapping génère des codes synthétiques
au lieu de trouver les vrais codes PRESTAXXX
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

def analyze_formateur_vs_prestation_data():
    """Analyse les données formateurs vs prestations pour comprendre le mapping"""
    
    print("=== ANALYSE FORMATEURS vs PRESTATIONS ===\n")
    
    try:
        from App_PADESCE.core.public_views import _build_satisfaction_formateurs_dashboard_context
        from django.db import connection
        from django.test import RequestFactory
        
        # Créer une requête
        factory = RequestFactory()
        request = factory.get('/?scope=formateur&section=stats')
        
        print("1. Obtention des données formateurs...")
        ctx = _build_satisfaction_formateurs_dashboard_context(request)
        all_rows = ctx.get("all_rows", [])
        print(f"   Nombre d'enregistrements formateurs: {len(all_rows)}")
        
        print("\n2. Obtention des prestations de la base...")
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT p.code, pr.raison_sociale as prestataire_nom, 
                       b.nom_structure as beneficiaire_nom, f.nom as formation_nom
                FROM formations_prestation p
                LEFT JOIN formations_prestataire pr ON p.prestataire_id = pr.id
                LEFT JOIN formations_beneficiaire b ON p.beneficiaire_id = b.id  
                LEFT JOIN formations_formation f ON p.formation_id = f.id
                WHERE p.actif = 1
                ORDER BY p.code
            """)
            prestations = cursor.fetchall()
            print(f"   Nombre de prestations actives: {len(prestations)}")
        
        print("\n3. Analyse des premiers enregistrements formateurs...")
        for i, record in enumerate(all_rows[:5]):
            print(f"\n   Record {i+1}:")
            print(f"     Type: {type(record)}")
            
            # Extraire les données pertinentes
            prestataire_val = str(record.get('prestataire', '')).strip() if isinstance(record, dict) else str(getattr(record, 'prestataire', '')).strip()
            beneficiaire_val = str(record.get('beneficiaire', '')).strip() if isinstance(record, dict) else str(getattr(record, 'beneficiaire', '')).strip()
            formation_val = str(record.get('formation', '')).strip() if isinstance(record, dict) else str(getattr(record, 'formation', '')).strip()
            
            print(f"     Prestataire: '{prestataire_val}'")
            print(f"     Bénéficiaire: '{beneficiaire_val}'")
            print(f"     Formation: '{formation_val}'")
            
            # Chercher des correspondances possibles dans les prestations
            print(f"     Correspondances possibles:")
            matches = []
            for code, prestataire_db, beneficiaire_db, formation_db in prestations[:10]:
                prestataire_db = str(prestataire_db or '').lower()
                beneficiaire_db = str(beneficiaire_db or '').lower()
                formation_db = str(formation_db or '').lower()
                
                score = 0
                prestataire_clean = prestataire_val.lower()
                beneficiaire_clean = beneficiaire_val.lower()
                formation_clean = formation_val.lower()
                
                # Vérifier les correspondances
                if prestataire_clean and prestataire_db:
                    if prestataire_clean == prestataire_db:
                        score += 5
                    elif prestataire_clean in prestataire_db or prestataire_db in prestataire_clean:
                        score += 3
                
                if beneficiaire_clean and beneficiaire_db:
                    if beneficiaire_clean == beneficiaire_db:
                        score += 3
                    elif beneficiaire_clean in beneficiaire_db or beneficiaire_db in beneficiaire_clean:
                        score += 2
                
                if formation_clean and formation_db:
                    if formation_clean == formation_db:
                        score += 4
                    elif formation_clean in formation_db or formation_db in formation_clean:
                        score += 2
                
                if score >= 3:  # Seuil minimum
                    matches.append((code, score, prestataire_db, beneficiaire_db, formation_db))
            
            if matches:
                matches.sort(key=lambda x: x[1], reverse=True)
                for code, score, prest, benef, form in matches[:3]:
                    print(f"       {code} (score: {score}) - {prest} / {benef} / {form}")
            else:
                print(f"       Aucune correspondance trouvée")
        
        return True
        
    except Exception as e:
        print(f"ERREUR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mapping_function_directly():
    """Test la fonction de mapping directement"""
    
    print("\n=== TEST DIRECT DE LA FONCTION DE MAPPING ===\n")
    
    try:
        from django.db import connection
        
        # Créer le mapping comme dans la fonction
        prestation_mapping = {}
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT p.code, p.id, pr.raison_sociale as prestataire_nom, 
                       b.nom_structure as beneficiaire_nom, f.nom as formation_nom
                FROM formations_prestation p
                LEFT JOIN formations_prestataire pr ON p.prestataire_id = pr.id
                LEFT JOIN formations_beneficiaire b ON p.beneficiaire_id = b.id  
                LEFT JOIN formations_formation f ON p.formation_id = f.id
                WHERE p.actif = 1
            """)
            prestations_info = cursor.fetchall()
            
            for code, id, prestataire_nom, beneficiaire_nom, formation_nom in prestations_info:
                prestation_mapping[code] = {
                    'id': id,
                    'prestataire_nom': str(prestataire_nom or "").strip().lower(),
                    'beneficiaire_nom': str(beneficiaire_nom or "").strip().lower(),
                    'formation_nom': str(formation_nom or "").strip().lower()
                }
        
        print(f"Mapping créé avec {len(prestation_mapping)} prestations")
        
        # Tester quelques exemples
        test_cases = [
            ("CFEM", "SCOOPSDESA", ""),
            ("PRESTA001", "CFP FAMEAC", "Réparation des engins agricoles"),
            ("NAT-TECHNOLOGIES", "ASENIA", ""),
        ]
        
        def find_best_prestation_match(prestataire_val, beneficiaire_val, formation_val):
            """Version simplifiée de la fonction de mapping"""
            prestataire_clean = str(prestataire_val or "").strip().lower()
            beneficiaire_clean = str(beneficiaire_val or "").strip().lower()
            formation_clean = str(formation_val or "").strip().lower()
            
            best_match = None
            best_score = 0
            
            for code, info in prestation_mapping.items():
                score = 0
                
                # Compare prestataires
                if prestataire_clean and info['prestataire_nom']:
                    if prestataire_clean == info['prestataire_nom']:
                        score += 5
                    elif prestataire_clean in info['prestataire_nom'] or info['prestataire_nom'] in prestataire_clean:
                        score += 3
                    elif any(word in info['prestataire_nom'] for word in prestataire_clean.split() if len(word) > 2):
                        score += 2
                
                # Compare bénéficiaires
                if beneficiaire_clean and info['beneficiaire_nom']:
                    if beneficiaire_clean == info['beneficiaire_nom']:
                        score += 3
                    elif beneficiaire_clean in info['beneficiaire_nom'] or info['beneficiaire_nom'] in beneficiaire_clean:
                        score += 2
                
                # Compare formations
                if formation_clean and info["formation_nom"]:
                    if formation_clean == info["formation_nom"]:
                        score += 4
                    elif formation_clean in info["formation_nom"] or info["formation_nom"] in formation_clean:
                        score += 2
                
                if score > best_score and score >= 2:
                    best_score = score
                    best_match = code
            
            return best_match, best_score
        
        print("\nTests de mapping:")
        for prestataire, beneficiaire, formation in test_cases:
            match, score = find_best_prestation_match(prestataire, beneficiaire, formation)
            print(f"  '{prestataire}' + '{beneficiaire}' -> {match or 'Aucune correspondance'} (score: {score})")
        
        return True
        
    except Exception as e:
        print(f"ERREUR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    setup_django()
    
    print("DIAGNOSTIC DU PROBLÈME DE MAPPING\n")
    
    # Tests successifs
    tests = [
        ("Analyse formateurs vs prestations", analyze_formateur_vs_prestation_data),
        ("Test fonction mapping", test_mapping_function_directly),
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
    
    sys.exit(0)

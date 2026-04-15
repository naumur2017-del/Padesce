#!/usr/bin/env python3
"""
Script pour analyser comment trouver les vrais IDs de prestations
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

def analyze_prestation_mapping():
    """Analyse la relation entre formateurs et prestations réelles"""
    
    with connection.cursor() as cursor:
        print("=== ANALYSE DES RELATIONS FORMATEUR-PRESTATION ===\n")
        
        # 1. Vérifier les prestations réelles dans la base
        cursor.execute("""
            SELECT code, titre, actif 
            FROM formations_prestation 
            WHERE actif = 1
            ORDER BY code
        """)
        real_prestations = cursor.fetchall()
        
        print(f"Prestations réelles dans la base ({len(real_prestations)}):")
        for code, titre, actif in real_prestations[:10]:
            print(f"  {code}: {titre}")
        
        # 2. Analyser les données de formateurs avec leurs prestataires/bénéficiaires
        cursor.execute("""
            SELECT DISTINCT prestataire, beneficiaire, COUNT(*) as nb_formateurs
            FROM appels_appelformateur 
            WHERE q1_prerequis_apprenants IS NOT NULL 
              AND q2_interaction_apprenants IS NOT NULL 
              AND q3_competences_acquises IS NOT NULL
            GROUP BY prestataire, beneficiaire
            ORDER BY nb_formateurs DESC
        """)
        formateur_groups = cursor.fetchall()
        
        print(f"\nGroupes de formateurs avec scores ({len(formateur_groups)}):")
        for prestataire, beneficiaire, count in formateur_groups[:10]:
            print(f"  {prestataire} | {beneficiaire}: {count} formateurs")
        
        # 3. Chercher des correspondances entre les groupes de formateurs et les prestations réelles
        print(f"\n=== RECHERCHE DE CORRESPONDANCES ===\n")
        
        matches = []
        for prestataire, beneficiaire, count in formateur_groups:
            # Normaliser les chaînes pour la comparaison
            prestataire_clean = str(prestataire or "").strip().lower()
            beneficiaire_clean = str(beneficiaire or "").strip().lower()
            
            if not prestataire_clean or prestataire_clean == "-":
                continue
                
            # Chercher dans les prestations réelles
            for code, titre, actif in real_prestations:
                titre_clean = str(titre or "").strip().lower()
                
                # Vérifier si le prestataire correspond au titre de la prestation
                if prestataire_clean in titre_clean or titre_clean in prestataire_clean:
                    matches.append({
                        'prestataire_formateur': prestataire,
                        'beneficiaire_formateur': beneficiaire,
                        'prestation_code': code,
                        'prestation_titre': titre,
                        'nb_formateurs': count,
                        'match_type': 'prestataire_titre'
                    })
                    break
                    
                # Vérifier si le bénéficiaire correspond
                if beneficiaire_clean and beneficiaire_clean in titre_clean:
                    matches.append({
                        'prestataire_formateur': prestataire,
                        'beneficiaire_formateur': beneficiaire,
                        'prestation_code': code,
                        'prestation_titre': titre,
                        'nb_formateurs': count,
                        'match_type': 'beneficiaire_titre'
                    })
                    break
        
        print(f"Correspondances trouvées ({len(matches)}):")
        for match in matches[:10]:
            print(f"  {match['prestation_code']}: {match['prestation_titre']}")
            print(f"    <- {match['prestataire_formateur']} | {match['beneficiaire_formateur']}")
            print(f"    Type: {match['match_type']}, Formateurs: {match['nb_formateurs']}")
            print()
        
        # 4. Analyser les formateurs qui n'ont pas de correspondance
        matched_prestataires = set(match['prestataire_formateur'] for match in matches)
        unmatched = [g for g in formateur_groups if g[0] not in matched_prestataires]
        
        print(f"Groupes sans correspondance ({len(unmatched)}):")
        for prestataire, beneficiaire, count in unmatched[:5]:
            print(f"  {prestataire} | {beneficiaire}: {count} formateurs")

if __name__ == "__main__":
    setup_django()
    analyze_prestation_mapping()

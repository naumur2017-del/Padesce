#!/usr/bin/env python3
"""
Script pour créer un mapping entre les données de formateurs et les vraies prestations
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

def create_prestation_mapping():
    """Crée un mapping pour trouver les vraies prestations"""
    
    with connection.cursor() as cursor:
        print("=== CRÉATION DU MAPPING PRESTATIONS ===\n")
        
        # 1. Obtenir toutes les prestations avec leurs informations
        cursor.execute("""
            SELECT p.code, p.id, pr.raison_sociale as prestataire_nom, b.nom_structure as beneficiaire_nom, f.nom as formation_nom
            FROM formations_prestation p
            LEFT JOIN formations_prestataire pr ON p.prestataire_id = pr.id
            LEFT JOIN formations_beneficiaire b ON p.beneficiaire_id = b.id  
            LEFT JOIN formations_formation f ON p.formation_id = f.id
            WHERE p.actif = 1
        """)
        prestations_info = cursor.fetchall()
        
        print(f"Prestations avec informations ({len(prestations_info)}):")
        for code, id, prestataire_nom, beneficiaire_nom, formation_nom in prestations_info[:10]:
            print(f"  {code} (ID: {id}): {prestataire_nom} | {beneficiaire_nom} | {formation_nom}")
        
        # 2. Analyser les groupes de formateurs
        cursor.execute("""
            SELECT prestataire, beneficiaire, formation, COUNT(*) as nb_formateurs,
                   GROUP_CONCAT(id) as formateur_ids
            FROM appels_appelformateur 
            WHERE q1_prerequis_apprenants IS NOT NULL 
              AND q2_interaction_apprenants IS NOT NULL 
              AND q3_competences_acquises IS NOT NULL
              AND prestataire IS NOT NULL 
              AND prestataire != ''
            GROUP BY prestataire, beneficiaire, formation
            ORDER BY nb_formateurs DESC
        """)
        formateur_groups = cursor.fetchall()
        
        print(f"\nGroupes de formateurs avec scores ({len(formateur_groups)}):")
        for prestataire, beneficiaire, formation, count, ids in formateur_groups[:10]:
            print(f"  {prestataire} | {beneficiaire} | {formation}: {count} formateurs")
        
        # 3. Créer le mapping en utilisant les noms
        mapping = {}
        
        for prestataire, beneficiaire, formation, count, ids in formateur_groups:
            best_match = None
            best_score = 0
            
            # Normaliser les chaînes pour comparaison
            prestataire_clean = str(prestataire or "").strip().lower()
            beneficiaire_clean = str(beneficiaire or "").strip().lower()
            formation_clean = str(formation or "").strip().lower()
            
            for code, id, prestataire_nom, beneficiaire_nom, formation_nom in prestations_info:
                prestataire_db = str(prestataire_nom or "").strip().lower()
                beneficiaire_db = str(beneficiaire_nom or "").strip().lower()
                formation_db = str(formation_nom or "").strip().lower()
                
                score = 0
                
                # Comparaison des prestataires
                if prestataire_clean and prestataire_db:
                    if prestataire_clean == prestataire_db:
                        score += 3
                    elif prestataire_clean in prestataire_db or prestataire_db in prestataire_clean:
                        score += 2
                
                # Comparaison des bénéficiaires
                if beneficiaire_clean and beneficiaire_db:
                    if beneficiaire_clean == beneficiaire_db:
                        score += 2
                    elif beneficiaire_clean in beneficiaire_db or beneficiaire_db in beneficiaire_clean:
                        score += 1
                
                # Comparaison des formations
                if formation_clean and formation_db:
                    if formation_clean == formation_db:
                        score += 1
                    elif formation_clean in formation_db or formation_db in formation_clean:
                        score += 0.5
                
                if score > best_score and score >= 2:  # Score minimum de 2 requis
                    best_score = score
                    best_match = {
                        'prestation_code': code,
                        'prestation_id': id,
                        'score': score
                    }
            
            if best_match:
                key = f"{prestataire}|{beneficiaire}|{formation}"
                mapping[key] = best_match
                print(f"  Mapping: {key[:50]}... -> {best_match['prestation_code']} (score: {best_match['score']})")
        
        print(f"\nMapping créé: {len(mapping)} correspondances")
        
        # 4. Afficher les résultats
        print(f"\n=== RÉSULTATS DU MAPPING ===\n")
        
        for key, match in list(mapping.items())[:10]:
            print(f"{key} -> {match['prestation_code']} (score: {match['score']})")
        
        return mapping

if __name__ == "__main__":
    setup_django()
    create_prestation_mapping()

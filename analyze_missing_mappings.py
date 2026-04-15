#!/usr/bin/env python3
"""
Script pour analyser pourquoi certains formateurs ne sont pas mappés vers des PRESTAXXX
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

def analyze_missing_mappings():
    """Analyse les formateurs qui ne sont pas mappés vers des PRESTAXXX"""
    
    with connection.cursor() as cursor:
        print("=== ANALYSE DES MAPPINGS MANQUANTS ===\n")
        
        # 1. Obtenir les groupes de formateurs avec scores qui ne sont pas mappés
        cursor.execute("""
            SELECT prestataire, beneficiaire, formation, COUNT(*) as nb_formateurs
            FROM appels_appelformateur 
            WHERE q1_prerequis_apprenants IS NOT NULL 
              AND q2_interaction_apprenants IS NOT NULL 
              AND q3_competences_acquises IS NOT NULL
            GROUP BY prestataire, beneficiaire, formation
            ORDER BY nb_formateurs DESC
        """)
        all_formateur_groups = cursor.fetchall()
        
        print(f"Total groupes de formateurs avec scores: {len(all_formateur_groups)}")
        
        # 2. Obtenir toutes les prestations disponibles
        cursor.execute("""
            SELECT p.code, p.id, pr.raison_sociale as prestataire_nom, b.nom_structure as beneficiaire_nom, f.nom as formation_nom
            FROM formations_prestation p
            LEFT JOIN formations_prestataire pr ON p.prestataire_id = pr.id
            LEFT JOIN formations_beneficiaire b ON p.beneficiaire_id = b.id  
            LEFT JOIN formations_formation f ON p.formation_id = f.id
            WHERE p.actif = 1
        """)
        all_prestations = cursor.fetchall()
        
        print(f"Total prestations disponibles: {len(all_prestations)}")
        
        # 3. Tester chaque groupe de formateurs contre toutes les prestations
        matched_groups = []
        unmatched_groups = []
        
        for prestataire, beneficiaire, formation, count in all_formateur_groups:
            best_match = None
            best_score = 0
            
            # Normaliser les chaînes
            prestataire_clean = str(prestataire or "").strip().lower()
            beneficiaire_clean = str(beneficiaire or "").strip().lower()
            formation_clean = str(formation or "").strip().lower()
            
            for code, id, prestataire_nom, beneficiaire_nom, formation_nom in all_prestations:
                prestataire_db = str(prestataire_nom or "").strip().lower()
                beneficiaire_db = str(beneficiaire_nom or "").strip().lower()
                formation_db = str(formation_nom or "").strip().lower()
                
                score = 0
                
                # Comparaison plus flexible
                if prestataire_clean and prestataire_db:
                    # Correspondance exacte
                    if prestataire_clean == prestataire_db:
                        score += 5
                    # Correspondance partielle (contient)
                    elif prestataire_clean in prestataire_db or prestataire_db in prestataire_clean:
                        score += 3
                    # Correspondance par mots-clés
                    elif any(word in prestataire_db for word in prestataire_clean.split() if len(word) > 2):
                        score += 2
                    elif any(word in prestataire_clean for word in prestataire_db.split() if len(word) > 2):
                        score += 2
                
                if beneficiaire_clean and beneficiaire_db:
                    if beneficiaire_clean == beneficiaire_db:
                        score += 3
                    elif beneficiaire_clean in beneficiaire_db or beneficiaire_db in beneficiaire_clean:
                        score += 2
                    elif any(word in beneficiaire_db for word in beneficiaire_clean.split() if len(word) > 2):
                        score += 1
                
                if formation_clean and formation_db:
                    if formation_clean == formation_db:
                        score += 2
                    elif formation_clean in formation_db or formation_db in formation_clean:
                        score += 1
                    elif any(word in formation_db for word in formation_clean.split() if len(word) > 2):
                        score += 0.5
                
                if score > best_score and score >= 3:  # Score minimum réduit à 3
                    best_score = score
                    best_match = (code, score)
            
            if best_match:
                matched_groups.append((prestataire, beneficiaire, formation, count, best_match))
            else:
                unmatched_groups.append((prestataire, beneficiaire, formation, count))
        
        print(f"\nGroupes mappés: {len(matched_groups)}")
        print(f"Groupes non mappés: {len(unmatched_groups)}")
        
        # 4. Analyser les groupes non mappés
        print(f"\n=== GROUPES NON MAPPÉS ===\n")
        for prestataire, beneficiaire, formation, count in unmatched_groups[:10]:
            print(f"Prestataire: {prestataire}")
            print(f"Bénéficiaire: {beneficiaire}")
            print(f"Formation: {formation}")
            print(f"Formateurs: {count}")
            print("---")
        
        # 5. Suggestions pour améliorer le mapping
        print(f"\n=== SUGGESTIONS D'AMÉLIORATION ===\n")
        
        # Chercher des correspondances manuelles évidentes
        for prestataire, beneficiaire, formation, count in unmatched_groups:
            prestataire_clean = str(prestataire or "").strip().lower()
            
            # Chercher dans les prestations par mots-clés
            for code, id, prestataire_nom, beneficiaire_nom, formation_nom in all_prestations:
                prestataire_db = str(prestataire_nom or "").strip().lower()
                
                # Correspondances évidentes manquées
                if "cfem" in prestataire_clean and "cfem" in prestataire_db:
                    print(f"Correspondance manquée: {prestataire} -> {code} ({formation_nom})")
                elif "nat" in prestataire_clean and "nat" in prestataire_db:
                    print(f"Correspondance manquée: {prestataire} -> {code} ({formation_nom})")
                elif "cfp" in prestataire_clean and "cfp" in prestataire_db:
                    print(f"Correspondance manquée: {prestataire} -> {code} ({formation_nom})")

if __name__ == "__main__":
    setup_django()
    analyze_missing_mappings()

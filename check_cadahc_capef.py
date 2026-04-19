#!/usr/bin/env python
"""
Script pour vérifier les moyennes pour la combinaison CADAHC-CAPEF
"""

import sqlite3
import os

def _avg_num(values):
    """Fonction de calcul de moyenne robuste"""
    nums = []
    for v in values:
        if v is not None:
            try:
                if isinstance(v, (int, float)):
                    nums.append(v)
                else:
                    nums.append(float(v))
            except (ValueError, TypeError):
                continue
    return round(sum(nums) / len(nums), 2) if nums else 0

def main():
    db_path = "c:\\Users\\LENOVO\\Downloads\\backup_20260416_145722.sqlite3"
    
    print("=== Vérification des moyennes pour CADAHC-CAPEF ===\n")
    
    try:
        # Connexion directe à la base de données
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Rechercher spécifiquement la combinaison CADAHC-CAPEF
        cursor.execute("""
            SELECT reference_code, prestataire, beneficiaire, 
                   q1_prerequis_apprenants, q2_interaction_apprenants, q3_competences_acquises,
                   cohorte, session_date, status
            FROM appels_appelformateur 
            WHERE is_active = 1 
            AND (UPPER(prestataire) LIKE '%CADAHC%' OR UPPER(beneficiaire) LIKE '%CAPEF%')
            ORDER BY reference_code
        """)
        records = cursor.fetchall()
        
        print(f"Recherche de la combinaison CADAHC-CAPEF...")
        print(f"Nombre d'enregistrements trouvés: {len(records)}")
        
        if records:
            print(f"\n=== Détails des enregistrements CADAHC-CAPEF ===")
            for i, record in enumerate(records, 1):
                print(f"\nEnregistrement {i}:")
                print(f"  Code: {record[0]}")
                print(f"  Prestataire: {record[1]}")
                print(f"  Bénéficiaire: {record[2]}")
                print(f"  Cohorte: {record[6]}")
                print(f"  Date: {record[7]}")
                print(f"  Statut: {record[8]}")
                print(f"  Q1 (Prérequis): {record[3]}")
                print(f"  Q2 (Interactions): {record[4]}")
                print(f"  Q3 (Compétences): {record[5]}")
            
            # Calculer les moyennes pour cette combinaison spécifique
            q1_values = [r[3] for r in records if r[3] is not None]
            q2_values = [r[4] for r in records if r[4] is not None]
            q3_values = [r[5] for r in records if r[5] is not None]
            
            print(f"\n=== Moyennes calculées pour CADAHC-CAPEF ===")
            print(f"Q1 - Prérequis apprenants: {_avg_num(q1_values)}")
            print(f"Q2 - Interactions apprenants: {_avg_num(q2_values)}")
            print(f"Q3 - Compétences acquises: {_avg_num(q3_values)}")
            print(f"Nombre total d'appels: {len(records)}")
            print(f"Appels avec scores: {len([r for r in records if r[3] is not None or r[4] is not None or r[5] is not None])}")
            
            # Vérifier s'il y a une prestation officielle correspondante
            cursor.execute("""
                SELECT p.code, pr.raison_sociale as prestataire_nom, 
                       b.nom_structure as beneficiaire_nom
                FROM formations_prestation p
                LEFT JOIN formations_prestataire pr ON p.prestataire_id = pr.id
                LEFT JOIN formations_beneficiaire b ON p.beneficiaire_id = b.id
                WHERE p.actif = 1
                AND (UPPER(pr.raison_sociale) LIKE '%CADAHC%' OR UPPER(b.nom_structure) LIKE '%CAPEF%')
            """)
            prestations_officielles = cursor.fetchall()
            
            if prestations_officielles:
                print(f"\n=== Prestations officielles correspondantes ===")
                for code, prestataire_nom, beneficiaire_nom in prestations_officielles:
                    print(f"  Code: {code}")
                    print(f"  Prestataire: {prestataire_nom}")
                    print(f"  Bénéficiaire: {beneficiaire_nom}")
            else:
                print(f"\nAucune prestation officielle trouvée pour CADAHC-CAPEF")
        
        else:
            print("Aucun enregistrement trouvé pour CADAHC-CAPEF")
            
            # Rechercher des enregistrements CADAHC ou CAPEF séparément
            cursor.execute("""
                SELECT reference_code, prestataire, beneficiaire, 
                       q1_prerequis_apprenants, q2_interaction_apprenants, q3_competences_acquises
                FROM appels_appelformateur 
                WHERE is_active = 1 
                AND (UPPER(prestataire) LIKE '%CADAHC%' OR UPPER(beneficiaire) LIKE '%CAPEF%')
                LIMIT 10
            """)
            similar_records = cursor.fetchall()
            
            if similar_records:
                print(f"\n=== Enregistrements similaires trouvés ===")
                for i, record in enumerate(similar_records, 1):
                    print(f"{i}. {record[0]} - {record[1]} - {record[2]}")
                    print(f"   Q1: {record[3]}, Q2: {record[4]}, Q3: {record[5]}")
        
        conn.close()
        print(f"\n=== Vérification terminée ===")
        
    except Exception as e:
        print(f"ERREUR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

#!/usr/bin/env python
"""
Script pour vérifier spécifiquement les moyennes de la prestation PRESTA008
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
    
    print("=== Vérification des moyennes pour PRESTA008 ===\n")
    
    try:
        # Connexion directe à la base de données
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Rechercher spécifiquement PRESTA008
        cursor.execute("""
            SELECT reference_code, prestataire, beneficiaire, 
                   q1_prerequis_apprenants, q2_interaction_apprenants, q3_competences_acquises,
                   cohorte, session_date, status
            FROM appels_appelformateur 
            WHERE is_active = 1 AND UPPER(reference_code) LIKE '%PRESTA008%'
            ORDER BY reference_code
        """)
        records = cursor.fetchall()
        
        print(f"Recherche de PRESTA008...")
        print(f"Nombre d'enregistrements trouvés: {len(records)}")
        
        if records:
            print(f"\n=== Détails des enregistrements PRESTA008 ===")
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
            
            # Calculer les moyennes
            q1_values = [r[3] for r in records if r[3] is not None]
            q2_values = [r[4] for r in records if r[4] is not None]
            q3_values = [r[5] for r in records if r[5] is not None]
            
            print(f"\n=== Calcul des moyennes pour PRESTA008 ===")
            print(f"Q1 - Prérequis apprenants: {_avg_num(q1_values)}")
            print(f"Q2 - Interactions apprenants: {_avg_num(q2_values)}")
            print(f"Q3 - Compétences acquises: {_avg_num(q3_values)}")
            print(f"Nombre total d'appels: {len(records)}")
            print(f"Appels avec scores: {len([r for r in records if r[3] is not None or r[4] is not None or r[5] is not None])}")
            
        else:
            print("PRESTA008 non trouvé. Recherche des codes similaires...")
            
            # Rechercher des codes similaires
            cursor.execute("""
                SELECT DISTINCT reference_code
                FROM appels_appelformateur 
                WHERE is_active = 1 AND UPPER(reference_code) LIKE '%PRESTA%'
                ORDER BY reference_code
                LIMIT 20
            """)
            similar_codes = cursor.fetchall()
            
            if similar_codes:
                print(f"\nCodes de prestations similaires avec 'PRESTA':")
                for i, (code,) in enumerate(similar_codes, 1):
                    cursor.execute("""
                        SELECT COUNT(*) FROM appels_appelformateur 
                        WHERE is_active = 1 AND reference_code = ?
                    """, (code,))
                    count = cursor.fetchone()[0]
                    print(f"  {i}. {code} ({count} appels)")
            else:
                print("Aucune prestation avec 'PRESTA' trouvée.")
                
                # Afficher quelques exemples de codes existants
                cursor.execute("""
                    SELECT DISTINCT reference_code
                    FROM appels_appelformateur 
                    WHERE is_active = 1
                    ORDER BY reference_code
                    LIMIT 10
                """)
                sample_codes = cursor.fetchall()
                print(f"\nExemples de codes de prestations existants:")
                for i, (code,) in enumerate(sample_codes, 1):
                    print(f"  {i}. {code}")
        
        conn.close()
        print(f"\n=== Vérification terminée ===")
        
    except Exception as e:
        print(f"ERREUR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

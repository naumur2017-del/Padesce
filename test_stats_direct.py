#!/usr/bin/env python
"""
Script pour tester le calcul des statistiques directement avec les données du backup
sans passer par Django ORM pour éviter les problèmes de schéma.
"""

import sqlite3
import os

def _avg_num(values):
    """Fonction de calcul de moyenne robuste (copiée de views.py)"""
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
    
    print("=== Test des statistiques avec données réelles ===\n")
    
    try:
        # Connexion directe à la base de données
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Récupérer tous les enregistrements actifs avec les scores
        cursor.execute("""
            SELECT reference_code, prestataire, beneficiaire, 
                   q1_prerequis_apprenants, q2_interaction_apprenants, q3_competences_acquises,
                   cohorte
            FROM appels_appelformateur 
            WHERE is_active = 1
            ORDER BY reference_code
        """)
        records = cursor.fetchall()
        
        print(f"Nombre d'enregistrements actifs: {len(records)}")
        
        # Convertir en dictionnaire pour simuler la structure Django
        formatted_records = []
        for record in records:
            formatted_records.append({
                "reference_code": record[0],
                "prestataire": record[1] or "",
                "beneficiaire": record[2] or "",
                "q1_prerequis_apprenants": record[3],
                "q2_interaction_apprenants": record[4],
                "q3_competences_acquises": record[5],
                "cohorte": record[6] or "",
            })
        
        # Simuler la fonction _group_stats pour les prestations
        def _group_stats(key_fn):
            groups = {}
            for r in formatted_records:
                key = key_fn(r)
                if key not in groups:
                    groups[key] = []
                groups[key].append(r)
            
            return sorted([
                {
                    "label": k,
                    "nb": len(v),
                    "avgs": [_avg_num([r[field] for r in v]) for field in ["q1_prerequis_apprenants", "q2_interaction_apprenants", "q3_competences_acquises"]],
                }
                for k, v in groups.items()
            ], key=lambda x: x["label"])
        
        # Calculer les statistiques par prestation
        prestation_stats = _group_stats(lambda r: r["reference_code"] or "-")
        
        print(f"\n=== Statistiques par prestation ({len(prestation_stats)} prestations) ===")
        
        # Afficher les 10 premières prestations
        for i, stat in enumerate(prestation_stats[:10], 1):
            print(f"{i:2d}. {stat['label'][:50]:50s} | Nb: {stat['nb']:3d} | Q1: {stat['avgs'][0]:5.2f} | Q2: {stat['avgs'][1]:5.2f} | Q3: {stat['avgs'][2]:5.2f}")
        
        if len(prestation_stats) > 10:
            print(f"... et {len(prestation_stats) - 10} autres prestations")
        
        # Calculer les statistiques par prestataire
        prestataire_stats = _group_stats(lambda r: r["prestataire"] or "-")
        print(f"\n=== Statistiques par prestataire ({len(prestataire_stats)} prestataires) ===")
        
        for i, stat in enumerate(prestataire_stats[:5], 1):
            print(f"{i}. {stat['label'][:40]:40s} | Nb: {stat['nb']:3d} | Q1: {stat['avgs'][0]:5.2f} | Q2: {stat['avgs'][1]:5.2f} | Q3: {stat['avgs'][2]:5.2f}")
        
        # Calculer les statistiques par bénéficiaire
        beneficiaire_stats = _group_stats(lambda r: r["beneficiaire"] or "-")
        print(f"\n=== Statistiques par bénéficiaire ({len(beneficiaire_stats)} bénéficiaires) ===")
        
        for i, stat in enumerate(beneficiaire_stats[:5], 1):
            print(f"{i}. {stat['label'][:40]:40s} | Nb: {stat['nb']:3d} | Q1: {stat['avgs'][0]:5.2f} | Q2: {stat['avgs'][1]:5.2f} | Q3: {stat['avgs'][2]:5.2f}")
        
        # Vérifier les prestations avec des scores
        prestations_with_scores = [s for s in prestation_stats if any(avg > 0 for avg in s['avgs'])]
        print(f"\n=== Résumé ===")
        print(f"Prestations avec des scores: {len(prestations_with_scores)}/{len(prestation_stats)}")
        print(f"Total des appels avec scores: {sum(s['nb'] for s in prestations_with_scores)}")
        
        conn.close()
        print(f"\n=== Test terminé avec succès ===")
        
    except Exception as e:
        print(f"ERREUR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

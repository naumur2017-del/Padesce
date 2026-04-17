#!/usr/bin/env python
"""
Script pour tester la nouvelle logique de combinaison prestataire-bénéficiaire
avec les données réelles du backup
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
    
    print("=== Test de la nouvelle logique de combinaison ===\n")
    
    try:
        # Connexion directe à la base de données
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. Récupérer tous les enregistrements actifs
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
        
        # 2. Simuler la fonction _build_prestation_stats_with_combination()
        formateur_combinations = {}
        for r in records:
            prestataire = str(r[1] or "").strip().lower()
            beneficiaire = str(r[2] or "").strip().lower()
            reference_code = str(r[0] or "").strip()
            
            if not prestataire or not beneficiaire or not reference_code:
                continue
                
            combo_key = f"{prestataire}|{beneficiaire}"
            if combo_key not in formateur_combinations:
                formateur_combinations[combo_key] = {
                    "prestataire": r[1],
                    "beneficiaire": r[2],
                    "reference_codes": set(),
                    "q1_scores": [],
                    "q2_scores": [],
                    "q3_scores": [],
                    "form_count": 0
                }
            
            combo = formateur_combinations[combo_key]
            combo["reference_codes"].add(reference_code)
            combo["form_count"] += 1
            
            # Ajouter les scores s'ils existent
            q1 = r[3]
            q2 = r[4]
            q3 = r[5]
            
            if q1 is not None:
                combo["q1_scores"].append(float(q1))
            if q2 is not None:
                combo["q2_scores"].append(float(q2))
            if q3 is not None:
                combo["q3_scores"].append(float(q3))
        
        print(f"Nombre de combinaisons prestataire-bénéficiaire: {len(formateur_combinations)}")
        
        # 3. Récupérer les prestations officielles
        prestation_officielles = {}
        cursor.execute("""
            SELECT p.code, pr.raison_sociale as prestataire_nom, 
                   b.nom_structure as beneficiaire_nom
            FROM formations_prestation p
            LEFT JOIN formations_prestataire pr ON p.prestataire_id = pr.id
            LEFT JOIN formations_beneficiaire b ON p.beneficiaire_id = b.id
            WHERE p.actif = 1
        """)
        for code, prestataire_nom, beneficiaire_nom in cursor.fetchall():
            if code and prestataire_nom and beneficiaire_nom:
                prestation_officielles[code] = {
                    "prestataire_nom": str(prestataire_nom).strip().lower(),
                    "beneficiaire_nom": str(beneficiaire_nom).strip().lower()
                }
        
        print(f"Nombre de prestations officielles: {len(prestation_officielles)}")
        
        # 4. Créer la table masquée des combinaisons valides
        table_masquee = []
        combinaisons_valides = 0
        
        for combo_key, combo_data in formateur_combinations.items():
            prestataire_nom = combo_data["prestataire"]
            beneficiaire_nom = combo_data["beneficiaire"]
            
            # Chercher la prestation officielle correspondante
            code_prestation = None
            for code, prestation_info in prestation_officielles.items():
                if (prestation_info["prestataire_nom"] == prestataire_nom.strip().lower() and 
                    prestation_info["beneficiaire_nom"] == beneficiaire_nom.strip().lower()):
                    code_prestation = code
                    break
            
            if code_prestation:
                combinaisons_valides += 1
                # Calculer les moyennes pour cette combinaison
                q1_avg = round(sum(combo_data["q1_scores"]) / len(combo_data["q1_scores"]), 2) if combo_data["q1_scores"] else 0.0
                q2_avg = round(sum(combo_data["q2_scores"]) / len(combo_data["q2_scores"]), 2) if combo_data["q2_scores"] else 0.0
                q3_avg = round(sum(combo_data["q3_scores"]) / len(combo_data["q3_scores"]), 2) if combo_data["q3_scores"] else 0.0
                
                table_masquee.append({
                    "id_prestation": code_prestation,
                    "prestataire": prestataire_nom,
                    "beneficiaire": beneficiaire_nom,
                    "q1_moyenne": q1_avg,
                    "q2_moyenne": q2_avg,
                    "q3_moyenne": q3_avg,
                    "nb_formulaires": combo_data["form_count"],
                    "reference_codes": list(combo_data["reference_codes"])
                })
        
        print(f"Combinaisons valides trouvées: {combinaisons_valides}")
        
        # 5. Calculer les statistiques finales par prestation
        prestation_stats_final = {}
        
        # Initialiser avec toutes les prestations officielles
        for code in prestation_officielles.keys():
            prestation_stats_final[code] = {
                "label": code,
                "nb": 0,
                "avgs": [0.0, 0.0, 0.0]  # Q1, Q2, Q3
            }
        
        # Ajouter les données de la table masquée
        for ligne in table_masquee:
            code = ligne["id_prestation"]
            if code in prestation_stats_final:
                prestation_stats_final[code]["nb"] = ligne["nb_formulaires"]
                prestation_stats_final[code]["avgs"] = [
                    ligne["q1_moyenne"],
                    ligne["q2_moyenne"], 
                    ligne["q3_moyenne"]
                ]
        
        # Ajouter les prestations qui existent seulement dans les appels formateurs
        all_reference_codes = set(r[0] for r in records if r[0])
        for code in all_reference_codes:
            if code and code not in prestation_stats_final:
                prestation_stats_final[code] = {
                    "label": code,
                    "nb": 0,
                    "avgs": [0.0, 0.0, 0.0]  # Afficher un tiret = 0.0
                }
        
        print(f"\n=== Résultats finaux ===")
        print(f"Total des prestations dans la table: {len(prestation_stats_final)}")
        
        # Afficher les 10 premières prestations avec des données
        prestations_avec_donnees = [s for s in prestation_stats_final.values() if s["nb"] > 0]
        print(f"Prestations avec des données: {len(prestations_avec_donnees)}")
        
        print(f"\nTop 10 prestations par nombre de formulaires:")
        sorted_by_nb = sorted(prestations_avec_donnees, key=lambda x: x["nb"], reverse=True)[:10]
        for i, stat in enumerate(sorted_by_nb, 1):
            print(f"{i:2d}. {stat['label'][:50]:50s} | Nb: {stat['nb']:3d} | Q1: {stat['avgs'][0]:5.2f} | Q2: {stat['avgs'][1]:5.2f} | Q3: {stat['avgs'][2]:5.2f}")
        
        conn.close()
        print(f"\n=== Test terminé avec succès ===")
        
    except Exception as e:
        print(f"ERREUR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

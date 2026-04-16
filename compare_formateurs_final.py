#!/usr/bin/env python3
"""
Script pour comparer les formateurs depuis le fichier texte (site) et le fichier Excel
en utilisant le matching par nom et en incluant les prestations ID
"""

import pandas as pd
import re
from difflib import SequenceMatcher

def read_site_formateurs():
    """
    Lit les formateurs depuis le fichier texte (données du site)
    """
    txt_file = r"D:\Documents\NAUMUR\Liste formateur.txt"
    
    try:
        # Lire le fichier avec pandas en spécifiant le séparateur tabulation
        df = pd.read_csv(txt_file, sep='\t')
        print(f"Fichier texte lu: {df.shape}")
        print(f"Colonnes: {list(df.columns)}")
        
        formateurs = []
        
        # Nettoyer les noms de colonnes
        df.columns = df.columns.str.strip()
        
        # Ignorer les lignes d'en-tête (commençant par "Nom")
        for index, row in df.iterrows():
            # Vérifier si c'est une ligne d'en-tête à ignorer
            first_col_value = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
            if first_col_value == 'Nom':
                print(f"Ligne d'en-tête ignorée: {index + 2}")
                continue
            
            def clean_value(value):
                """Nettoie une valeur: enlève les espaces et ne garde rien si c'est juste '-'"""
                if pd.isna(value):
                    return ''
                cleaned = str(value).strip()
                return '' if cleaned == '-' else cleaned
            
            formateur = {
                'nom_site': clean_value(row['Nom']),
                'classe_site': clean_value(row['Classe']),
                'prestation_id_site': clean_value(row['Prestation ID']),
                'prestataire_site': clean_value(row['Prestataire']),
                'beneficiaire_site': clean_value(row['Bénéficiaire']),
                'formation_site': clean_value(row['Formation']),
                'cohorte_site': clean_value(row['Cohorte']),
                'telephone_site': clean_value(row['Téléphone']),
                'statut_site': clean_value(row['Statut']),
                'formulaire_site': clean_value(row['Formulaire']),
                'audio_site': clean_value(row['Audio']),
            }
            
            # Nettoyer le numéro de téléphone
            if formateur['telephone_site']:
                formateur['telephone_site'] = re.sub(r'[^\d+]', '', formateur['telephone_site'])
            
            formateurs.append(formateur)
        
        print(f"Formateurs extraits du fichier texte: {len(formateurs)}")
        return formateurs
        
    except Exception as e:
        print(f"Erreur lecture fichier texte: {e}")
        import traceback
        traceback.print_exc()
        return []

def read_excel_formateurs():
    """
    Lit les formateurs depuis le fichier Excel avec optimisation par unicité des téléphones
    Utilise la feuille "Données" et les colonnes AM, AP, AQ
    """
    excel_file = r"D:\Documents\NAUMUR\fichier_concatene (1) 1 (1)(Donnees).xlsx"
    
    try:
        # Lire la feuille par défaut (seule feuille)
        df = pd.read_excel(excel_file, engine='openpyxl')
        print(f"Fichier Excel lu: {df.shape}")
        print(f"Feuille: par défaut")
        
        # Colonnes spécifiques avec les bons indices
        # Les indices Python commencent à 0, fichier a 47 colonnes (0-46)
        prestation_id_col = df.columns[38]  # Index 38: Prestation ID
        nom_formateur1_col = df.columns[41]  # Index 41: Nom du formateur 1
        telephone_formateur1_col = df.columns[42]  # Index 42: Telephone formateur1
        nom_formateur2_col = df.columns[43]  # Index 43: Nom de la formation 2
        telephone_formateur2_col = df.columns[44]  # Index 44: Telephone du formateur 2
        nom_formateur3_col = df.columns[45]  # Index 45: Nom du formateur 3
        telephone_formateur3_col = df.columns[46]  # Index 46: Telephone du formateur 3
        
        print(f"Colonnes utilisées:")
        print(f"  Index 38: {prestation_id_col}")
        print(f"  Index 41: {nom_formateur1_col}")
        print(f"  Index 42: {telephone_formateur1_col}")
        print(f"  Index 43: {nom_formateur2_col}")
        print(f"  Index 44: {telephone_formateur2_col}")
        print(f"  Index 45: {nom_formateur3_col}")
        print(f"  Index 46: {telephone_formateur3_col}")
        
        # Dictionnaire pour stocker les formateurs uniques par téléphone
        unique_formateurs = {}
        
        for index, row in df.iterrows():
            # Extraire les valeurs des colonnes spécifiques
            prestation_id = str(row[prestation_id_col]).strip() if pd.notna(row[prestation_id_col]) else ''
            
            # Traiter les 3 formateurs possibles
            formateurs_data = [
                {
                    'nom': str(row[nom_formateur1_col]).strip() if pd.notna(row[nom_formateur1_col]) else '',
                    'telephone': str(row[telephone_formateur1_col]).strip() if pd.notna(row[telephone_formateur1_col]) else ''
                },
                {
                    'nom': str(row[nom_formateur2_col]).strip() if pd.notna(row[nom_formateur2_col]) else '',
                    'telephone': str(row[telephone_formateur2_col]).strip() if pd.notna(row[telephone_formateur2_col]) else ''
                },
                {
                    'nom': str(row[nom_formateur3_col]).strip() if pd.notna(row[nom_formateur3_col]) else '',
                    'telephone': str(row[telephone_formateur3_col]).strip() if pd.notna(row[telephone_formateur3_col]) else ''
                }
            ]
            
            # Traiter chaque formateur
            for formateur_data in formateurs_data:
                nom_formateur = formateur_data['nom']
                telephone_formateur = formateur_data['telephone']
                
                # Nettoyer le numéro de téléphone
                if telephone_formateur:
                    telephone_formateur = re.sub(r'[^\d+]', '', telephone_formateur)
                
                # Créer l'objet formateur seulement si on a un téléphone
                if telephone_formateur:
                    # Vérifier si c'est un numéro de 18 chiffres (probablement 2 numéros collés)
                    if len(telephone_formateur) == 18 and telephone_formateur.isdigit():
                        # Séparer en 2 numéros de 9 chiffres
                        phone1 = telephone_formateur[:9]
                        phone2 = telephone_formateur[9:]
                        
                        # Créer une entrée pour le premier numéro
                        formateur1 = {
                            'prestation_id_excel': prestation_id,
                            'nom_excel': nom_formateur,
                            'telephone_excel': phone1,
                            'ligne_excel': index + 2,
                            'split_from': 'original_18_digit'
                        }
                        
                        # Créer une entrée pour le deuxième numéro
                        formateur2 = {
                            'prestation_id_excel': prestation_id,
                            'nom_excel': nom_formateur,
                            'telephone_excel': phone2,
                            'ligne_excel': index + 2,
                            'split_from': 'original_18_digit'
                        }
                        
                        # Ajouter les deux numéros
                        for phone, formateur in [(phone1, formateur1), (phone2, formateur2)]:
                            if phone not in unique_formateurs:
                                unique_formateurs[phone] = formateur
                            else:
                                # Si le téléphone existe déjà, mettre à jour avec le nom/prestation si manquant
                                if not unique_formateurs[phone]['nom_excel'] and nom_formateur:
                                    unique_formateurs[phone]['nom_excel'] = nom_formateur
                                if not unique_formateurs[phone]['prestation_id_excel'] and prestation_id:
                                    unique_formateurs[phone]['prestation_id_excel'] = prestation_id
                    else:
                        # Numéro normal (non 18 chiffres)
                        formateur = {
                            'prestation_id_excel': prestation_id,
                            'nom_excel': nom_formateur,
                            'telephone_excel': telephone_formateur,
                            'ligne_excel': index + 2,
                            'split_from': 'normal'
                        }
                        
                        phone = telephone_formateur
                        # Si le téléphone n'existe pas encore, l'ajouter
                        if phone not in unique_formateurs:
                            unique_formateurs[phone] = formateur
                        else:
                            # Si le téléphone existe déjà, mettre à jour avec le nom/prestation si manquant
                            if not unique_formateurs[phone]['nom_excel'] and nom_formateur:
                                unique_formateurs[phone]['nom_excel'] = nom_formateur
                            if not unique_formateurs[phone]['prestation_id_excel'] and prestation_id:
                                unique_formateurs[phone]['prestation_id_excel'] = prestation_id
        
        # Convertir en liste
        formateurs = list(unique_formateurs.values())
        
        # Statistiques sur les numéros séparés
        split_count = sum(1 for f in formateurs if f.get('split_from') == 'original_18_digit')
        normal_count = sum(1 for f in formateurs if f.get('split_from') == 'normal')
        
        print(f"Formateurs uniques extraits du Excel: {len(formateurs)}")
        print(f"Total lignes traitées: {df.shape[0]}")
        print(f"Téléphones uniques trouvés: {len(unique_formateurs)}")
        print(f"  - Numéros normaux: {normal_count}")
        print(f"  - Numéros séparés (depuis 18 chiffres): {split_count}")
        
        return formateurs
        
    except Exception as e:
        print(f"Erreur lecture Excel: {e}")
        import traceback
        traceback.print_exc()
        return []

def normalize_name(name):
    """
    Normalise un nom pour la comparaison
    """
    if not name:
        return ""
    
    # Mettre en majuscules et enlever les accents
    name = name.upper()
    
    # Enlever les caractères spéciaux et espaces multiples
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name

def name_similarity(name1, name2):
    """
    Calcule la similarité entre deux noms
    """
    norm1 = normalize_name(name1)
    norm2 = normalize_name(name2)
    
    if not norm1 or not norm2:
        return 0.0
    
    return SequenceMatcher(None, norm1, norm2).ratio()

def find_best_match(site_formateur, excel_formateurs):
    """
    Trouve le meilleur match dans Excel pour un formateur du site
    """
    best_match = None
    best_score = 0.0
    
    for excel_formateur in excel_formateurs:
        # Comparaison par nom
        score = 0.0
        
        # Si les deux ont des noms, comparer par similarité
        if site_formateur['nom_site'] and excel_formateur['nom_excel']:
            name_score = name_similarity(site_formateur['nom_site'], excel_formateur['nom_excel'])
            if name_score > 0.7:  # Seuil de similarité
                score = name_score
        
        # Si les deux ont des téléphones, comparer par téléphone exact
        elif site_formateur['telephone_site'] and excel_formateur['telephone_excel']:
            if site_formateur['telephone_site'] == excel_formateur['telephone_excel']:
                score = 1.0
        
        # Si le score est meilleur, garder ce match
        if score > best_score:
            best_score = score
            best_match = excel_formateur
    
    return best_match, best_score

def create_comparison_table(site_formateurs, excel_formateurs):
    """
    Crée le tableau de comparaison final
    """
    print("Création du tableau de comparaison...")
    
    comparison_data = []
    used_excel_indices = set()
    
    # Traiter chaque formateur du site
    for site_formateur in site_formateurs:
        best_match, score = find_best_match(site_formateur, excel_formateurs)
        
        comparison_row = {
            'Prestation ID Excel': best_match.get('prestation_id_excel', '') if best_match else '',
            'Prestation ID Site': site_formateur['prestation_id_site'],
            'Numéro site': site_formateur['telephone_site'],
            'Numéro Excel': best_match['telephone_excel'] if best_match else '',
            'Nom site': site_formateur['nom_site'],
            'Nom Excel': best_match['nom_excel'] if best_match else '',
            'Score matching': f"{score:.2f}" if score > 0 else '',
            'Statut': ''
        }
        
        # Déterminer le statut
        if best_match and score > 0.7:
            comparison_row['Statut'] = 'Match trouvé'
            used_excel_indices.add(id(best_match))
        elif best_match:
            comparison_row['Statut'] = 'Match partiel'
        else:
            comparison_row['Statut'] = 'Non trouvé dans Excel'
        
        comparison_data.append(comparison_row)
    
    # Ajouter les formateurs Excel qui n'ont pas été matchés
    for excel_formateur in excel_formateurs:
        if id(excel_formateur) not in used_excel_indices:
            comparison_row = {
                'Prestation ID Excel': excel_formateur.get('prestation_id_excel', ''),
                'Prestation ID Site': '',
                'Numéro site': '',
                'Numéro Excel': excel_formateur['telephone_excel'],
                'Nom site': '',
                'Nom Excel': excel_formateur['nom_excel'],
                'Score matching': '',
                'Statut': 'Seulement dans Excel'
            }
            comparison_data.append(comparison_row)
    
    return comparison_data

def main():
    """
    Fonction principale
    """
    print("Comparaison finale des formateurs...")
    print("=" * 60)
    
    # 1. Lire les données du site (fichier texte)
    print("\n1. Lecture des données du site...")
    site_formateurs = read_site_formateurs()
    
    # 2. Lire les données Excel
    print("\n2. Lecture des données Excel...")
    excel_formateurs = read_excel_formateurs()
    
    # 3. Créer la comparaison
    print("\n3. Création du tableau de comparaison...")
    comparison_data = create_comparison_table(site_formateurs, excel_formateurs)
    
    # 4. Sauvegarder les résultats
    print("\n4. Sauvegarde des résultats...")
    
    if comparison_data:
        df = pd.DataFrame(comparison_data)
        
        # Statistiques
        total_site = len(site_formateurs)
        total_excel = len(excel_formateurs)
        match_trouve = len([r for r in comparison_data if 'Match trouvé' in r['Statut']])
        match_partiel = len([r for r in comparison_data if 'Match partiel' in r['Statut']])
        non_trouve = len([r for r in comparison_data if 'Non trouvé dans Excel' in r['Statut']])
        seulement_excel = len([r for r in comparison_data if 'Seulement dans Excel' in r['Statut']])
        
        print(f"\nStatistiques:")
        print(f"  - Total site: {total_site}")
        print(f"  - Total Excel: {total_excel}")
        print(f"  - Match trouvé: {match_trouve}")
        print(f"  - Match partiel: {match_partiel}")
        print(f"  - Non trouvé dans Excel: {non_trouve}")
        print(f"  - Seulement dans Excel: {seulement_excel}")
        
        # Sauvegarder en Excel
        output_file = 'comparaison_formateurs_v2.xlsx'
        df.to_excel(output_file, index=False)
        print(f"\nFichier sauvegardé: {output_file}")
        
        # Afficher les premiers résultats
        print(f"\nAperçu des résultats:")
        for i, row in enumerate(comparison_data[:10]):
            print(f"  {row['Prestation ID Site']} | {row['Prestation ID Excel']} | {row['Nom site']} | {row['Nom Excel']} | {row['Statut']}")
        
    else:
        print("Aucune donnée à sauvegarder")

if __name__ == "__main__":
    main()

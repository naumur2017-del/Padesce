#!/usr/bin/env python3
"""
Script pour comparer les numéros de formateurs depuis la base de données distante
et le fichier Excel concaténé.
"""

import os
import sys
import pandas as pd
from pathlib import Path

# Configuration de l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'App_PADESCE'))

import django
django.setup()

from formations.models import Formation, Formateur

def get_remote_formateurs():
    """
    Récupère les numéros de formateurs depuis la base de données distante
    """
    try:
        # Utiliser la connexion par défaut qui devrait pointer vers la base distante
        formateurs = Formateur.objects.all().values(
            'id', 'nom', 'telephone', 'formation__code', 'formation__prestataire'
        )
        
        print(f"✅ Récupération de {formateurs.count()} formateurs depuis la base distante")
        return list(formateurs)
        
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des formateurs: {e}")
        return []

def read_excel_file():
    """
    Lit le fichier Excel concaténé pour extraire les numéros de formateurs
    """
    excel_file = "fichier_concatene (1) 1 (1).xlsx"
    
    if not os.path.exists(excel_file):
        print(f"❌ Fichier Excel non trouvé: {excel_file}")
        return []
    
    try:
        # Essayer de lire avec différentes méthodes
        df = None
        
        # Méthode 1: lecture directe
        try:
            df = pd.read_excel(excel_file, engine='openpyxl')
        except:
            pass
        
        # Méthode 2: lecture avec xlrd
        if df is None:
            try:
                df = pd.read_excel(excel_file, engine='xlrd')
            except:
                pass
        
        # Méthode 3: lecture en spécifiant des colonnes
        if df is None:
            try:
                df = pd.read_excel(excel_file, header=None)
            except:
                pass
        
        if df is None:
            print("❌ Impossible de lire le fichier Excel avec les moteurs disponibles")
            return []
        
        print(f"✅ Fichier Excel lu avec succès. Colonnes: {list(df.columns)}")
        print(f"📊 Dimensions: {df.shape}")
        
        # Chercher les colonnes pertinentes
        formateurs_excel = []
        
        # Colonnes possibles pour les numéros de téléphone
        phone_columns = []
        for col in df.columns:
            col_str = str(col).lower()
            if any(keyword in col_str for keyword in ['téléphone', 'telephone', 'tel', 'phone', 'numéro', 'numero']):
                phone_columns.append(col)
        
        print(f"📋 Colonnes de téléphone trouvées: {phone_columns}")
        
        # Extraire les données
        for index, row in df.iterrows():
            if index >= 100:  # Limiter pour éviter les problèmes de mémoire
                break
                
            formateur_data = {
                'ligne_excel': index + 2,  # +2 pour correspondre aux numéros de ligne Excel
                'nom': '',
                'telephone': '',
                'prestataire': '',
                'formation': ''
            }
            
            # Extraire le nom
            for col in df.columns:
                col_str = str(col).lower()
                if any(keyword in col_str for keyword in ['nom', 'name']):
                    formateur_data['nom'] = str(row[col]) if pd.notna(row[col]) else ''
                    break
            
            # Extraire le téléphone
            for col in phone_columns:
                if pd.notna(row[col]):
                    formateur_data['telephone'] = str(row[col]).strip()
                    break
            
            # Extraire prestataire
            for col in df.columns:
                col_str = str(col).lower()
                if any(keyword in col_str for keyword in ['prestataire', 'prestation']):
                    formateur_data['prestataire'] = str(row[col]) if pd.notna(row[col]) else ''
                    break
            
            # Extraire formation
            for col in df.columns:
                col_str = str(col).lower()
                if any(keyword in col_str for keyword in ['formation', 'classe', 'cohorte']):
                    formateur_data['formation'] = str(row[col]) if pd.notna(row[col]) else ''
                    break
            
            # Ajouter seulement si on a un téléphone
            if formateur_data['telephone']:
                formateurs_excel.append(formateur_data)
        
        print(f"✅ Extraction de {len(formateurs_excel)} formateurs depuis Excel")
        return formateurs_excel
        
    except Exception as e:
        print(f"❌ Erreur lors de la lecture du fichier Excel: {e}")
        import traceback
        traceback.print_exc()
        return []

def create_comparison_table(remote_formateurs, excel_formateurs):
    """
    Crée un tableau de comparaison entre les formateurs distants et Excel
    """
    print("🔄 Création du tableau de comparaison...")
    
    # Créer des dictionnaires pour une recherche rapide
    remote_by_phone = {f['telephone'].strip(): f for f in remote_formateurs}
    excel_by_phone = {f['telephone'].strip(): f for f in excel_formateurs}
    
    comparison_data = []
    
    # Analyser tous les numéros uniques
    all_phones = set(remote_by_phone.keys()) | set(excel_by_phone.keys())
    
    for phone in all_phones:
        remote = remote_by_phone.get(phone)
        excel = excel_by_phone.get(phone)
        
        comparison_row = {
            'Téléphone': phone,
            'Nom_Distant': remote['nom'] if remote else '',
            'Prestataire_Distant': remote['formation__prestataire'] if remote else '',
            'Formation_Distant': remote['formation__code'] if remote else '',
            'ID_Distant': remote['id'] if remote else '',
            'Nom_Excel': excel['nom'] if excel else '',
            'Prestataire_Excel': excel['prestataire'] if excel else '',
            'Formation_Excel': excel['formation'] if excel else '',
            'Ligne_Excel': excel['ligne_excel'] if excel else '',
            'Statut': ''
        }
        
        # Déterminer le statut
        if remote and excel:
            comparison_row['Statut'] = '✅ Présent dans les deux'
        elif remote and not excel:
            comparison_row['Statut'] = '🔵 Seulement base distante'
        elif not remote and excel:
            comparison_row['Statut'] = '🟡 Seulement fichier Excel'
        else:
            comparison_row['Statut'] = '❌ Erreur'
        
        comparison_data.append(comparison_row)
    
    # Trier par téléphone
    comparison_data.sort(key=lambda x: x['Téléphone'])
    
    return comparison_data

def save_to_excel(comparison_data, filename="comparaison_formateurs.xlsx"):
    """
    Sauvegarde le tableau de comparaison en format Excel
    """
    try:
        df = pd.DataFrame(comparison_data)
        
        # Ajouter des statistiques
        stats_data = [
            ['Statistiques', '', '', '', '', '', '', '', '', '', ''],
            ['Total formateurs base distante', len([r for r in comparison_data if r['ID_Distant']]), '', '', '', '', '', '', '', '', ''],
            ['Total formateurs fichier Excel', len([r for r in comparison_data if r['Ligne_Excel']]), '', '', '', '', '', '', '', '', ''],
            ['Communs aux deux', len([r for r in comparison_data if 'Présent dans les deux' in r['Statut']]), '', '', '', '', '', '', '', '', ''],
            ['Seulement base distante', len([r for r in comparison_data if 'Seulement base distante' in r['Statut']]), '', '', '', '', '', '', '', '', ''],
            ['Seulement fichier Excel', len([r for r in comparison_data if 'Seulement fichier Excel' in r['Statut']]), '', '', '', '', '', '', '', '', ''],
            ['', '', '', '', '', '', '', '', '', '', ''],
        ]
        
        # Combiner les données
        final_data = stats_data + [list(df.columns)] + df.values.tolist()
        
        # Créer le DataFrame final
        final_df = pd.DataFrame(final_data[1:], columns=final_data[0])
        
        # Sauvegarder
        final_df.to_excel(filename, index=False, engine='openpyxl')
        
        print(f"✅ Fichier de comparaison sauvegardé: {filename}")
        print(f"📊 Statistiques:")
        print(f"   - Total base distante: {len([r for r in comparison_data if r['ID_Distant']])}")
        print(f"   - Total fichier Excel: {len([r for r in comparison_data if r['Ligne_Excel']])}")
        print(f"   - Communs: {len([r for r in comparison_data if 'Présent dans les deux' in r['Statut']])}")
        print(f"   - Seulement base distante: {len([r for r in comparison_data if 'Seulement base distante' in r['Statut']])}")
        print(f"   - Seulement fichier Excel: {len([r for r in comparison_data if 'Seulement fichier Excel' in r['Statut']])}")
        
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde Excel: {e}")
        import traceback
        traceback.print_exc()

def main():
    """
    Fonction principale
    """
    print("🚀 Début de la comparaison des formateurs...")
    print("=" * 60)
    
    # 1. Récupérer les formateurs depuis la base distante
    print("\n📡 Étape 1: Récupération depuis la base distante...")
    remote_formateurs = get_remote_formateurs()
    
    # 2. Lire le fichier Excel
    print("\n📊 Étape 2: Lecture du fichier Excel...")
    excel_formateurs = read_excel_file()
    
    # 3. Créer le tableau de comparaison
    print("\n🔄 Étape 3: Création du tableau de comparaison...")
    comparison_data = create_comparison_table(remote_formateurs, excel_formateurs)
    
    # 4. Sauvegarder en Excel
    print("\n💾 Étape 4: Sauvegarde des résultats...")
    save_to_excel(comparison_data)
    
    print("\n✅ Comparaison terminée!")
    print("=" * 60)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Script pour vérifier les colonnes exactes du fichier Excel
"""

import pandas as pd

def verify_excel_columns():
    """
    Vérifie les colonnes AM, AP, AQ du fichier Excel
    """
    excel_file = r"D:\Documents\NAUMUR\fichier_concatene (1) 1 (1)(Donnees).xlsx"
    
    try:
        df = pd.read_excel(excel_file, engine='openpyxl')
        print(f"Fichier Excel lu: {df.shape}")
        print(f"Nombre total de colonnes: {len(df.columns)}")
        
        # Afficher les colonnes autour de AM, AP, AQ
        print(f"\nColonnes autour de AM, AP, AQ (indices 39, 41, 42):")
        
        for i in range(max(0, 35), min(len(df.columns), 50)):
            col_name = df.columns[i]
            print(f"  {chr(65+i)}: {col_name}")
        
        # Vérifier spécifiquement AM, AP, AQ
        if len(df.columns) > 42:
            col_am = df.columns[39]  # AM
            col_ap = df.columns[41]  # AP  
            col_aq = df.columns[42]  # AQ
            
            print(f"\nVérification des colonnes:")
            print(f"  AM (index 39): '{col_am}'")
            print(f"  AP (index 41): '{col_ap}'")
            print(f"  AQ (index 42): '{col_aq}'")
            
            # Afficher quelques exemples de données
            print(f"\nExemples de données (premières 10 lignes):")
            for i in range(min(10, len(df))):
                print(f"  Ligne {i+1}:")
                print(f"    AM: {df.iloc[i][col_am]}")
                print(f"    AP: {df.iloc[i][col_ap]}")
                print(f"    AQ: {df.iloc[i][col_aq]}")
                print()
        
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_excel_columns()

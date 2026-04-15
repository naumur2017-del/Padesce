#!/usr/bin/env python3
"""
Script pour lister toutes les colonnes de l'Excel avec leurs indices
"""

import pandas as pd

def list_all_columns():
    """
    Liste toutes les colonnes du fichier Excel avec leurs indices
    """
    excel_file = r"D:\Documents\NAUMUR\fichier_concatene (1) 1 (1)(Donnees).xlsx"
    
    try:
        df = pd.read_excel(excel_file, engine='openpyxl')
        print(f"Fichier Excel lu: {df.shape}")
        print(f"Nombre total de colonnes: {len(df.columns)}")
        
        print(f"\nToutes les colonnes avec leurs indices:")
        for i, col in enumerate(df.columns):
            print(f"  {i:2d}: {col}")
        
        # Chercher spécifiquement les colonnes de formateurs
        print(f"\nColonnes contenant 'formateur' ou 'telephone':")
        for i, col in enumerate(df.columns):
            col_lower = str(col).lower()
            if 'formateur' in col_lower or 'telephone' in col_lower:
                print(f"  {i:2d}: {col}")
        
        # Chercher la colonne Prestation ID
        print(f"\nColonnes contenant 'prestation':")
        for i, col in enumerate(df.columns):
            col_lower = str(col).lower()
            if 'prestation' in col_lower:
                print(f"  {i:2d}: {col}")
        
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    list_all_columns()

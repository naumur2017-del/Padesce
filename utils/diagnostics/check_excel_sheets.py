#!/usr/bin/env python3
"""
Script pour vérifier les feuilles du fichier Excel
"""

import pandas as pd


def check_excel_sheets():
    """
    Vérifie les feuilles du fichier Excel
    """
    excel_file = "fichier_concatene (1) 1 (1).xlsx"

    try:
        # Lister toutes les feuilles
        excel_file = pd.ExcelFile(excel_file, engine="openpyxl")
        sheet_names = excel_file.sheet_names

        print(f"Feuilles trouvées dans le fichier Excel:")
        for i, sheet in enumerate(sheet_names):
            print(f"  {i+1}. '{sheet}'")

        # Essayer de lire la première feuille pour voir les colonnes
        if sheet_names:
            first_sheet = sheet_names[0]
            print(f"\nAnalyse de la première feuille: '{first_sheet}'")

            df = pd.read_excel(excel_file, sheet_name=first_sheet, engine="openpyxl")
            print(f"Dimensions: {df.shape}")

            print(f"\nColonnes AM, AP, AQ (indices 39, 41, 42):")
            if len(df.columns) > 42:
                print(f"  AM (39): '{df.columns[39]}'")
                print(f"  AP (41): '{df.columns[41]}'")
                print(f"  AQ (42): '{df.columns[42]}'")

                # Afficher quelques exemples de ces colonnes
                print(f"\nExemples de données dans ces colonnes:")
                for i in range(min(5, len(df))):
                    print(f"  Ligne {i+1}:")
                    print(f"    AM: {df.iloc[i][df.columns[39]]}")
                    print(f"    AP: {df.iloc[i][df.columns[41]]}")
                    print(f"    AQ: {df.iloc[i][df.columns[42]]}")
            else:
                print(f"Le fichier n'a que {len(df.columns)} colonnes")

    except Exception as e:
        print(f"Erreur: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    check_excel_sheets()

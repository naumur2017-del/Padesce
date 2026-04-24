#!/usr/bin/env python3
"""
Script pour vérifier les colonnes exactes du fichier Excel
"""

import pandas as pd


def check_excel_columns():
    """
    Vérifie les colonnes du fichier Excel
    """
    excel_file = "fichier_concatene (1) 1 (1).xlsx"

    try:
        df = pd.read_excel(excel_file, engine="openpyxl")
        print(f"Fichier Excel lu: {df.shape}")
        print(f"\nColonnes trouvées ({len(df.columns)}):")

        for i, col in enumerate(df.columns):
            print(f"  {i+1:2d}. '{col}'")

        # Chercher les colonnes contenant 'formateur' et 'téléphone'
        print(f"\nColonnes avec 'formateur':")
        for i, col in enumerate(df.columns):
            if "formateur" in str(col).lower():
                print(f"  {i+1:2d}. '{col}'")

        print(f"\nColonnes avec 'téléphone':")
        for i, col in enumerate(df.columns):
            if (
                "téléphone" in str(col).lower()
                or "telephone" in str(col).lower()
                or "tel" in str(col).lower()
            ):
                print(f"  {i+1:2d}. '{col}'")

        # Afficher quelques exemples de données
        print(f"\nExemples de données (premières lignes):")
        for i in range(min(5, len(df))):
            print(f"\nLigne {i+1}:")
            for col in df.columns:
                if (
                    "formateur" in str(col).lower()
                    or "téléphone" in str(col).lower()
                    or "tel" in str(col).lower()
                ):
                    value = df.iloc[i][col]
                    print(f"  {col}: {value}")

    except Exception as e:
        print(f"Erreur: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    check_excel_columns()

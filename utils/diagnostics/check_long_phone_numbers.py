#!/usr/bin/env python3
"""
Script pour vérifier les numéros de téléphone longs dans le fichier Excel
"""

import re

import pandas as pd


def check_long_phone_numbers():
    """
    Vérifie les numéros de téléphone longs dans le fichier Excel
    """
    excel_file = r"D:\Documents\NAUMUR\fichier_concatene (1) 1 (1)(Donnees).xlsx"

    try:
        df = pd.read_excel(excel_file, engine="openpyxl")
        print(f"Fichier Excel lu: {df.shape}")

        # Colonnes de téléphones
        phone_columns = [
            df.columns[42],  # Telephone formateur1
            df.columns[44],  # Telephone du formateur 2
            df.columns[46],  # Telephone du formateur 3
        ]

        print(f"\nColonnes de téléphones analysées:")
        for i, col in enumerate(phone_columns):
            print(f"  {i+1}. {col}")

        long_numbers = []
        all_numbers = []

        for index, row in df.iterrows():
            for col_name in phone_columns:
                if pd.notna(row[col_name]):
                    phone = str(row[col_name]).strip()
                    phone = re.sub(r"[^\d+]", "", phone)

                    if phone:
                        all_numbers.append(phone)
                        if len(phone) >= 15:  # Numéros très longs
                            long_numbers.append(
                                {
                                    "ligne": index + 2,
                                    "colonne": col_name,
                                    "original": phone,
                                    "longueur": len(phone),
                                }
                            )

        print(f"\nStatistiques:")
        print(f"  - Total numéros trouvés: {len(all_numbers)}")
        print(f"  - Numéros très longs (>=15 chiffres): {len(long_numbers)}")

        if long_numbers:
            print(f"\nNuméros très longs trouvés:")
            for num in long_numbers[:20]:  # Limiter à 20 affichages
                print(
                    f"  Ligne {num['ligne']}, {num['colonne']}: {num['original']} ({num['longueur']} chiffres)"
                )

                # Si c'est 18 chiffres, montrer la séparation
                if num["longueur"] == 18:
                    phone1 = num["original"][:9]
                    phone2 = num["original"][9:]
                    print(f"    -> Séparation: {phone1} | {phone2}")

        # Analyser la distribution des longueurs
        length_dist = {}
        for phone in all_numbers:
            length = len(phone)
            length_dist[length] = length_dist.get(length, 0) + 1

        print(f"\nDistribution des longueurs de numéros:")
        for length in sorted(length_dist.keys()):
            print(f"  {length} chiffres: {length_dist[length]} numéros")

    except Exception as e:
        print(f"Erreur: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    check_long_phone_numbers()

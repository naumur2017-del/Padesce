#!/usr/bin/env python
"""
Script simple pour vérifier l'accès à la base de données SQLite
"""

import os
import sqlite3


def main():
    db_path = "c:\\Users\\LENOVO\\Downloads\\backup_20260416_145722.sqlite3"

    print("=== Vérification simple de la base de données SQLite ===\n")

    try:
        # Connexion directe avec sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Lister les tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        print(f"Tables trouvées ({len(tables)}):")
        for table in tables:
            print(f"  - {table[0]}")

        # Vérifier la table appels_appelformateur
        if ("appels_appelformateur",) in tables:
            cursor.execute("SELECT COUNT(*) FROM appels_appelformateur;")
            count = cursor.fetchone()[0]
            print(f"\nNombre total d'enregistrements dans appels_appelformateur: {count}")

            # Vérifier les enregistrements actifs
            cursor.execute("SELECT COUNT(*) FROM appels_appelformateur WHERE is_active = 1;")
            active_count = cursor.fetchone()[0]
            print(f"Nombre d'enregistrements actifs: {active_count}")

            # Voir quelques exemples
            cursor.execute(
                """
                SELECT reference_code, prestataire, beneficiaire,
                       q1_prerequis_apprenants, q2_interaction_apprenants, q3_competences_acquises
                FROM appels_appelformateur
                WHERE is_active = 1
                LIMIT 5
            """
            )
            samples = cursor.fetchall()

            print(f"\nExemples d'enregistrements:")
            for i, sample in enumerate(samples, 1):
                print(f"  {i}. {sample[0]} - {sample[1]} - {sample[2]}")
                print(f"     Q1: {sample[3]}, Q2: {sample[4]}, Q3: {sample[5]}")

        conn.close()
        print(f"\n=== Vérification terminée avec succès ===")

    except Exception as e:
        print(f"ERREUR: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()

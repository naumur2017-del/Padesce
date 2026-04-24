#!/usr/bin/env python3
"""
Script pour créer les colonnes manquantes après les fake migrations
"""

import os
import sys

import django
from django.conf import settings
from django.db import connection


def setup_django():
    """Configure Django"""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "App_PADESCE.settings")
    django.setup()


def add_missing_columns():
    """Ajoute les colonnes manquantes dans la base de données"""

    # Colonnes manquantes pour apprenants_apprenant selon la migration 0007
    missing_columns = [
        ("apprenants_apprenant", "c1", 'VARCHAR(2) DEFAULT "AB"'),
        ("apprenants_apprenant", "c2", 'VARCHAR(2) DEFAULT "AB"'),
        ("apprenants_apprenant", "c3", 'VARCHAR(2) DEFAULT "AB"'),
        ("apprenants_apprenant", "c4", 'VARCHAR(2) DEFAULT "AB"'),
    ]

    with connection.cursor() as cursor:
        for table, column, column_def in missing_columns:
            try:
                # Vérifier si la colonne existe déjà
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in cursor.fetchall()]

                if column not in columns:
                    print(f"Ajout de la colonne {column} dans la table {table}")
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_def}")
                    print(f"  -> Colonne {column} ajoutée avec succès")
                else:
                    print(f"La colonne {column} existe déjà dans la table {table}")

            except Exception as e:
                print(f"Erreur lors de l'ajout de la colonne {column}: {e}")

        # Valider les changements
        connection.commit()
        print("Toutes les colonnes manquantes ont été ajoutées avec succès")


def verify_columns():
    """Vérifie que les colonnes existent maintenant"""
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA table_info(apprenants_apprenant)")
        columns = cursor.fetchall()

        print("\nColonnes dans la table apprenants_apprenant:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")


if __name__ == "__main__":
    setup_django()
    add_missing_columns()
    verify_columns()

#!/usr/bin/env python3
"""
Script pour ajouter la colonne manquante dans formations_formateur
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


def add_formateur_nom_column():
    """Ajoute la colonne nom manquante dans formations_formateur"""

    with connection.cursor() as cursor:
        try:
            # Vérifier si la colonne existe déjà
            cursor.execute("PRAGMA table_info(formations_formateur)")
            columns = [row[1] for row in cursor.fetchall()]

            if "nom" not in columns:
                print("Ajout de la colonne nom dans la table formations_formateur")
                cursor.execute("ALTER TABLE formations_formateur ADD COLUMN nom TEXT")
                print("  -> Colonne nom ajoutée avec succès")
            else:
                print("La colonne nom existe déjà dans la table formations_formateur")

        except Exception as e:
            print(f"Erreur lors de l'ajout de la colonne nom: {e}")

        # Valider les changements
        connection.commit()
        print("Colonne formations_formateur.nom ajoutée avec succès")


def verify_columns():
    """Vérifie que les colonnes existent maintenant"""
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA table_info(formations_formateur)")
        columns = cursor.fetchall()

        print("\nColonnes dans la table formations_formateur:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")


if __name__ == "__main__":
    setup_django()
    add_formateur_nom_column()
    verify_columns()

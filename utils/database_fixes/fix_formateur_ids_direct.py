#!/usr/bin/env python3
"""
Script pour corriger directement les formateurs avec des ID manquants
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


def fix_formateur_ids_directly():
    """Corrige directement les formateurs avec des ID manquants"""

    with connection.cursor() as cursor:
        # D'abord, vérifier le problème
        cursor.execute("SELECT COUNT(*) FROM formations_formateur WHERE id IS NULL")
        null_count = cursor.fetchone()[0]
        print(f"Formateurs avec ID NULL: {null_count}")

        if null_count > 0:
            # Trouver le prochain ID disponible
            cursor.execute("SELECT MAX(id) FROM formations_formateur WHERE id IS NOT NULL")
            max_id_result = cursor.fetchone()
            max_id = max_id_result[0] if max_id_result[0] else 0

            print(f"ID maximal existant: {max_id}")

            # Assigner des IDs séquentiels aux formateurs sans ID
            cursor.execute(
                """
                UPDATE formations_formateur
                SET id = (
                    SELECT rowid + (SELECT COALESCE(MAX(id), 0) FROM formations_formateur WHERE id IS NOT NULL)
                    FROM (SELECT rowid FROM formations_formateur WHERE id IS NULL ORDER BY rowid)
                    WHERE formations_formateur.rowid = rowid
                )
                WHERE id IS NULL
            """
            )

            connection.commit()
            print("IDs assignés avec succès")

        # Vérifier le résultat
        cursor.execute("SELECT COUNT(*) FROM formations_formateur WHERE id IS NULL")
        remaining_null = cursor.fetchone()[0]
        print(f"Formateurs restants avec ID NULL: {remaining_null}")

        # Afficher quelques exemples pour vérification
        cursor.execute(
            "SELECT id, code, nom_complet FROM formations_formateur WHERE code = 'TEL698065452'"
        )
        test_formateur = cursor.fetchone()
        if test_formateur:
            print(
                f"Formateur test: ID={test_formateur[0]}, Code={test_formateur[1]}, Nom={test_formateur[2]}"
            )


def verify_formateurs():
    """Vérification finale"""
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM formations_formateur")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM formations_formateur WHERE id IS NULL")
        problematic = cursor.fetchone()[0]

        print(f"\nÉtat final des formateurs:")
        print(f"  Total: {total}")
        print(f"  Avec ID NULL: {problematic}")

        if problematic == 0:
            print("  -> TOUS LES FORMATEURS ONT DES IDS VALIDES!")


if __name__ == "__main__":
    setup_django()
    fix_formateur_ids_directly()
    verify_formateurs()

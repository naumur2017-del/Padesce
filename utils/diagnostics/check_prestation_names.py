#!/usr/bin/env python3
"""
Script pour vérifier les vrais noms des prestations
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


def check_prestation_names():
    """Vérifie les vrais noms/titres des prestations"""

    with connection.cursor() as cursor:
        print("=== VÉRIFICATION DES NOMS DE PRESTATIONS ===\n")

        # Vérifier si la table formations_formation a un champ nom/titre
        cursor.execute("PRAGMA table_info(formations_formation)")
        formation_columns = cursor.fetchall()

        print("Colonnes de formations_formation:")
        for col in formation_columns:
            print(f"  {col[1]} ({col[2]})")

        # Vérifier les prestations avec leurs vrais noms
        cursor.execute(
            """
            SELECT p.code, p.id, f.nom as formation_nom, pr.raison_sociale, b.nom_structure
            FROM formations_prestation p
            LEFT JOIN formations_formation f ON p.formation_id = f.id
            LEFT JOIN formations_prestataire pr ON p.prestataire_id = pr.id
            LEFT JOIN formations_beneficiaire b ON p.beneficiaire_id = b.id
            WHERE p.actif = 1
            ORDER BY p.code
            LIMIT 20
        """
        )
        prestations = cursor.fetchall()

        print(f"\nPrestations avec leurs vrais noms:")
        for code, id, formation_nom, prestataire_nom, beneficiaire_nom in prestations:
            print(f"  {code}: {formation_nom} | {prestataire_nom} | {beneficiaire_nom}")

        # Vérifier spécifiquement les prestations qui apparaissent dans les tops
        top_prestations = ["PRESTA066", "PRESTA079", "PRESTA001", "PRESTA018", "PRESTA147"]

        print(f"\nVérification des prestations du top:")
        cursor.execute(
            """
            SELECT p.code, f.nom as formation_nom, pr.raison_sociale, b.nom_structure, b.region
            FROM formations_prestation p
            LEFT JOIN formations_formation f ON p.formation_id = f.id
            LEFT JOIN formations_prestataire pr ON p.prestataire_id = pr.id
            LEFT JOIN formations_beneficiaire b ON p.beneficiaire_id = b.id
            WHERE p.code IN (%s, %s, %s, %s, %s) AND p.actif = 1
        """,
            top_prestations,
        )
        top_details = cursor.fetchall()

        for code, formation_nom, prestataire_nom, beneficiaire_nom, region in top_details:
            print(f"  {code}:")
            print(f"    Formation: {formation_nom}")
            print(f"    Prestataire: {prestataire_nom}")
            print(f"    Bénéficiaire: {beneficiaire_nom}")
            print(f"    Region: {region}")
            print()


if __name__ == "__main__":
    setup_django()
    check_prestation_names()

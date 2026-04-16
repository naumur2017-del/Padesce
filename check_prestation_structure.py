#!/usr/bin/env python3
"""
Script pour vérifier la structure de la table des prestations
"""

import os
import sys
import django
from django.conf import settings
from django.db import connection

def setup_django():
    """Configure Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
    django.setup()

def check_prestation_structure():
    """Vérifie la structure exacte de la table des prestations"""
    
    with connection.cursor() as cursor:
        print("=== STRUCTURE DE LA TABLE PRESTATIONS ===\n")
        
        # Vérifier la structure de la table
        cursor.execute("PRAGMA table_info(formations_prestation)")
        columns = cursor.fetchall()
        
        print("Colonnes de formations_prestation:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # Vérifier les prestations existantes
        cursor.execute("SELECT * FROM formations_prestation WHERE actif = 1 LIMIT 10")
        prestations = cursor.fetchall()
        
        print(f"\nPrestations actives (exemples):")
        for i, row in enumerate(prestations):
            print(f"  {i+1}. {row}")
        
        # Compter les prestations actives
        cursor.execute("SELECT COUNT(*) FROM formations_prestation WHERE actif = 1")
        count = cursor.fetchone()[0]
        print(f"\nTotal prestations actives: {count}")

if __name__ == "__main__":
    setup_django()
    check_prestation_structure()

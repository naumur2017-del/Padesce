#!/usr/bin/env python3
"""
Script pour résoudre les problèmes de migration avec les clés étrangères
"""

import os
import sys
import django
from django.conf import settings
from django.db import connection
from django.core.management import execute_from_command_line

def setup_django():
    """Configure Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
    django.setup()

def disable_foreign_key_checks():
    """Désactive temporairement les vérifications de clés étrangères"""
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA foreign_keys = OFF")
        print("Contraintes de clés étrangères désactivées")

def enable_foreign_key_checks():
    """Réactive les vérifications de clés étrangères"""
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA foreign_keys = ON")
        print("Contraintes de clés étrangères réactivées")

def run_migrations():
    """Exécute les migrations avec les contraintes désactivées"""
    try:
        disable_foreign_key_checks()
        
        # Exécuter les migrations
        execute_from_command_line(['manage.py', 'migrate'])
        print("Migrations appliquées avec succès")
        
    except Exception as e:
        print(f"Erreur pendant les migrations: {e}")
        return False
    finally:
        enable_foreign_key_checks()
    
    return True

if __name__ == "__main__":
    setup_django()
    success = run_migrations()
    
    if success:
        print("Toutes les migrations ont été appliquées avec succès!")
    else:
        print("Échec des migrations. Vérifiez les erreurs ci-dessus.")

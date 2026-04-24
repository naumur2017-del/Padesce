#!/usr/bin/env python3
"""
Script pour corriger les formateurs avec des ID manquants ou invalides
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
    
    # Importer les modèles après configuration de Django
    global Formateur
    from App_PADESCE.formations.models import Formateur

def fix_formateur_ids():
    """Corrige les formateurs avec des ID manquants ou invalides"""
    
    # D'abord, vérifier les formateurs avec des problèmes d'ID
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, code, nom_complet FROM formations_formateur WHERE id IS NULL OR id = '' OR code = 'TEL698065452'")
        problematic_formateurs = cursor.fetchall()
        
        print(f"Formateurs avec problèmes d'ID: {len(problematic_formateurs)}")
        for formateur in problematic_formateurs:
            print(f"  ID: {formateur[0]}, Code: {formateur[1]}, Nom: {formateur[2]}")
    
    # Si on trouve le formateur spécifique mentionné dans l'erreur
    try:
        problematic_formateur = Formateur.objects.filter(code='TEL698065452').first()
        if problematic_formateur and (not problematic_formateur.id or problematic_formateur.id == ''):
            print(f"Correction du formateur: {problematic_formateur}")
            
            # Supprimer ce formateur problématique
            problematic_formateur.delete()
            print("Formateur problématique supprimé")
        else:
            print("Formateur TEL698065452 non trouvé ou déjà correct")
            
    except Exception as e:
        print(f"Erreur lors de la correction: {e}")
    
    # Vérifier s'il y a des formateurs sans ID valide
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM formations_formateur WHERE id IS NULL OR id = ''")
        count = cursor.fetchone()[0]
        
        if count > 0:
            print(f"Il y a encore {count} formateurs sans ID valide")
            
            # Assigner des IDs valides aux formateurs sans ID
            cursor.execute("SELECT MAX(id) FROM formations_formateur WHERE id IS NOT NULL AND id != ''")
            max_id_result = cursor.fetchone()
            max_id = max_id_result[0] if max_id_result[0] else 0
            
            cursor.execute("UPDATE formations_formateur SET id = id + 1 WHERE id IS NULL OR id = ''")
            print("IDs assignés aux formateurs sans ID")
        else:
            print("Tous les formateurs ont des IDs valides")

def verify_formateurs():
    """Vérifie l'état des formateurs après correction"""
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM formations_formateur")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM formations_formateur WHERE id IS NULL OR id = ''")
        problematic = cursor.fetchone()[0]
        
        print(f"\nÉtat des formateurs après correction:")
        print(f"  Total formateurs: {total}")
        print(f"  Formateurs avec ID problématique: {problematic}")

if __name__ == "__main__":
    setup_django()
    fix_formateur_ids()
    verify_formateurs()

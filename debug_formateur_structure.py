#!/usr/bin/env python3
"""
Script pour analyser la structure exacte des tables formateurs
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

def analyze_table_structure():
    """Analyse la structure des tables pertinentes"""
    
    with connection.cursor() as cursor:
        print("=== STRUCTURE DES TABLES ===\n")
        
        # 1. Structure de AppelFormateur
        cursor.execute("PRAGMA table_info(appels_appelformateur)")
        columns = cursor.fetchall()
        
        print("Colonnes de appels_appelformateur:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        print(f"\nTotal colonnes: {len(columns)}")
        
        # 2. Vérifier les données réelles
        cursor.execute("SELECT COUNT(*) FROM appels_appelformateur")
        total_formateurs = cursor.fetchone()[0]
        print(f"\nTotal enregistrements dans appels_appelformateur: {total_formateurs}")
        
        if total_formateurs > 0:
            # Voir un échantillon de données
            cursor.execute("SELECT * FROM appels_appelformateur LIMIT 3")
            sample_data = cursor.fetchall()
            
            print("\nÉchantillon de données (3 premiers enregistrements):")
            for i, row in enumerate(sample_data):
                print(f"  Enregistrement {i+1}: {row}")
        
        # 3. Vérifier les colonnes de score
        score_columns = ['q1_prerequis_apprenants', 'q2_interaction_apprenants', 'q3_competences_acquises']
        print(f"\nVérification des colonnes de score:")
        
        for col in score_columns:
            cursor.execute(f"SELECT COUNT(*) FROM appels_appelformateur WHERE {col} IS NOT NULL")
            count = cursor.fetchone()[0]
            print(f"  {col}: {count} enregistrements avec des valeurs")
        
        # 4. Vérifier les colonnes qui pourraient contenir la référence à la prestation
        cursor.execute("PRAGMA table_info(appels_appelformateur)")
        columns = cursor.fetchall()
        
        possible_prestation_cols = [col[1] for col in columns if 'prestation' in col[1].lower() or 'code' in col[1].lower()]
        print(f"\nColonnes potentiellement liées aux prestations: {possible_prestation_cols}")
        
        for col in possible_prestation_cols:
            cursor.execute(f"SELECT DISTINCT {col} FROM appels_appelformateur WHERE {col} IS NOT NULL LIMIT 10")
            values = cursor.fetchall()
            print(f"  {col}: {[v[0] for v in values]}")

def analyze_prestation_relations():
    """Analyse comment les formateurs sont liés aux prestations"""
    
    with connection.cursor() as cursor:
        print("\n=== ANALYSE DES RELATIONS PRESTATION-FORMATEUR ===\n")
        
        # Vérifier s'il y a une table de liaison
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%prestation%' AND name LIKE '%formateur%'")
        relation_tables = cursor.fetchall()
        
        print(f"Tables de liaison prestation-formateur: {[t[0] for t in relation_tables]}")
        
        # Vérifier la table Appel (appels_appel)
        cursor.execute("PRAGMA table_info(appels_appel)")
        appel_columns = cursor.fetchall()
        
        print(f"\nColonnes de appels_appel:")
        for col in appel_columns:
            print(f"  {col[1]} ({col[2]})")

if __name__ == "__main__":
    setup_django()
    analyze_table_structure()
    analyze_prestation_relations()

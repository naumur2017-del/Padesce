#!/usr/bin/env python3
"""
Script pour déboguer pourquoi seulement PRESTA001 apparaît dans les stats formateurs
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

def debug_formateur_data():
    """Analyse les données de formateurs dans la base de données"""
    
    # Vérifier les tables de formateurs
    with connection.cursor() as cursor:
        print("=== ANALYSE DES DONNÉES FORMATEURS ===\n")
        
        # 1. Vérifier AppelFormateur (table principale pour les scores)
        cursor.execute("""
            SELECT COUNT(*) as total,
                   COUNT(DISTINCT prestation_id) as prestations_uniques,
                   COUNT(CASE WHEN q1_prerequis_apprenants IS NOT NULL 
                              AND q2_interaction_apprenants IS NOT NULL 
                              AND q3_competences_acquises IS NOT NULL THEN 1 END) as avec_scores_complets
            FROM appels_appelformateur
        """)
        result = cursor.fetchone()
        print(f"AppelFormateur - Total: {result[0]}, Prestations uniques: {result[1]}, Avec scores complets: {result[2]}")
        
        # 2. Vérifier les prestations avec des scores
        cursor.execute("""
            SELECT DISTINCT prestation_id, 
                   COUNT(*) as nb_formateurs,
                   AVG(q1_prerequis_apprenants) as avg_q1,
                   AVG(q2_interaction_apprenants) as avg_q2,
                   AVG(q3_competences_acquises) as avg_q3,
                   AVG((q1_prerequis_apprenants + q2_interaction_apprenants + q3_competences_acquises) / 3) as avg_total
            FROM appels_appelformateur 
            WHERE q1_prerequis_apprenants IS NOT NULL 
              AND q2_interaction_apprenants IS NOT NULL 
              AND q3_competences_acquises IS NOT NULL
            GROUP BY prestation_id
            ORDER BY avg_total DESC
        """)
        prestations_with_scores = cursor.fetchall()
        
        print(f"\nPrestations avec scores complets ({len(prestations_with_scores)}):")
        for row in prestations_with_scores:
            print(f"  Prestation {row[0]}: {row[1]} formateurs, Score moyen: {row[5]:.2f}")
        
        # 3. Vérifier la table Prestation
        cursor.execute("""
            SELECT code, titre, actif 
            FROM formations_prestation 
            WHERE actif = 1
            ORDER BY code
            LIMIT 20
        """)
        prestations_actives = cursor.fetchall()
        
        print(f"\nPrestations actives dans la base ({len(prestations_actives)}):")
        for row in prestations_actives:
            print(f"  {row[0]}: {row[1]}")
        
        # 4. Vérifier les relations AppelFormateur -> Prestation
        cursor.execute("""
            SELECT af.prestation_id, p.code, p.titre, COUNT(*) as nb_formateurs
            FROM appels_appelformateur af
            LEFT JOIN formations_prestation p ON af.prestation_id = p.id
            WHERE af.prestation_id IS NOT NULL
            GROUP BY af.prestation_id, p.code, p.titre
            ORDER BY nb_formateurs DESC
            LIMIT 10
        """)
        relation_stats = cursor.fetchall()
        
        print(f"\nFormateurs par prestation (Top 10):")
        for row in relation_stats:
            print(f"  {row[1] or row[0]}: {row[3]} formateurs")

def debug_satisfaction_formateurs_context():
    """Analyse le contexte utilisé par _build_satisfaction_formateurs_dashboard_context"""
    
    print("\n=== ANALYSE DU CONTEXT SATISFACTION FORMATEURS ===\n")
    
    # Importer après configuration Django
    from App_PADESCE.satisfaction_formateurs.views import _build_satisfaction_formateurs_dashboard_context
    from django.test import RequestFactory
    
    # Créer une requête factice
    factory = RequestFactory()
    request = factory.get('/?scope=formateur&section=stats')
    
    try:
        ctx = _build_satisfaction_formateurs_dashboard_context(request)
        
        print(f"Total rows dans le contexte: {len(ctx.get('all_rows', []))}")
        
        # Analyser les prestations dans all_rows
        prestations_in_rows = {}
        for record in ctx.get('all_rows', []):
            prestation_id = getattr(record, 'prestation_id', None)
            if prestation_id:
                prestations_in_rows[prestation_id] = prestations_in_rows.get(prestation_id, 0) + 1
        
        print(f"Prestations dans all_rows: {len(prestations_in_rows)}")
        for prestation_id, count in list(prestations_in_rows.items())[:10]:
            print(f"  Prestation {prestation_id}: {count} enregistrements")
            
        # Vérifier les scores complets
        records_with_scores = 0
        for record in ctx.get('all_rows', []):
            if (getattr(record, 'q1_prerequis_apprenants', None) is not None and
                getattr(record, 'q2_interaction_apprenants', None) is not None and
                getattr(record, 'q3_competences_acquises', None) is not None):
                records_with_scores += 1
        
        print(f"Enregistrements avec scores complets: {records_with_scores}")
        
    except Exception as e:
        print(f"Erreur lors de l'analyse du contexte: {e}")

if __name__ == "__main__":
    setup_django()
    debug_formateur_data()
    debug_satisfaction_formateurs_context()

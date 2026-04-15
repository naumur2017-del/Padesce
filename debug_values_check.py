#!/usr/bin/env python3
"""
Script pour vérifier pourquoi les valeurs de scores sont considérées comme vides
"""

import os
import sys
import django
from django.conf import settings

def setup_django():
    """Configure Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
    django.setup()

def debug_values_check():
    """Vérifie pourquoi les valeurs de scores échouent le test"""
    
    from App_PADESCE.core.public_views import _formateur_record_value
    from App_PADESCE.satisfaction_formateurs.views import _build_satisfaction_formateurs_dashboard_context
    from App_PADESCE.appels.models import FORMATEUR_SCORE_FIELDS
    from django.test import RequestFactory
    
    print("=== DÉBOGAGE DU TEST DES VALEURS ===\n")
    
    # Créer une requête
    factory = RequestFactory()
    request = factory.get('/?scope=formateur&section=stats')
    
    # Obtenir le contexte source
    ctx_source = _build_satisfaction_formateurs_dashboard_context(request)
    all_rows = ctx_source.get('all_rows', [])
    
    print(f"FORMATEUR_SCORE_FIELDS: {FORMATEUR_SCORE_FIELDS}")
    
    # Analyser quelques enregistrements
    analyzed_count = 0
    for record in all_rows:
        values = []
        for field_name in FORMATEUR_SCORE_FIELDS:
            value = _formateur_record_value(record, field_name, None)
            values.append(value)
        
        print(f"\nEnregistrement {analyzed_count + 1}:")
        print(f"  Type de record: {type(record)}")
        print(f"  Valeurs brutes: {values}")
        
        # Vérifier chaque valeur individuellement
        for i, (field_name, value) in enumerate(zip(FORMATEUR_SCORE_FIELDS, values)):
            print(f"    {field_name}: {repr(value)} (type: {type(value)})")
            print(f"      value not in (None, ''): {value not in (None, '')}")
        
        # Test du conditionnel complet
        all_values_valid = all(value not in (None, "") for value in values)
        print(f"  Test 'all(value not in (None, \"\"))': {all_values_valid}")
        
        if all_values_valid:
            print(f"  -> CET ENREGISTREMENT SERAIT INCLUS!")
        else:
            print(f"  -> CET ENREGISTREMENT SERAIT IGNORÉ!")
        
        analyzed_count += 1
        if analyzed_count >= 5:
            break
    
    # Compter combien passent le test
    passing_records = 0
    failing_records = 0
    
    for record in all_rows:
        values = [
            _formateur_record_value(record, field_name, None)
            for field_name in FORMATEUR_SCORE_FIELDS
        ]
        
        if all(value not in (None, "") for value in values):
            passing_records += 1
        else:
            failing_records += 1
    
    print(f"\n=== RÉSUMÉ ===")
    print(f"Total enregistrements: {len(all_rows)}")
    print(f"Enregistrements passant le test: {passing_records}")
    print(f"Enregistrements échouant le test: {failing_records}")

if __name__ == "__main__":
    setup_django()
    debug_values_check()

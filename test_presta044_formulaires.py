#!/usr/bin/env python
"""
Test script to find the number of filled forms for prestation PRESTA044
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from App_PADESCE.core.models import Appel, AppelFormateur, Prestation
from agent_padesceV2.data_loader import build_padesce_source_index

print("=" * 80)
print("TESTING PRESTA044 - Form Count")
print("=" * 80)

# Test 1: Check if PRESTA044 exists in database
print("\n[1] Searching in database:")
prestations = Prestation.objects.filter(code__iexact='PRESTA044')
print(f"  Prestations found: {prestations.count()}")
if prestations.exists():
    for p in prestations:
        print(f"    - {p.code}: {p.libelle}")

# Test 2: Check AppelFormateur records for PRESTA044
print("\n[2] Checking AppelFormateur records:")
appel_formateurs = AppelFormateur.objects.filter(prestation__code__iexact='PRESTA044')
print(f"  AppelFormateur records: {appel_formateurs.count()}")
for af in appel_formateurs[:5]:
    print(f"    - Appel: {af.appel.code}, Formateur: {af.formateur}")

# Test 3: Check Appel records with PRESTA044
print("\n[3] Checking Appel records with PRESTA044:")
appels = Appel.objects.filter(code__contains='PRESTA044')
print(f"  Appel records with PRESTA044: {appels.count()}")

# Test 4: Load from Excel source
print("\n[4] Loading from Excel source:")
try:
    source_bundle = build_padesce_source_index(source_key="cutoff")
    
    # Search for PRESTA044 in source records
    matching_records = []
    for record in source_bundle.get("records", []):
        prestataire = record.get("prestataire", "").strip()
        beneficiaire = record.get("beneficiaire", "").strip()
        
        if prestataire.upper() == "PRESTA044" or beneficiaire.upper() == "PRESTA044":
            matching_records.append(record)
    
    print(f"  PRESTA044 records in Excel: {len(matching_records)}")
    
    # Count filled forms (records with responses)
    filled_forms = 0
    for record in matching_records:
        # Check if record has form responses (usually in formateur score fields)
        q1 = record.get("formateur_q1", None)
        q2 = record.get("formateur_q2", None)
        q3 = record.get("formateur_q3", None)
        
        # If any of these fields has a value, it's a filled form
        if any(v is not None and str(v).strip() for v in [q1, q2, q3]):
            filled_forms += 1
            print(f"    - Filled form: Q1={q1}, Q2={q2}, Q3={q3}")
    
    print(f"\n  Total filled forms: {filled_forms}")
    
except Exception as e:
    print(f"  Error loading source: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)

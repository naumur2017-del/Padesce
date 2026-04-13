#!/usr/bin/env python
"""Test script to verify formateur display for PRESTA064"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
django.setup()

from App_PADESCE.formations.models import Prestation
from App_PADESCE.reporting.network_excel import build_padesce_source_index
from types import SimpleNamespace

print("=" * 80)
print("TEST: Formateurs pour PRESTA064")
print("=" * 80)

# Get prestation from DB
prestation = Prestation.objects.filter(code__iexact='PRESTA064').select_related(
    'prestataire', 'beneficiaire', 'formation'
).first()

if not prestation:
    print("\n❌ PRESTA064 not found in database")
else:
    print(f"\n✅ Prestation found: {prestation.code}")
    print(f"   Prestataire: {prestation.prestataire.raison_sociale if prestation.prestataire else 'None'}")
    print(f"   Beneficiaire: {prestation.beneficiaire.nom_structure if prestation.beneficiaire else 'None'}")
    
    # Load source bundle
    try:
        source_bundle = build_padesce_source_index(source_key="cutoff")
        print(f"\n📊 Source bundle loaded")
    except Exception as e:
        print(f"\n❌ Error loading source bundle: {e}")
        source_bundle = None
    
    if source_bundle:
        # Simulate _prestation_formateur_candidates logic
        prestataire_name = str(
            prestation.prestataire.raison_sociale if prestation.prestataire else ""
        ).strip()
        beneficiaire_name = str(
            prestation.beneficiaire.nom_structure if prestation.beneficiaire else ""
        ).strip()
        
        print(f"\n🔍 Searching in Excel source_bundle:")
        print(f"   Prestataire: '{prestataire_name}'")
        print(f"   Beneficiaire: '{beneficiaire_name}'")
        
        # Search in source_bundle
        source_records = source_bundle.get("records", {}) or {}
        matching_rows = []
        
        for record_key, record in source_records.items():
            record_dict = dict(record) if not isinstance(record, dict) else record
            record_prestataire = str(record_dict.get("prestataire") or "").strip()
            record_beneficiaire = str(record_dict.get("beneficiaire") or "").strip()
            
            # Match if prestataire OR beneficiaire matches
            if (prestataire_name and record_prestataire.lower() == prestataire_name.lower()) or \
               (beneficiaire_name and record_beneficiaire.lower() == beneficiaire_name.lower()):
                matching_rows.append(record_dict)
        
        print(f"\n✅ Formateurs Found in Excel: {len(matching_rows)}")
        
        if matching_rows:
            print(f"\n   Sample records (showing first 5):")
            for i, row in enumerate(matching_rows[:5], 1):
                print(f"   {i}. {row.get('reference_code')}: prestataire='{row.get('prestataire')}', formation='{row.get('formation')}'")
        else:
            print(f"\n❌ No formateurs found in Excel for this prestation")
            
            # Debug: show what's in the database
            print(f"\n🔎 Checking unique prestataires in source (first 15):")
            unique_prest = set()
            for record in source_records.values():
                prest = str(record.get("prestataire") or "").strip()
                if prest:
                    unique_prest.add(prest)
            
            for prest in sorted(unique_prest)[:15]:
                print(f"   - '{prest}'")
    
    # Check database as fallback
    print(f"\n📦 Checking AppelFormateur database:")
    from App_PADESCE.appels.models import AppelFormateur
    from django.db.models import Q
    
    queryset = AppelFormateur.objects.filter(is_active=True)
    filters = Q()
    
    prestataire_name = str(
        prestation.prestataire.raison_sociale if prestation.prestataire else ""
    ).strip()
    beneficiaire_name = str(
        prestation.beneficiaire.nom_structure if prestation.beneficiaire else ""
    ).strip()
    
    if prestataire_name:
        filters |= Q(prestataire__iexact=prestataire_name)
    if beneficiaire_name:
        filters |= Q(beneficiaire__iexact=beneficiaire_name)
    
    if filters:
        db_results = queryset.filter(filters).count()
    else:
        db_results = 0
    
    print(f"   AppelFormateur records found: {db_results}")

print("\n" + "=" * 80)

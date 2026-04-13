#!/usr/bin/env python
"""Debug script to diagnose formateur display issue for CLA001"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
django.setup()

from App_PADESCE.formations.models import Classe, Prestation, AppelFormateur

# Get CLA001
print("=" * 80)
print("DEBUGGING CLA001 FORMATEURS")
print("=" * 80)

classe = Classe.objects.filter(code__iexact='CLA001').select_related(
    'prestation',
    'prestation__prestataire',
    'prestation__beneficiaire',
    'prestation__formation'
).first()

if not classe:
    print("❌ CLA001 not found in database")
else:
    print(f"\n✅ Classe found: {classe.code}")
    print(f"   Prestation: {classe.prestation}")
    
    if classe.prestation:
        prestation = classe.prestation
        print(f"\n📋 PRESTATION INFO:")
        print(f"   Code: {prestation.code}")
        print(f"   Prestataire: {prestation.prestataire.raison_sociale if prestation.prestataire else 'None'}")
        print(f"   Beneficiaire: {prestation.beneficiaire.nom_structure if prestation.beneficiaire else 'None'}")
        print(f"   Formation: {prestation.formation.nom if prestation.formation else 'None'}")
        
        # Search for formateurs
        prestataire_name = str(
            prestation.prestataire.raison_sociale if prestation.prestataire else ""
        ).strip()
        beneficiaire_name = str(
            prestation.beneficiaire.nom_structure if prestation.beneficiaire else ""
        ).strip()
        
        print(f"\n🔍 SEARCHING FORMATEURS:")
        print(f"   Prestataire name: '{prestataire_name}'")
        print(f"   Beneficiaire name: '{beneficiaire_name}'")
        
        # Count all active AppelFormateur
        all_formateurs = AppelFormateur.objects.filter(is_active=True).count()
        print(f"\n   Total active AppelFormateur records: {all_formateurs}")
        
        # Search by prestataire
        if prestataire_name:
            by_prestataire = AppelFormateur.objects.filter(
                is_active=True,
                prestataire__iexact=prestataire_name
            ).count()
            print(f"   By prestataire='{prestataire_name}': {by_prestataire} records")
        
        # Search by beneficiaire
        if beneficiaire_name:
            by_beneficiaire = AppelFormateur.objects.filter(
                is_active=True,
                beneficiaire__iexact=beneficiaire_name
            ).count()
            print(f"   By beneficiaire='{beneficiaire_name}': {by_beneficiaire} records")
        
        # Search by both (OR)
        from django.db.models import Q
        
        filters = Q()
        if prestataire_name:
            filters |= Q(prestataire__iexact=prestataire_name)
        if beneficiaire_name:
            filters |= Q(beneficiaire__iexact=beneficiaire_name)
        
        if filters:
            combined = AppelFormateur.objects.filter(is_active=True).filter(filters).count()
            print(f"   Combined (prestataire OR beneficiaire): {combined} records")
            
            # Show sample records
            samples = AppelFormateur.objects.filter(is_active=True).filter(filters)[:3]
            if samples:
                print(f"\n   Sample records found:")
                for sample in samples:
                    print(f"     - {sample.reference_code}: prestataire='{sample.prestataire}', beneficiaire='{sample.beneficiaire}'")
        
        # Check for exact matches in AppelFormateur
        print(f"\n   Checking unique prestataires in database:")
        unique_prest = set(
            AppelFormateur.objects.filter(is_active=True)
            .values_list('prestataire', flat=True)
            .distinct()
        )
        for prest in sorted(unique_prest)[:10]:
            if prest:
                print(f"     - '{prest}'")
        
        print(f"\n   Checking unique beneficiaires in database:")
        unique_benef = set(
            AppelFormateur.objects.filter(is_active=True)
            .values_list('beneficiaire', flat=True)
            .distinct()
        )
        for benef in sorted(unique_benef)[:10]:
            if benef:
                print(f"     - '{benef}'")

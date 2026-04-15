#!/usr/bin/env python
"""Debug script to diagnose formateur display issue for CLA001"""

import os

import django
from django.db.models import Q

from App_PADESCE.appels.models import AppelFormateur
from App_PADESCE.formations.models import Classe

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "App_PADESCE.settings")
django.setup()

print("=" * 80)
print("DEBUGGING CLA001 FORMATEURS")
print("=" * 80)

classe = (
    Classe.objects.filter(code__iexact="CLA001")
    .select_related(
        "prestation", "prestation__prestataire", "prestation__beneficiaire", "prestation__formation"
    )
    .first()
)

if not classe:
    print("\n❌ CLA001 not found in database")
else:
    print(f"\n✅ Classe found: {classe.code}")
    print(f"   Prestation: {classe.prestation}")

    if classe.prestation:
        prestation = classe.prestation
        print("\n📋 PRESTATION INFO:")
        print(f"   Code: {prestation.code}")
        print(
            f"   Prestataire: {prestation.prestataire.raison_sociale if prestation.prestataire else 'None'}"
        )
        print(
            f"   Beneficiaire: {prestation.beneficiaire.nom_structure if prestation.beneficiaire else 'None'}"
        )
        print(f"   Formation: {prestation.formation.nom if prestation.formation else 'None'}")

        # Search for formateurs
        prestataire_name = str(
            prestation.prestataire.raison_sociale if prestation.prestataire else ""
        ).strip()
        beneficiaire_name = str(
            prestation.beneficiaire.nom_structure if prestation.beneficiaire else ""
        ).strip()

        print("\n🔍 SEARCHING FORMATEURS:")
        print(f"   Prestataire name: '{prestataire_name}'")
        print(f"   Beneficiaire name: '{beneficiaire_name}'")

        # Count all active AppelFormateur
        all_formateurs = AppelFormateur.objects.filter(is_active=True).count()
        print(f"\n   Total active AppelFormateur records: {all_formateurs}")

        # Build filters
        filters = Q()
        if prestataire_name:
            filters |= Q(prestataire__iexact=prestataire_name)
        if beneficiaire_name:
            filters |= Q(beneficiaire__iexact=beneficiaire_name)

        if filters:
            combined = (
                AppelFormateur.objects.filter(is_active=True, **{"__".join([]): ""})
                .filter(filters)
                .count()
            )
            combined = AppelFormateur.objects.filter(is_active=True).filter(filters).count()
            print(f"\n   Combined (prestataire OR beneficiaire) matches: {combined} records")

            # Show sample records
            samples = AppelFormateur.objects.filter(is_active=True).filter(filters)[:5]
            if samples:
                print("\n   Sample records found:")
                for sample in samples:
                    print(
                        f"     - {sample.reference_code}: prestataire='{sample.prestataire}', beneficiaire='{sample.beneficiaire}', formation='{sample.formation}'"
                    )
        else:
            print("\n   ⚠️ No filters generated (prestataire and beneficiaire both empty)")
    else:
        print("\n❌ No prestation linked to this classe")

print("\n" + "=" * 80)

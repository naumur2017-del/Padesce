#!/usr/bin/env python
"""Debug script to check AppelFormateur for PRESTA072"""

import os

import django

from App_PADESCE.appels.models import AppelFormateur

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "App_PADESCE.settings")
django.setup()

print("=" * 80)
print("SEARCHING FORMATEURS FOR PRESTA072 / CENTRE DE FORMATION PROFESSIONNELLE PONTAAH")
print("=" * 80)

prestataire_name = "CENTRE DE FORMATION PROFESSIONNELLE PONTAAH"

# Search 1: Exact match
exact_match = AppelFormateur.objects.filter(
    is_active=True, prestataire__iexact=prestataire_name
).count()
print(f"\n1. Exact match on prestataire='{prestataire_name}':")
print(f"   Records found: {exact_match}")

if exact_match > 0:
    samples = AppelFormateur.objects.filter(is_active=True, prestataire__iexact=prestataire_name)[
        :5
    ]
    for sample in samples:
        print(
            f"   - {sample.reference_code}: beneficiaire='{sample.beneficiaire}', formation='{sample.formation}'"
        )

# Search 2: Case-insensitive partial match
partial_match = AppelFormateur.objects.filter(
    is_active=True, prestataire__icontains="PONTAAH"
).count()
print("\n2. Partial match on prestataire containing 'PONTAAH':")
print(f"   Records found: {partial_match}")

if partial_match > 0:
    samples = AppelFormateur.objects.filter(is_active=True, prestataire__icontains="PONTAAH")[:5]
    for sample in samples:
        print(f"     - prestataire='{sample.prestataire}'")

# Search 3: All unique prestataires in database
print("\n3. All unique prestataires in database (first 20):")
unique_prest = (
    AppelFormateur.objects.filter(is_active=True)
    .values_list("prestataire", flat=True)
    .distinct()
    .order_by("prestataire")[:20]
)
for i, prest in enumerate(unique_prest, 1):
    if prest.strip():
        print(f"   {i}. '{prest}'")

# Search 4: Check if table is completely empty
total_records = AppelFormateur.objects.filter(is_active=True).count()
print(f"\n4. Total active AppelFormateur records in database: {total_records}")

print("\n" + "=" * 80)

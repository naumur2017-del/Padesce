#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
django.setup()

from App_PADESCE.appels.models import AppelFormateur

try:
    total = AppelFormateur.objects.filter(is_active=True).count()
    print(f"Total AppelFormateur actifs: {total}")
    
    count_pontaah = AppelFormateur.objects.filter(
        is_active=True, 
        prestataire__iexact="CENTRE DE FORMATION PROFESSIONNELLE PONTAAH"
    ).count()
    print(f"Avec prestataire=PONTAAH: {count_pontaah}")
    
    if count_pontaah > 0:
        print("\nExemples:")
        for rec in AppelFormateur.objects.filter(is_active=True, prestataire__iexact="CENTRE DE FORMATION PROFESSIONNELLE PONTAAH")[:3]:
            print(f"  - {rec.reference_code}: {rec.prestataire}")
    
    # List all unique prestataires
    print("\nTous les prestataires (premiers 10):")
    for prest in AppelFormateur.objects.filter(is_active=True).values_list('prestataire', flat=True).distinct()[:10]:
        if prest:
            print(f"  - '{prest}'")
            
except Exception as e:
    print(f"Erreur: {e}")
    import traceback
    traceback.print_exc()

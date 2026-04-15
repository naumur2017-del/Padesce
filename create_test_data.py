#!/usr/bin/env python3
"""
Script pour créer des données de test après la recréation de la base de données
"""

import os
import sys
import django
from django.conf import settings
from django.contrib.auth.models import User
from App_PADESCE.formations.models import Prestation, Formation, Beneficiaire

def setup_django():
    """Configure Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
    django.setup()

def create_test_data():
    """Crée des données de test de base"""
    
    # Créer un utilisateur admin si nécessaire
    if not User.objects.filter(username='admin').exists():
        admin = User.objects.create_superuser('admin', 'admin@example.com', 'admin')
        print("Utilisateur admin créé")
    else:
        admin = User.objects.get(username='admin')
        print("Utilisateur admin existe déjà")
    
    # Créer un bénéficiaire de test
    beneficiaire, created = Beneficiaire.objects.get_or_create(
        nom="Bénéficiaire Test",
        defaults={
            'description': "Bénéficiaire de test pour les prestations",
            'created_by': admin
        }
    )
    if created:
        print(f"Bénéficiaire créé: {beneficiaire.nom}")
    else:
        print(f"Bénéficiaire existe déjà: {beneficiaire.nom}")
    
    # Créer quelques prestations de test
    prestations_data = [
        {
            'code': 'PRESTA046',
            'titre': 'Formation Test 1',
            'description': 'Description de la formation test 1',
            'beneficiaire': beneficiaire,
            'created_by': admin
        },
        {
            'code': 'PRESTA001',
            'titre': 'Formation Test 2', 
            'description': 'Description de la formation test 2',
            'beneficiaire': beneficiaire,
            'created_by': admin
        },
        {
            'code': 'PRESTA166',
            'titre': 'Formation Test 3',
            'description': 'Description de la formation test 3', 
            'beneficiaire': beneficiaire,
            'created_by': admin
        }
    ]
    
    for prestation_data in prestations_data:
        prestation, created = Prestation.objects.get_or_create(
            code=prestation_data['code'],
            defaults=prestation_data
        )
        if created:
            print(f"Prestation créée: {prestation.code} - {prestation.titre}")
        else:
            print(f"Prestation existe déjà: {prestation.code}")
    
    # Créer une formation liée à PRESTA046
    try:
        prestation046 = Prestation.objects.get(code='PRESTA046')
        formation, created = Formation.objects.get_or_create(
            prestation=prestation046,
            defaults={
                'date_debut': '2026-04-15',
                'lieu': 'Lieu Test',
                'created_by': admin
            }
        )
        if created:
            print(f"Formation créée pour PRESTA046")
        else:
            print(f"Formation existe déjà pour PRESTA046")
    except Prestation.DoesNotExist:
        print("PRESTA046 n'existe pas")
    
    print("\nDonnées de test créées avec succès!")
    print(f"Total prestations: {Prestation.objects.count()}")
    print(f"Total formations: {Formation.objects.count()}")

if __name__ == "__main__":
    setup_django()
    create_test_data()

#!/usr/bin/env python
"""
Script de test pour vérifier la connexion à la base de données SQLite de backup
et vérifier que les données des appels formateurs sont accessibles.
"""

import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

django.setup()

from App_PADESCE.appels.models import AppelFormateur
from App_PADESCE.satisfaction_formateurs.views import _build_satisfaction_formateurs_dashboard_context
from django.test import RequestFactory

def main():
    print("=== Test de connexion à la base de données SQLite de backup ===\n")
    
    # 1. Vérifier la connexion à la base de données
    try:
        total_records = AppelFormateur.objects.count()
        active_records = AppelFormateur.objects.filter(is_active=True).count()
        
        print(f"Connexion réussie !")
        print(f"Total des enregistrements dans AppelFormateur: {total_records}")
        print(f"Enregistrements actifs: {active_records}")
        
    except Exception as e:
        print(f"ERREUR de connexion: {e}")
        return
    
    # 2. Vérifier les données de satisfaction
    if active_records > 0:
        print(f"\n=== Vérification des données de satisfaction ===")
        
        # Compter les enregistrements avec des scores
        with_scores = AppelFormateur.objects.filter(
            is_active=True,
            q1_prerequis_apprenants__isnull=False
        ).count()
        
        print(f"Enregistrements avec scores Q1: {with_scores}")
        
        # Voir quelques exemples
        sample = AppelFormateur.objects.filter(is_active=True)[:5]
        print(f"\nExemples d'appels formateurs:")
        for i, record in enumerate(sample, 1):
            print(f"  {i}. {record.reference_code} - {record.prestataire} - {record.beneficiaire}")
            print(f"     Q1: {record.q1_prerequis_apprenants}, Q2: {record.q2_interaction_apprenants}, Q3: {record.q3_competences_acquises}")
        
        # 3. Tester le calcul des statistiques
        print(f"\n=== Test du calcul des statistiques ===")
        try:
            # Créer une requête factice
            factory = RequestFactory()
            request = factory.get('/satisfaction-formateurs/analyse/')
            
            # Calculer le contexte du dashboard
            context = _build_satisfaction_formateurs_dashboard_context(request)
            
            print(f"Statistiques calculées avec succès !")
            print(f"Nombre de prestataires: {len(context['prestataires'])}")
            print(f"Nombre de bénéficiaires: {len(context['beneficiaires'])}")
            print(f"Nombre de cohortes: {len(context['cohortes'])}")
            print(f"Nombre de statistiques par prestation: {len(context['prestation_stats'])}")
            
            # Afficher quelques statistiques par prestation
            if context['prestation_stats']:
                print(f"\nExemples de statistiques par prestation:")
                for i, stat in enumerate(context['prestation_stats'][:3], 1):
                    print(f"  {i}. {stat['label']}: Nb={stat['nb']}, Moyennes={stat['avgs']}")
            
        except Exception as e:
            print(f"ERREUR lors du calcul des statistiques: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Aucun enregistrement actif trouvé dans la base de données.")
    
    print(f"\n=== Test terminé ===")

if __name__ == '__main__':
    main()

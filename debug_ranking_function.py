#!/usr/bin/env python3
"""
Script pour déboguer la fonction get_prestations_ranking
"""

import os
import sys
import django
from django.conf import settings

def setup_django():
    """Configure Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
    django.setup()

def debug_ranking_function():
    """Débogue la fonction get_prestations_ranking"""
    
    from App_PADESCE.core.public_views import _build_formateur_stats
    from App_PADESCE.satisfaction_apprenants.services import get_prestations_ranking
    from django.test import RequestFactory
    
    print("=== DÉBOGAGE FONCTION RANKING ===\n")
    
    # Créer une requête
    factory = RequestFactory()
    request = factory.get('/?scope=formateur&section=stats')
    
    # Obtenir les stats brutes avant le ranking
    ctx = _build_formateur_stats(request)
    
    # Simuler le calcul des prestation_stats manuellement
    from App_PADESCE.satisfaction_formateurs.views import _build_satisfaction_formateurs_dashboard_context
    from App_PADESCE.core.public_views import _formateur_record_value, _resolve_formateur_classe
    from App_PADESCE.appels.models import FORMATEUR_SCORE_FIELDS
    
    ctx_source = _build_satisfaction_formateurs_dashboard_context(request)
    all_rows = ctx_source.get('all_rows', [])
    
    resolution_cache = {}
    grouped = {}
    
    for record in all_rows:
        classe = _resolve_formateur_classe(record, resolution_cache)
        prestation = getattr(classe, "prestation", None)
        code = str(getattr(prestation, "code", "") or "").strip()
        
        if not code:
            prestataire_val = _formateur_record_value(record, "prestataire") or "-"
            beneficiaire_val = _formateur_record_value(record, "beneficiaire") or "-"
            formation_val = _formateur_record_value(record, "formation") or "-"
            
            if prestataire_val != "-" and beneficiaire_val != "-":
                code = f"{prestataire_val[:10]}-{beneficiaire_val[:10]}"
            elif formation_val != "-":
                code = f"FORMATION-{formation_val[:15]}"
            else:
                code = f"FORMATEUR-{record.get('id', 'UNKNOWN')}"
        
        group_key = code
        
        bucket = grouped.setdefault(
            group_key,
            {
                "code": code,
                "prestataire": _formateur_record_value(record, "prestataire") or "-",
                "beneficiaire": _formateur_record_value(record, "beneficiaire") or "-",
                "effectif": 0,
                "nb": 0,
                "scores": {field_name: [] for field_name in FORMATEUR_SCORE_FIELDS},
            },
        )
        bucket["effectif"] += 1
        
        values = [
            _formateur_record_value(record, field_name, None)
            for field_name in FORMATEUR_SCORE_FIELDS
        ]
        if not all(value not in (None, "") for value in values):
            continue
        
        bucket["nb"] += 1
        for field_name, value in zip(FORMATEUR_SCORE_FIELDS, values):
            bucket["scores"][field_name].append(float(value))
    
    # Calculer les stats
    prestation_stats = []
    for item in grouped.values():
        if not item["nb"]:
            continue
        avgs = []
        for field_name in FORMATEUR_SCORE_FIELDS:
            values = item["scores"][field_name]
            avgs.append(round(sum(values) / len(values), 2) if values else 0)
        avg = round(sum(avgs) / len(avgs), 2) if avgs else 0
        
        prestation_stats.append({
            "code": item["code"],
            "prestataire": item["prestataire"],
            "beneficiaire": item["beneficiaire"],
            "nb": item["nb"],
            "avg": avg,
            "avgs": avgs,
            "effectif": item["effectif"],
        })
    
    print(f"prestation_stats calculées: {len(prestation_stats)}")
    print("\nExemples de prestation_stats:")
    for i, item in enumerate(prestation_stats[:5]):
        print(f"  {i+1}. {item['code']}: Score {item['avg']:.2f}, Nb {item['nb']}, Effectif {item['effectif']}")
    
    # Tester la fonction get_prestations_ranking
    print(f"\n=== TEST DE get_prestations_ranking ===")
    
    best_rankings = get_prestations_ranking(prestation_stats, order="desc")
    improve_rankings = get_prestations_ranking(prestation_stats, order="asc")
    
    print(f"best_rankings retournés: {len(best_rankings)}")
    print(f"improve_rankings retournés: {len(improve_rankings)}")
    
    print(f"\nTop 5 best_rankings:")
    for i, item in enumerate(best_rankings[:5]):
        print(f"  {i+1}. {item}")
    
    print(f"\nTop 5 improve_rankings:")
    for i, item in enumerate(improve_rankings[:5]):
        print(f"  {i+1}. {item}")

if __name__ == "__main__":
    setup_django()
    debug_ranking_function()

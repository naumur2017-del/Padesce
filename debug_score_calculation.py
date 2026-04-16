#!/usr/bin/env python3
"""
Script pour analyser pourquoi les scores sont tous à 0.00
"""

import os
import sys
import django
from django.conf import settings
from django.db import connection

def setup_django():
    """Configure Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
    django.setup()

def debug_score_calculation():
    """Analyse le calcul des scores dans _build_formateur_stats"""
    
    from App_PADESCE.core.public_views import _build_formateur_stats, _formateur_record_value
    from App_PADESCE.satisfaction_formateurs.views import _build_satisfaction_formateurs_dashboard_context
    from App_PADESCE.appels.models import FORMATEUR_SCORE_FIELDS
    from django.test import RequestFactory
    
    print("=== DÉBOGAGE CALCUL DES SCORES ===\n")
    print(f"FORMATEUR_SCORE_FIELDS: {FORMATEUR_SCORE_FIELDS}")
    
    # Créer une requête
    factory = RequestFactory()
    request = factory.get('/?scope=formateur&section=stats')
    
    # Obtenir le contexte source
    ctx_source = _build_satisfaction_formateurs_dashboard_context(request)
    all_rows = ctx_source.get('all_rows', [])
    
    print(f"\nTotal rows dans le contexte: {len(all_rows)}")
    
    # Analyser les rows avec des scores
    rows_with_complete_scores = []
    for record in all_rows:
        values = []
        for field_name in FORMATEUR_SCORE_FIELDS:
            value = _formateur_record_value(record, field_name, None)
            values.append(value)
        
        if all(value not in (None, "") for value in values):
            rows_with_complete_scores.append((record, values))
    
    print(f"Rows avec scores complets: {len(rows_with_complete_scores)}")
    
    # Afficher quelques exemples
    print(f"\nExemples de rows avec scores complets:")
    for i, (record, values) in enumerate(rows_with_complete_scores[:5]):
        print(f"  {i+1}. Record ID: {getattr(record, 'id', 'N/A')}")
        print(f"     Prestataire: {getattr(record, 'prestataire', 'N/A')}")
        print(f"     Bénéficiaire: {getattr(record, 'beneficiaire', 'N/A')}")
        print(f"     Formation: {getattr(record, 'formation', 'N/A')}")
        print(f"     Scores bruts: {values}")
        
        # Calculer le score moyen
        float_values = [float(v) for v in values]
        avg_score = round(sum(float_values) / len(float_values), 2)
        print(f"     Score calculé: {avg_score}")
        print()
    
    # Simuler le groupement comme dans _build_formateur_stats
    print("=== SIMULATION DU GROUPEMENT ===\n")
    
    resolution_cache = {}
    grouped = {}
    
    for record, values in rows_with_complete_scores:
        # Simuler la résolution de classe
        from App_PADESCE.core.public_views import _resolve_formateur_classe
        classe = _resolve_formateur_classe(record, resolution_cache)
        prestation = getattr(classe, "prestation", None)
        code = str(getattr(prestation, "code", "") or "").strip()
        
        # Si pas de code, créer un code synthétique
        if not code:
            prestataire_val = _formateur_record_value(record, "prestataire") or "-"
            beneficiaire_val = _formateur_record_value(record, "beneficiaire") or "-"
            formation_val = _formateur_record_value(record, "formation") or "-"
            
            if prestataire_val != "-" and beneficiaire_val != "-":
                code = f"{prestataire_val[:10]}-{beneficiaire_val[:10]}"
            elif formation_val != "-":
                code = f"FORMATION-{formation_val[:15]}"
            else:
                code = f"FORMATEUR-{getattr(record, 'id', 'UNKNOWN')}"
        
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
        bucket["nb"] += 1
        
        for field_name, value in zip(FORMATEUR_SCORE_FIELDS, values):
            bucket["scores"][field_name].append(float(value))
    
    print(f"Groupes créés: {len(grouped)}")
    
    # Calculer les moyennes pour chaque groupe
    prestation_stats = []
    for group_key, item in grouped.items():
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
    
    print(f"\nStats calculées: {len(prestation_stats)}")
    
    # Trier et afficher les résultats
    prestation_stats.sort(key=lambda x: x["avg"], reverse=True)
    
    print(f"\nTop 10 prestations par score:")
    for i, item in enumerate(prestation_stats[:10]):
        print(f"  {i+1}. {item['code']} | Score: {item['avg']:.2f} | Nb: {item['nb']} | Effectif: {item['effectif']}")
        print(f"     Prestataire: {item['prestataire']}")
        print(f"     Bénéficiaire: {item['beneficiaire']}")
        print(f"     Détails scores: {item['avgs']}")
        print()

if __name__ == "__main__":
    setup_django()
    debug_score_calculation()

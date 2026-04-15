#!/usr/bin/env python3
"""
Script pour déboguer la création des buckets et l'ajout des scores
"""

import os
import sys
import django
from django.conf import settings

def setup_django():
    """Configure Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
    django.setup()

def debug_bucket_creation():
    """Débogue la création des buckets dans _build_formateur_stats"""
    
    from App_PADESCE.core.public_views import _formateur_record_value, _resolve_formateur_classe
    from App_PADESCE.satisfaction_formateurs.views import _build_satisfaction_formateurs_dashboard_context
    from App_PADESCE.appels.models import FORMATEUR_SCORE_FIELDS
    from django.test import RequestFactory
    
    print("=== DÉBOGAGE CRÉATION DES BUCKETS ===\n")
    
    # Créer une requête
    factory = RequestFactory()
    request = factory.get('/?scope=formateur&section=stats')
    
    # Obtenir le contexte source
    ctx_source = _build_satisfaction_formateurs_dashboard_context(request)
    all_rows = ctx_source.get('all_rows', [])
    
    # Simuler exactement le code de _build_formateur_stats
    resolution_cache = {}
    grouped = {}
    
    processed_records = 0
    records_with_scores = 0
    records_added_to_buckets = 0
    
    for record in all_rows:
        processed_records += 1
        
        # Résolution de classe
        classe = _resolve_formateur_classe(record, resolution_cache)
        prestation = getattr(classe, "prestation", None)
        code = str(getattr(prestation, "code", "") or "").strip()
        
        # Créer code synthétique si nécessaire
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
        
        # Créer ou obtenir le bucket
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
        
        # Obtenir les valeurs de score
        values = [
            _formateur_record_value(record, field_name, None)
            for field_name in FORMATEUR_SCORE_FIELDS
        ]
        
        # Vérifier si toutes les valeurs sont présentes
        if all(value not in (None, "") for value in values):
            records_with_scores += 1
            
            # Ajouter au bucket
            bucket["nb"] += 1
            records_added_to_buckets += 1
            
            for field_name, value in zip(FORMATEUR_SCORE_FIELDS, values):
                bucket["scores"][field_name].append(float(value))
                
                # Afficher les détails pour le premier enregistrement
                if records_added_to_buckets <= 3:
                    print(f"  Ajout au bucket '{code}':")
                    print(f"    {field_name}: {value} -> {float(value)}")
        
        # Limiter l'analyse aux premiers enregistrements
        if processed_records >= 20:
            break
    
    print(f"\n=== STATISTIQUES ===")
    print(f"Enregistrements traités: {processed_records}")
    print(f"Enregistrements avec scores complets: {records_with_scores}")
    print(f"Enregistrements ajoutés aux buckets: {records_added_to_buckets}")
    print(f"Buckets créés: {len(grouped)}")
    
    # Afficher l'état des buckets
    print(f"\n=== ÉTAT DES BUCKETS ===")
    for code, bucket in list(grouped.items())[:10]:
        print(f"Bucket '{code}':")
        print(f"  Effectif: {bucket['effectif']}")
        print(f"  Nb (avec scores): {bucket['nb']}")
        print(f"  Scores par champ:")
        for field_name, values in bucket['scores'].items():
            print(f"    {field_name}: {len(values)} valeurs -> {values}")
        print()
    
    # Calculer les stats finales
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
    
    print(f"=== STATS FINALES ===")
    print(f"Prestations avec stats: {len(prestation_stats)}")
    
    for item in prestation_stats[:5]:
        print(f"  {item['code']}: Score {item['avg']:.2f}, Nb {item['nb']}, Effectif {item['effectif']}")

if __name__ == "__main__":
    setup_django()
    debug_bucket_creation()

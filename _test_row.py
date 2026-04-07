import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "App_PADESCE.settings")
django.setup()

from App_PADESCE.core.fast_stats import build_fast_stats_bundle, request_like_with_query

req = request_like_with_query("")
bundle = build_fast_stats_bundle(req)
apprenant_mode = next(m for m in bundle["modes"] if m["id"] == "apprenant")

print("--- Exemple de classe VIRTUAL ---")
for row in apprenant_mode["rows"]:
    if row["calls_effectues"] == 0 and row["apprenant_count"] > 0:
        print(f"Classe: {row['classe_id']}")
        print(f"Prestation: {row['prestation_id']}")
        print(f"Inscrits: {row['apprenant_count']}")
        print(f"Effectues: {row['calls_effectues']}")
        print(f"Termines: {row['calls_termines']}")
        print(f"% Effectues label: {row['pct_appel_effectue_label']}")
        print(f"% Termines label: {row['pct_appel_termine_label']}")
        break

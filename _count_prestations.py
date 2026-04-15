import os

import django

from App_PADESCE.core.fast_stats import build_fast_stats_bundle, request_like_with_query
from App_PADESCE.reporting.network_excel import build_padesce_source_index

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "App_PADESCE.settings")
django.setup()

print("=== FAST STATS BUNDLE ===")
req = request_like_with_query("")
bundle = build_fast_stats_bundle(req)
apprenant_mode = next(m for m in bundle["modes"] if m["id"] == "apprenant")

prestations = set()
for row in apprenant_mode["rows"]:
    prestations.add(row.get("prestation_id", ""))

print(f"Nombre de prestations uniques dans FAST STATS: {len(prestations)}")

print("\n=== SOURCE EXCEL ===")
source = build_padesce_source_index()
source_classes = source.get("classes", {})
source_prestations = set(
    info.get("prestation_id", "") for info in source_classes.values() if info.get("prestation_id")
)
print(f"Nombre de prestations liees a des classes dans Excel: {len(source_prestations)}")
print(
    f"Nombre total de prestations definies dans Excel (count): {source.get('counts', {}).get('prestations', 0)}"
)

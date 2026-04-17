import json
import os
import sys

import django

# Add current directory to path
sys.path.append(os.getcwd())

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "App_PADESCE.settings")
django.setup()

from App_PADESCE.appels.models import AppelFormateur

# Query records
qs = AppelFormateur.objects.filter(is_active=True).values(
    "id", "reference_code", "prestataire", "beneficiaire", "formation", "telephone", "status"
)

# Save to JSON
with open("scratch/db_formateurs.json", "w", encoding="utf-8") as f:
    json.dump(list(qs), f, indent=2, ensure_ascii=False)

print(f"Dumped {len(qs)} records to scratch/db_formateurs.json")

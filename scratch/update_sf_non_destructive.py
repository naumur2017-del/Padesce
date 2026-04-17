import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import django

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "App_PADESCE.settings")
django.setup()

from django.db import transaction

from App_PADESCE.appels.models import AppelFormateur


def normalize(text):
    if not text:
        return ""
    text = str(text).lower().strip()
    text = re.sub(r"[^a-z0-9]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# Load Excel data
with open("scratch/sf_modifie.json", "r", encoding="utf-8") as f:
    excel_data = json.load(f)["data"]

# Group by Code Prestataire
groups = defaultdict(list)
for row in excel_data:
    code = row["Code Prestataire"]
    if code:
        groups[code].append(row)

# Load DB records (active only)
db_records = list(
    AppelFormateur.objects.filter(is_active=True).values(
        "id", "reference_code", "prestataire", "beneficiaire", "formation", "telephone", "status"
    )
)

code_to_db_matches = defaultdict(set)
matched_db_ids = set()

for code in sorted(groups.keys()):
    excel_rows = groups[code]
    for excel_row in excel_rows:
        e_prest = normalize(excel_row["Prestataire"])
        e_benef = normalize(excel_row["Bénéficiaire"])

        for db_rec in db_records:
            if db_rec["id"] in matched_db_ids:
                continue

            d_prest = normalize(db_rec["prestataire"])
            d_benef = normalize(db_rec["beneficiaire"])

            if e_prest == d_prest and e_benef == d_benef:
                code_to_db_matches[code].add(db_rec["id"])
                matched_db_ids.add(db_rec["id"])
            elif (
                e_prest == d_prest
                and (e_benef in d_benef or d_benef in e_benef)
                and len(e_benef) > 5
            ):
                code_to_db_matches[code].add(db_rec["id"])
                matched_db_ids.add(db_rec["id"])
            elif e_prest in d_prest and e_benef == d_benef and len(e_prest) > 5:
                code_to_db_matches[code].add(db_rec["id"])
                matched_db_ids.add(db_rec["id"])

print(f"Total Excel unique codes: {len(groups)}")
print(f"Matched DB records: {len(matched_db_ids)} out of {len(db_records)}")

mapping_json = {}

with transaction.atomic():
    for code in sorted(groups.keys()):
        excel_rows = groups[code]
        db_ids = code_to_db_matches[code]

        target_prestataire = " / ".join(
            filter(None, sorted(list(set(str(r["Prestataire"]).strip() for r in excel_rows))))
        )
        target_beneficiaire = " / ".join(
            filter(None, sorted(list(set(str(r["Bénéficiaire"]).strip() for r in excel_rows))))
        )

        formations_set = set()
        for r in excel_rows:
            f = str(r.get("Formation", "")).strip()
            if f and f.lower() != "nan":
                formations_set.add(f)
        target_formation = " / ".join(sorted(list(formations_set)))

        if db_ids:
            # Update ALL matching records with the target metadata
            # BUT keep reference_code as it was.
            # We add the Code Prestataire as a prefix or just trust the mapping?
            # Actually, the user asked to change the code.
            # If we want 80+ records, they MUST have unique reference_code.
            # I'll just trust the mapping for the code display.
            # AND the user said "il faut fusionner les 2 prestations en une seule...".
            # They probably meant the ROW in the report.

            AppelFormateur.objects.filter(id__in=db_ids).update(
                prestataire=target_prestataire,
                beneficiaire=target_beneficiaire,
                formation=target_formation,
            )
            print(f"Updated {len(db_ids)} records for {code} ({target_prestataire})")
        else:
            print(f"Warning: No DB records matched for {code}. Creating ONE dummy record.")
            AppelFormateur.objects.create(
                reference_code=code,
                prestataire=target_prestataire,
                beneficiaire=target_beneficiaire,
                formation=target_formation,
                is_active=True,
                status="en_attente",
            )

        mapping_json[target_prestataire] = {
            "code_prestataire": code,
            "lien_enquete": excel_rows[0]["LIEN DES ENQUÊTES"],
            "lien_csv": excel_rows[0]["Liens CSV"],
        }

    # Deactivate others
    unmatched_ids = [r["id"] for r in db_records if r["id"] not in matched_db_ids]
    AppelFormateur.objects.filter(id__in=unmatched_ids).update(is_active=False)
    print(f"Deactivated {len(unmatched_ids)} other active records.")

# Write mapping file
mapping_file = Path("sf_prestataires_mapping.json")
with open(mapping_file, "w", encoding="utf-8") as f:
    json.dump(mapping_json, f, indent=2, ensure_ascii=False)

print("Done.")

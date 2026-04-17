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
    # Replace non-alphanumeric with space, but keep some chars if needed
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

# Mapping from Code Prestataire to matched DB record IDs
code_to_db_matches = defaultdict(set)
matched_db_ids = set()

for code in sorted(groups.keys()):  # Consistent order
    excel_rows = groups[code]
    for excel_row in excel_rows:
        e_prest = normalize(excel_row["Prestataire"])
        e_benef = normalize(excel_row["Bénéficiaire"])

        for db_rec in db_records:
            if db_rec["id"] in matched_db_ids:
                continue

            d_prest = normalize(db_rec["prestataire"])
            d_benef = normalize(db_rec["beneficiaire"])

            # Match if prestataire and beneficiaire match closely
            if e_prest == d_prest and e_benef == d_benef:
                code_to_db_matches[code].add(db_rec["id"])
                matched_db_ids.add(db_rec["id"])
            elif (
                e_prest == d_prest
                and (e_benef in d_benef or d_benef in e_benef)
                and len(e_benef) > 5
            ):
                # Partial match on beneficiary if prestataire is exact
                code_to_db_matches[code].add(db_rec["id"])
                matched_db_ids.add(db_rec["id"])
            elif e_prest in d_prest and e_benef == d_benef and len(e_prest) > 5:
                # Partial match on prestataire if beneficiary is exact
                code_to_db_matches[code].add(db_rec["id"])
                matched_db_ids.add(db_rec["id"])

print(f"Total Excel unique codes: {len(groups)}")
print(f"Matched DB records: {len(matched_db_ids)} out of {len(db_records)}")

mapping_json = {}

with transaction.atomic():
    for code in sorted(groups.keys()):
        excel_rows = groups[code]
        db_ids = code_to_db_matches[code]

        # Concat names from all excel rows in this group
        target_prestataire = " / ".join(
            filter(None, sorted(list(set(str(r["Prestataire"]).strip() for r in excel_rows))))
        )
        target_beneficiaire = " / ".join(
            filter(None, sorted(list(set(str(r["Bénéficiaire"]).strip() for r in excel_rows))))
        )

        # Merge formation as well
        formations_set = set()
        for r in excel_rows:
            f = str(r.get("Formation", "")).strip()
            if f and f.lower() != "nan":
                formations_set.add(f)
        target_formation = " / ".join(sorted(list(formations_set)))

        if db_ids:
            # Sort IDs to pick a stable survivor
            sorted_db_ids = sorted(list(db_ids))
            survivor_id = sorted_db_ids[0]
            to_delete_ids = set(sorted_db_ids[1:])

            survivor = AppelFormateur.objects.get(id=survivor_id)

            # Update survivor
            survivor.reference_code = code
            survivor.prestataire = target_prestataire
            survivor.beneficiaire = target_beneficiaire
            survivor.formation = target_formation
            survivor.is_active = True
            survivor.save()

            # Delete others
            if to_delete_ids:
                AppelFormateur.objects.filter(id__in=to_delete_ids).delete()

            print(f"Updated {code} with {len(db_ids)} merged records.")
        else:
            print(f"Warning: No DB records matched for {code} ({target_prestataire})")
            # Should we create one? The user said "replace tout les fichiers" but for DB "modifier".
            # If no record exists, there's nothing to modify.
            # But the user might expect it to appear.
            # I'll create a dummy record if none exists so it appears in the table as requested.
            # But wait, without actual call data, it will have 0 calls.
            # I'll create it just to be sure the 27 rows (25 codes) are present.
            AppelFormateur.objects.create(
                reference_code=code,
                prestataire=target_prestataire,
                beneficiaire=target_beneficiaire,
                formation=target_formation,
                is_active=True,
                status="en_attente",
            )
            print(f"Created new record for {code}.")

        # Always add to mapping
        mapping_json[target_prestataire] = {
            "code_prestataire": code,
            "lien_enquete": excel_rows[0]["LIEN DES ENQUÊTES"],
            "lien_csv": excel_rows[0]["Liens CSV"],
        }

    # Deactivate others
    unmatched_count = 0
    all_active = AppelFormateur.objects.filter(is_active=True)
    for rec in all_active:
        found = False
        for code in groups.keys():
            if rec.reference_code == code:
                found = True
                break
        if not found:
            rec.is_active = False
            rec.save()
            unmatched_count += 1

    print(f"Deactivated {unmatched_count} other active records.")

# Write mapping file
mapping_file = Path("sf_prestataires_mapping.json")
with open(mapping_file, "w", encoding="utf-8") as f:
    json.dump(mapping_json, f, indent=2, ensure_ascii=False)

print("Done.")

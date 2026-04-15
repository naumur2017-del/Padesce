import os
import sys

import django
import openpyxl

from App_PADESCE.appels.models import AppelFormateur

# Setup Django Environment
sys.path.append(r"D:\Documents\NAUMUR\Projet PADESCE Call\Padesce")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "App_PADESCE.settings")
django.setup()


def run():
    print("Loading excel workbook...")
    wb = openpyxl.load_workbook(
        r"docs\data\network_excel_cache\network-fichier-consolide.xlsm",
        read_only=True,
        data_only=True,
    )
    sheet = wb["Consolidation"]

    # phone -> (Beneficiaire, Prestataire)
    phone_map = {}

    print("Parsing Consolidation sheet...")
    for row in sheet.iter_rows(min_row=2, values_only=True):
        tel = str(row[24]).strip() if row[24] else None
        if not tel or tel == "None":
            continue

        benef = str(row[2]).strip() if row[2] else None
        prest = str(row[9]).strip() if row[9] else None

        # We assume one phone matches roughly one (benef, prest) pair or we just take the first one
        if tel not in phone_map:
            phone_map[tel] = (benef, prest)

    print(f"Found {len(phone_map)} formateur phones in excel.")

    print("Updating AppelFormateur records...")
    updated_count = 0

    # We look for records that have either beneficiaire or prestataire empty or NULL
    # or ones that have "prestataire" as literal string which might be a default placeholder.
    calls = AppelFormateur.objects.all()
    for call in calls:
        phone = call.telephone
        if not phone:
            continue

        # Clean phone if needed (e.g., remove spaces)
        phone = "".join(c for c in phone if c.isdigit())

        if phone in phone_map:
            benef_excel, prest_excel = phone_map[phone]
            needs_update = False

            # Update if empty or generic placeholder
            if (
                not call.beneficiaire
                or call.beneficiaire.lower() == "beneficiaire"
                or call.beneficiaire.strip() == ""
            ):
                if benef_excel:
                    call.beneficiaire = benef_excel
                    needs_update = True

            if (
                not call.prestataire
                or call.prestataire.lower() == "prestataire"
                or call.prestataire.strip() == ""
            ):
                if prest_excel:
                    call.prestataire = prest_excel
                    needs_update = True

            if needs_update:
                call.save(update_fields=["beneficiaire", "prestataire"])
                updated_count += 1

    print(f"Successfully updated {updated_count} AppelFormateur records.")


if __name__ == "__main__":
    run()

import sys

import openpyxl

sys.stdout.reconfigure(encoding="utf-8")
wb = openpyxl.load_workbook(
    r"docs\data\network_excel_cache\network-fichier-consolide.xlsm", read_only=True, data_only=True
)
sheet = wb["Consolidation"]
rows = sheet.iter_rows(min_row=2, values_only=True)
count = 0
for r in rows:
    if r[24]:
        print(
            f"Nom Apprenant: {r[1]} | Beneficiaire: {r[2]} | TelFormateur: {r[24]} | Code: {r[25]} | Prestataire: {r[9]}"
        )
        count += 1
    if count > 20:
        break

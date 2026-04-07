"""Analyze classes present in Excel source but missing from Django DB."""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "App_PADESCE.settings")
django.setup()

from App_PADESCE.formations.models import Classe
from App_PADESCE.reporting.network_excel import build_padesce_source_index, normalize_network_lookup


def main():
    bundle = build_padesce_source_index()
    db_codes = {normalize_network_lookup(c) for c in Classe.objects.values_list("code", flat=True)}

    source_classes = bundle.get("classes", {})
    source_records = bundle.get("records", {})

    # Count apprenants per class from records
    class_apprenant_counts = {}
    for rec in source_records.values():
        cc = str(rec.get("classe_id") or rec.get("classe_label") or "").strip()
        key = normalize_network_lookup(cc)
        if key:
            class_apprenant_counts[key] = class_apprenant_counts.get(key, 0) + 1

    excel_only = {k: v for k, v in source_classes.items() if k not in db_codes}

    print(f"Classes en DB:                  {len(db_codes)}")
    print(f"Classes dans Excel source:      {len(source_classes)}")
    print(f"Classes Excel-only (pas en DB): {len(excel_only)}")
    print()

    # Show structure of a sample class
    if excel_only:
        sample = list(excel_only.values())[0]
        print("Structure dune classe source Excel:")
        for k in sorted(sample.keys()):
            if not k.startswith("teams"):
                print(f"  {k}: {repr(sample[k])[:80]}")
        print()

    # Show all Excel-only classes
    print("Liste des classes Excel-only:")
    print(f"{'Classe':<10} {'Prestation':<15} {'Prestataire':<35} {'Inscrits':<10}")
    print("-" * 70)
    for key in sorted(excel_only.keys()):
        info = excel_only[key]
        nb = class_apprenant_counts.get(key, 0)
        classe_id = info.get("classe_id", "?")
        prestation_id = info.get("prestation_id", "?")
        prestataire = info.get("prestataire", "?")[:33]
        print(f"{classe_id:<10} {prestation_id:<15} {prestataire:<35} {nb:<10}")

    print()
    total_inscrits_excel_only = sum(class_apprenant_counts.get(k, 0) for k in excel_only.keys())
    print(f"Total inscrits dans classes Excel-only: {total_inscrits_excel_only}")


if __name__ == "__main__":
    main()

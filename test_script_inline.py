from agent_padesceV2.data_loader import build_padesce_source_index
from App_PADESCE.core.models import AppelFormateur, Prestation

print("=" * 80)
print("PRESTA044 - Nombre de formulaires remplis")
print("=" * 80)

# Base de données
print("\n[1] Base de données - Prestations:")
prestations = Prestation.objects.filter(code__iexact="PRESTA044")
print(f"  Trouvé: {prestations.count()}")

# AppelFormateur (formulaires de satisfaction formateurs)
print("\n[2] AppelFormateur (formulaires formateurs):")
appel_formateurs = AppelFormateur.objects.filter(prestation__code__iexact="PRESTA044")
print(f"  Enregistrements: {appel_formateurs.count()}")
for af in appel_formateurs[:10]:
    appel_code = af.appel.code if af.appel else "N/A"
    formateur_name = getattr(af, "formateur", "N/A")
    print(f"    - Appel: {appel_code}, Formateur: {formateur_name}")

# Source Excel
print("\n[3] Source Excel - build_padesce_source_index():")
try:
    source_bundle = build_padesce_source_index(source_key="cutoff")
    print(f"  Total records in source: {len(source_bundle.get('records', []))}")

    matching = [
        r
        for r in source_bundle.get("records", [])
        if r.get("prestataire", "").upper() == "PRESTA044"
        or r.get("beneficiaire", "").upper() == "PRESTA044"
    ]

    print(f"  PRESTA044 records: {len(matching)}")

    # Count filled forms (have at least one question answered)
    filled = []
    for r in matching:
        q1 = r.get("formateur_q1")
        q2 = r.get("formateur_q2")
        q3 = r.get("formateur_q3")

        if any([q1, q2, q3]):
            filled.append(r)

    print(f"  Formulaires remplis: {len(filled)}")
    print("\n  Détails des formulaires remplis:")
    for i, r in enumerate(filled[:5], 1):
        prestataire = r.get("prestataire")
        q1 = r.get("formateur_q1")
        q2 = r.get("formateur_q2")
        q3 = r.get("formateur_q3")
        print(f"    {i}. {prestataire}: Q1={q1}, Q2={q2}, Q3={q3}")

    if len(filled) > 5:
        print(f"    ... et {len(filled) - 5} autres")

except Exception as e:
    print(f"  Erreur: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 80)

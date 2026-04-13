from App_PADESCE.core.models import Appel, AppelFormateur, Prestation
from agent_padesceV2.data_loader import build_padesce_source_index

print("=" * 80)
print("PRESTA044 - Nombre de formulaires remplis")
print("=" * 80)

# Base de données
print("\n[1] Base de données - Prestations:")
prestations = Prestation.objects.filter(code__iexact='PRESTA044')
print(f"  Trouvé: {prestations.count()}")

# AppelFormateur (formulaires de satisfaction formateurs)
print("\n[2] AppelFormateur (formulaires formateurs):")
appel_formateurs = AppelFormateur.objects.filter(prestation__code__iexact='PRESTA044')
print(f"  Enregistrements: {appel_formateurs.count()}")
for af in appel_formateurs[:10]:
    print(f"    - Appel: {af.appel.code if af.appel else 'N/A'}, Formateur: {getattr(af, 'formateur', 'N/A')}")

# Source Excel
print("\n[3] Source Excel - build_padesce_source_index():")
try:
    source_bundle = build_padesce_source_index(source_key="cutoff")
    print(f"  Total records in source: {len(source_bundle.get('records', []))}")
    
    matching = [r for r in source_bundle.get("records", []) 
                if r.get("prestataire", "").upper() == "PRESTA044" 
                or r.get("beneficiaire", "").upper() == "PRESTA044"]
    
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
    print(f"\n  Détails des formulaires remplis:")
    for i, r in enumerate(filled[:5], 1):
        print(f"    {i}. {r.get('prestataire')}: Q1={r.get('formateur_q1')}, Q2={r.get('formateur_q2')}, Q3={r.get('formateur_q3')}")
    
    if len(filled) > 5:
        print(f"    ... et {len(filled) - 5} autres")
        
except Exception as e:
    print(f"  Erreur: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)

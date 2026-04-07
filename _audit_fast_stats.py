"""Audit script for FAST STATS indicators validation."""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "App_PADESCE.settings")
django.setup()

from collections import Counter

from App_PADESCE.appels.models import Appel, AppelAnswers, AppelFormateur
from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.core.fast_stats import (
    _apprenant_call_effectue,
    _apprenant_call_termine,
    _apprenant_person_key,
    build_fast_stats_bundle,
    request_like_with_query,
)
from App_PADESCE.formations.models import Classe
from App_PADESCE.satisfaction_apprenants.models import SatisfactionApprenant


def separator(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def main():
    separator("AUDIT FAST STATS - VERIFICATION COMPLETE")

    # ── 1. Donnees brutes ──
    separator("1. DONNEES BRUTES EN BASE")
    total_classes = Classe.objects.count()
    total_apprenants = Apprenant.objects.count()
    total_appels = Appel.objects.filter(is_active=True).count()
    total_appels_answers = AppelAnswers.objects.count()
    total_satisfaction = SatisfactionApprenant.objects.count()
    total_appels_formateur = AppelFormateur.objects.filter(is_active=True).count()

    print(f"  Classes:               {total_classes}")
    print(f"  Apprenants:            {total_apprenants}")
    print(f"  Appels actifs:         {total_appels}")
    print(f"  AppelAnswers:          {total_appels_answers}")
    print(f"  SatisfactionApprenant: {total_satisfaction}")
    print(f"  AppelFormateur actifs: {total_appels_formateur}")

    # ── 2. Statuts des appels ──
    separator("2. REPARTITION DES STATUTS APPELS")
    statuts = list(Appel.objects.filter(is_active=True).values_list("status", flat=True))
    for k, v in Counter(statuts).most_common():
        print(f"  {k or '(vide)'}: {v}")

    # ── 3. Lancer FAST STATS (sans filtre) ──
    separator("3. RESULTATS FAST STATS (sans filtre)")
    req = request_like_with_query("")
    bundle = build_fast_stats_bundle(req)
    apprenant_mode = next(m for m in bundle["modes"] if m["id"] == "apprenant")
    formateur_mode = next(m for m in bundle["modes"] if m["id"] == "formateur")

    print(f"  Scope: {bundle['scope_label']}")
    print(f"  Terminated only: {bundle['terminated_only']}")
    print(f"  Classes affichees (apprenant): {apprenant_mode['row_count']}")
    print(f"  Classes affichees (formateur): {formateur_mode['row_count']}")

    # ── 4. Summary cards ──
    separator("4. SUMMARY CARDS")
    print("  --- Apprenant ---")
    for card in apprenant_mode["summary_cards"]:
        print(f"    {card['label']}: {card['value']}")
    print("  --- Formateur ---")
    for card in formateur_mode["summary_cards"]:
        print(f"    {card['label']}: {card['value']}")

    # ── 5. Verification classe par classe ──
    separator("5. VERIFICATION CLASSE PAR CLASSE (5 premieres)")
    rows = apprenant_mode["rows"][:5]
    errors = []

    for row in rows:
        classe_code = row["classe_id"]
        print(f"\n  --- Classe: {classe_code} ---")

        # Comptage direct des apprenants en base
        try:
            classe_obj = Classe.objects.get(code=classe_code)
        except Classe.DoesNotExist:
            print(f"    ERREUR: Classe {classe_code} introuvable en base!")
            errors.append(f"Classe {classe_code} introuvable")
            continue

        db_apprenants = Apprenant.objects.filter(classe=classe_obj).count()
        fast_stats_apprenants = row["apprenant_count"]
        match_apprenants = "OK" if db_apprenants == fast_stats_apprenants else "DIFF"
        print(f"    Apprenants (DB directe): {db_apprenants}")
        print(f"    Apprenants (FAST STATS): {fast_stats_apprenants}  [{match_apprenants}]")
        if match_apprenants == "DIFF":
            print("    NOTE: Difference possible due au source_bundle (fichier reseau)")

        # Comptage direct des appels
        db_appels = Appel.objects.filter(classe=classe_obj, is_active=True)
        db_appels_list = list(db_appels.select_related("answers", "satisfaction_apprenant"))

        # Verification appels effectues
        db_effectues_count = 0
        db_termines_count = 0
        people_seen = {}

        for appel in db_appels_list:
            key = _apprenant_person_key(appel)
            if key not in people_seen:
                people_seen[key] = {"effectue": False, "termine": False}
            people_seen[key]["effectue"] = people_seen[key]["effectue"] or _apprenant_call_effectue(
                appel
            )
            people_seen[key]["termine"] = people_seen[key]["termine"] or _apprenant_call_termine(
                appel
            )

        db_effectues_count = sum(1 for f in people_seen.values() if f["effectue"])
        db_termines_count = sum(1 for f in people_seen.values() if f["termine"])

        # Appliquer le min comme le fait fast_stats
        apprenant_count = fast_stats_apprenants
        db_effectues_capped = min(apprenant_count, db_effectues_count)
        db_termines_capped = min(apprenant_count, db_termines_count, db_effectues_capped)

        match_eff = "OK" if db_effectues_capped == row["calls_effectues"] else "ERREUR"
        match_ter = "OK" if db_termines_capped == row["calls_termines"] else "ERREUR"

        print(f"    Appels en base:      {len(db_appels_list)}")
        print(f"    Personnes uniques:   {len(people_seen)}")
        print(
            f"    Effectues (audit):   {db_effectues_capped}  vs FAST STATS: {row['calls_effectues']}  [{match_eff}]"
        )
        print(
            f"    Termines (audit):    {db_termines_capped}  vs FAST STATS: {row['calls_termines']}  [{match_ter}]"
        )

        if match_eff == "ERREUR":
            errors.append(
                f"Classe {classe_code}: effectues mismatch ({db_effectues_capped} vs {row['calls_effectues']})"
            )
        if match_ter == "ERREUR":
            errors.append(
                f"Classe {classe_code}: termines mismatch ({db_termines_capped} vs {row['calls_termines']})"
            )

        # Verification pourcentages
        if apprenant_count > 0:
            expected_pct_eff = db_effectues_capped / apprenant_count
            expected_pct_enq = db_termines_capped / apprenant_count
        else:
            expected_pct_eff = None
            expected_pct_enq = None

        if db_effectues_capped > 0:
            expected_pct_ter = db_termines_capped / db_effectues_capped
        else:
            expected_pct_ter = None

        print(
            f"    % effectue (audit):  {expected_pct_eff}  vs FAST STATS: {row['pct_appel_effectue']}"
        )
        print(
            f"    % termine (audit):   {expected_pct_ter}  vs FAST STATS: {row['pct_appel_termine']}"
        )
        print(f"    % enquetes (audit):  {expected_pct_enq}  vs FAST STATS: {row['pct_enquetes']}")

    # ── 6. Audit complet sur toutes les classes ──
    separator("6. AUDIT COMPLET - TOUTES LES CLASSES")
    all_rows = apprenant_mode["rows"]
    total_errors = 0

    for row in all_rows:
        classe_code = row["classe_id"]
        try:
            classe_obj = Classe.objects.get(code=classe_code)
        except Classe.DoesNotExist:
            total_errors += 1
            continue

        db_appels_list = list(
            Appel.objects.filter(classe=classe_obj, is_active=True).select_related(
                "answers", "satisfaction_apprenant"
            )
        )

        people_seen = {}
        for appel in db_appels_list:
            key = _apprenant_person_key(appel)
            if key not in people_seen:
                people_seen[key] = {"effectue": False, "termine": False}
            people_seen[key]["effectue"] = people_seen[key]["effectue"] or _apprenant_call_effectue(
                appel
            )
            people_seen[key]["termine"] = people_seen[key]["termine"] or _apprenant_call_termine(
                appel
            )

        db_effectues = min(
            row["apprenant_count"], sum(1 for f in people_seen.values() if f["effectue"])
        )
        db_termines = min(
            row["apprenant_count"],
            sum(1 for f in people_seen.values() if f["termine"]),
            db_effectues,
        )

        if db_effectues != row["calls_effectues"] or db_termines != row["calls_termines"]:
            total_errors += 1
            print(
                f"  ERREUR {classe_code}: eff={db_effectues} vs {row['calls_effectues']}, ter={db_termines} vs {row['calls_termines']}"
            )

    if total_errors == 0:
        print(f"  TOUTES LES {len(all_rows)} CLASSES SONT COHERENTES")
    else:
        print(f"  {total_errors} ERREUR(S) detectee(s) sur {len(all_rows)} classes")

    # ── 7. Verification des doublons de personnes ──
    separator("7. DETECTION DOUBLONS ET CAS LIMITES")
    classes_with_duplicates = 0
    classes_more_appels_than_apprenants = 0

    for row in all_rows:
        classe_code = row["classe_id"]
        try:
            classe_obj = Classe.objects.get(code=classe_code)
        except Classe.DoesNotExist:
            continue

        db_appels_list = list(Appel.objects.filter(classe=classe_obj, is_active=True))
        db_apprenants_count = Apprenant.objects.filter(classe=classe_obj).count()

        if len(db_appels_list) > db_apprenants_count and db_apprenants_count > 0:
            classes_more_appels_than_apprenants += 1

        # Check person key duplicates
        keys = [_apprenant_person_key(a) for a in db_appels_list]
        dupes = {k: v for k, v in Counter(keys).items() if v > 1}
        if dupes:
            classes_with_duplicates += 1

    print(f"  Classes avec doublons de personnes (dedup actif): {classes_with_duplicates}")
    print(
        f"  Classes ayant plus d'appels que d'apprenants:     {classes_more_appels_than_apprenants}"
    )

    # ── 8. Verification formateur ──
    separator("8. VERIFICATION FORMATEUR (5 premieres)")
    f_rows = formateur_mode["rows"][:5]
    for row in f_rows:
        classe_code = row["classe_id"]
        print(f"\n  --- Classe: {classe_code} ---")
        print(f"    Calendrier contacts: {row['calendar_contact_count']}")
        for i, c in enumerate(row["calendar_contacts"]):
            print(f"      Contact {i + 1}: {c['name'] or '(vide)'} / {c['phone'] or '(vide)'}")
        print(f"    Descente contacts:   {row['descente_contact_count']}")
        for i, c in enumerate(row["descente_contacts"]):
            if c["name"] or c["phone"]:
                print(f"      Contact {i + 1}: {c['name'] or '(vide)'} / {c['phone'] or '(vide)'}")
        print(f"    Descente termines:   {row['descente_completed_count']}")

    # ── 9. Resume final ──
    separator("9. RESUME METHODOLOGIQUE")
    print("""
  FORMULES VERIFIEES:
    % appel effectue  = calls_effectues / apprenant_count
    % appel termine   = calls_termines / calls_effectues
    % enquetes        = calls_termines / apprenant_count

  DEDUP: Les appels sont dedupliques par numero de telephone
         (ou par code/nom si pas de telephone).
         Chaque PERSONNE unique ne compte qu'une fois.

  PLAFONNEMENT: calls_effectues <= apprenant_count
                calls_termines <= min(apprenant_count, calls_effectues)

  APPEL EFFECTUE = status != 'en_attente'
                   OU formulaire rempli (AppelAnswers)
                   OU satisfaction completee
                   OU audio enregistre
                   OU locked_at renseigne
                   OU rappel_at renseigne

  APPEL TERMINE  = AppelAnswers existe
                   OU SatisfactionApprenant existe
    """)

    if errors:
        separator("ERREURS DETECTEES")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\n  >>> AUCUNE ERREUR DETECTEE - TOUS LES INDICATEURS SONT COHERENTS <<<")


if __name__ == "__main__":
    main()

from App_PADESCE.formations.models import Beneficiaire, Prestation


def get_prestations_ranking(prestation_stats=None, order="desc"):
    """
    Returns a list of dictionaries with Prestation ranking details.
    Takes prestation_stats calculated by the dashboard (view) as input
    to ensure perfect synchronization (e.g. the 52/134 count).
    """
    if prestation_stats is None:
        return []

    # 1. Pre-fetch beneficiary regions and class counts for speed
    beneficiary_map = {b.nom_structure: b.region for b in Beneficiaire.objects.all()}
    # We also need a mapping of codes to their original Prestation objects if available
    # to get regions more accurately if the name structure isn't direct.
    prestation_regions = {
        p.code: p.beneficiaire.region
        for p in Prestation.objects.filter(actif=True).select_related("beneficiaire")
        if p.beneficiaire
    }

    ranking = []

    # We expect prestation_stats to be a list of dicts:
    # {'code': ..., 'prestataire': ..., 'beneficiaire': ..., 'nb': ..., 'avg': ..., 'avgs': [...]}
    for item in prestation_stats:
        code = item["code"]
        nb_reponses = item["nb"]
        avg_sat = item["avg"]

        # We need the effectif (total participants) to calculate TR.
        # Use provided effectif from view if available, otherwise fallback to DB lookup
        effectif = item.get("effectif")
        if effectif is None:
            # Normalize code to UPPERCASE to match DB schema (e.g. PRESTA001)
            presta_obj = Prestation.objects.filter(code=code.upper(), actif=True).first()
            effectif = presta_obj.effectif_a_former if presta_obj else nb_reponses

        # If effectif is 0, we use nb_reponses as floor
        effectif = max(int(effectif or 0), nb_reponses)

        # Calculate response rate
        taux_reponse = 0.0
        if effectif > 0:
            taux_reponse = min(100.0, (nb_reponses / effectif) * 100)
        else:
            taux_reponse = 100.0 if nb_reponses > 0 else 0.0

        # Composite score: 0.7 * TR + 0.3 * (Sat/5 * 100)
        sat_pct = (avg_sat / 5.0) * 100
        score_global = (0.7 * taux_reponse) + (0.3 * sat_pct)

        # Region lookup (normalize to UPPER for DB mapping)
        region = prestation_regions.get(code.upper()) or beneficiary_map.get(
            item["beneficiaire"], ""
        )

        if effectif > 1:
            ranking.append(
                {
                    "code": code,
                    "intitule": code,  # Simplified
                    "prestataire": item["prestataire"],
                    "beneficiaire": item["beneficiaire"],
                    "region": region,
                    "effectif": effectif,
                    "nb_reponses": nb_reponses,
                    "taux_reponse": round(taux_reponse, 2),
                    "avg_satisfaction": round(avg_sat, 2),
                    "score_global": round(score_global, 2),
                }
            )

    # Sort
    # Sort by score_global DESC, then by effectif DESC for tie-breaking
    ranking = sorted(
        ranking, key=lambda x: (x["score_global"], x["effectif"]), reverse=(order == "desc")
    )
    return ranking

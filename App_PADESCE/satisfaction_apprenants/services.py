from App_PADESCE.formations.models import Beneficiaire, Prestation


def _build_prestation_lookup_maps() -> tuple[dict[str, dict[str, object]], dict[str, str]]:
    prestation_lookup: dict[str, dict[str, object]] = {}
    for prestation in Prestation.objects.filter(actif=True).select_related("beneficiaire"):
        prestation_lookup[str(prestation.code or "").strip().upper()] = {
            "effectif": int(prestation.effectif_a_former or 0),
            "region": getattr(getattr(prestation, "beneficiaire", None), "region", "") or "",
        }

    beneficiary_regions = {
        str(item["nom_structure"] or "").strip(): str(item["region"] or "").strip()
        for item in Beneficiaire.objects.values("nom_structure", "region")
    }
    return prestation_lookup, beneficiary_regions


def get_prestations_ranking(prestation_stats=None, order="desc"):
    """
    Returns a list of dictionaries with Prestation ranking details.
    Takes prestation_stats calculated by the dashboard (view) as input
    to ensure perfect synchronization (e.g. the 52/134 count).
    """
    if prestation_stats is None:
        return []

    prestation_lookup, beneficiary_map = _build_prestation_lookup_maps()

    ranking = []

    # We expect prestation_stats to be a list of dicts:
    # {'code': ..., 'prestataire': ..., 'beneficiaire': ..., 'nb': ..., 'avg': ..., 'avgs': [...]}
    for item in prestation_stats:
        code = str(item.get("code") or "").strip()
        lookup_key = code.upper()
        prestation_data = prestation_lookup.get(lookup_key, {})
        nb_reponses = int(item.get("nb") or 0)
        avg_sat = float(item.get("avg") or 0.0)
        beneficiaire = str(item.get("beneficiaire") or "").strip()

        # We need the effectif (total participants) to calculate TR.
        # Use provided effectif from view if available, otherwise fallback to DB lookup
        effectif = item.get("effectif")
        if effectif is None:
            effectif = prestation_data.get("effectif", nb_reponses)

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

        region = str(prestation_data.get("region") or beneficiary_map.get(beneficiaire, ""))

        if effectif > 1:
            ranking.append(
                {
                    "code": code,
                    "intitule": code,  # Simplified
                    "prestataire": item.get("prestataire", ""),
                    "beneficiaire": beneficiaire,
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

"""Evaluation multicritere du prestataire — Faible / Moyen / Excellent."""

from .cameroon_context import REGIONS_CAMEROUN


CRITERIA = {
    "completude_donnees": {
        "poids": 0.15,
        "description": "Qualité et complétude des données fournies",
        "seuils": {"excellent": 80, "moyen": 50},
    },
    "volume_apprenants": {
        "poids": 0.12,
        "description": "Nombre d'apprenants formés",
        "seuils": {"excellent": 30, "moyen": 15},
    },
    "diversite_formations": {
        "poids": 0.12,
        "description": "Nombre et diversité des formations dispensées",
        "seuils": {"excellent": 5, "moyen": 2},
    },
    "pertinence_sectorielle": {
        "poids": 0.13,
        "description": "Adéquation des formations aux vocations économiques locales",
        "seuils": {},
    },
    "parite_genre": {
        "poids": 0.10,
        "description": "Équilibre hommes/femmes parmi les apprenants",
        "seuils": {"excellent": 40, "moyen": 25},
    },
    "couverture_geographique": {
        "poids": 0.10,
        "description": "Nombre de lieux de formation couverts",
        "seuils": {"excellent": 3, "moyen": 2},
    },
    "adaptation_contexte": {
        "poids": 0.15,
        "description": "Prise en compte des contraintes locales",
        "seuils": {},
    },
    "planification": {
        "poids": 0.15,
        "description": "Qualité de la planification (calendrier, séances)",
        "seuils": {"excellent": 5, "moyen": 3},
    },
}


def evaluate_provider(analysis: dict, extra_answers: dict | None = None) -> dict:
    """Evalue le prestataire et retourne la categorie + scores detailles."""
    scores = {}

    # 1. Completude
    scores["completude_donnees"] = {
        "score": min(100, analysis["score_completude"]),
        "detail": f"Score de complétude : {analysis['score_completude']}%",
    }

    # 2. Volume apprenants
    nb = analysis["nb_apprenants"]
    s = min(100, nb / 30 * 100) if nb > 0 else 0
    scores["volume_apprenants"] = {
        "score": round(s, 1),
        "detail": f"{nb} apprenants détectés",
    }

    # 3. Diversite formations
    nf = analysis["nb_formations"]
    s = min(100, nf / 5 * 100) if nf > 0 else 0
    scores["diversite_formations"] = {
        "score": round(s, 1),
        "detail": f"{nf} formations identifiées : {', '.join(analysis['formations_list'][:5])}",
    }

    # 3b. Pertinence sectorielle
    geo_contexts = analysis.get("contexte_geo", [])
    formations = [f.lower() for f in analysis.get("formations_list", [])]
    if geo_contexts and formations:
        recommended = set()
        for ctx in geo_contexts:
            region_name = ctx.get("region", ctx.get("nom", ""))
            reg_data = REGIONS_CAMEROUN.get(region_name, {})
            for r in reg_data.get("formations_recommandees", []):
                recommended.add(r.lower())
        if recommended:
            matches = sum(1 for f in formations if any(r in f for r in recommended))
            s = min(100, matches / max(1, len(formations)) * 100)
            scores["pertinence_sectorielle"] = {
                "score": round(s, 1),
                "detail": f"{matches}/{len(formations)} formations alignées avec les vocations locales ({', '.join(list(recommended)[:4])})",
            }
        else:
            scores["pertinence_sectorielle"] = {"score": 50, "detail": "Vocations locales non identifiées"}
    else:
        scores["pertinence_sectorielle"] = {"score": 50, "detail": "Données insuffisantes pour évaluer"}

    # 4. Parite genre
    nb_f = analysis["genre_distribution"].get("F", 0)
    nb_m = analysis["genre_distribution"].get("M", 0)
    total_g = nb_f + nb_m
    if total_g > 0:
        pct_f = nb_f / total_g * 100
        s = min(100, pct_f / 50 * 100)
        scores["parite_genre"] = {
            "score": round(s, 1),
            "detail": f"{pct_f:.0f}% femmes ({nb_f}F / {nb_m}M)",
        }
    else:
        scores["parite_genre"] = {"score": 0, "detail": "Données de genre non disponibles"}

    # 5. Couverture geographique
    nv = len(analysis["villes"])
    s = min(100, nv / 3 * 100) if nv > 0 else 0
    scores["couverture_geographique"] = {
        "score": round(s, 1),
        "detail": f"{nv} lieu(x) de formation : {', '.join(analysis['villes'][:5])}",
    }

    # 6. Adaptation contexte
    geo_contexts = analysis.get("contexte_geo", [])
    if geo_contexts:
        avg_difficulty = sum(c.get("score_difficulte", 0.5) for c in geo_contexts) / len(geo_contexts)
        # Higher difficulty = bonus for operating there
        s = min(100, 50 + avg_difficulty * 50)
        defis = []
        for c in geo_contexts:
            defis.extend(c.get("defis", [])[:2])
        scores["adaptation_contexte"] = {
            "score": round(s, 1),
            "detail": f"Zones à difficulté moyenne {avg_difficulty:.0%}. Défis : {'; '.join(defis[:3])}",
        }
    else:
        scores["adaptation_contexte"] = {"score": 50, "detail": "Contexte géographique non identifié"}

    # 7. Planification
    ns = analysis.get("nb_seances", 0)
    s = min(100, ns / 5 * 100) if ns > 0 else 0
    scores["planification"] = {
        "score": round(s, 1),
        "detail": f"{ns} séance(s) planifiée(s)",
    }

    # Extra answers bonus
    if extra_answers:
        for key, answer in extra_answers.items():
            if key == "satisfaction" and answer:
                try:
                    sat = float(answer)
                    if sat >= 4:
                        scores["completude_donnees"]["score"] = min(100, scores["completude_donnees"]["score"] + 10)
                except ValueError:
                    pass

    # Weighted total
    total_weighted = 0
    for crit_key, crit_def in CRITERIA.items():
        crit_score = scores.get(crit_key, {}).get("score", 0)
        total_weighted += crit_score * crit_def["poids"]

    total_pct = round(total_weighted, 1)

    if total_pct >= 70:
        category = "Excellent"
    elif total_pct >= 45:
        category = "Moyen"
    else:
        category = "Faible"

    # Justifications
    justifications = []
    for crit_key, crit_def in CRITERIA.items():
        s = scores.get(crit_key, {})
        score_val = s.get("score", 0)
        if score_val >= 70:
            level = "fort"
        elif score_val >= 40:
            level = "acceptable"
        else:
            level = "insuffisant"
        justifications.append({
            "critere": crit_def["description"],
            "score": score_val,
            "poids": crit_def["poids"],
            "niveau": level,
            "detail": s.get("detail", ""),
        })

    return {
        "categorie": category,
        "score_global": total_pct,
        "scores_detailles": scores,
        "justifications": justifications,
        "alertes": analysis.get("alertes", []),
    }


def get_followup_questions(analysis: dict) -> list[dict]:
    """Questions supplementaires a poser a l'utilisateur pour mieux evaluer."""
    questions = []

    if analysis["nb_formations"] == 0:
        questions.append({
            "id": "formations",
            "question": "Quelles formations ont été dispensées par ce prestataire ?",
            "type": "text",
        })

    if not analysis["genre_distribution"]:
        questions.append({
            "id": "genre_ratio",
            "question": "Quelle est la répartition hommes/femmes parmi les apprenants ?",
            "type": "text",
        })

    if analysis["score_completude"] < 60:
        questions.append({
            "id": "completude",
            "question": "Disposez-vous de données complémentaires sur les apprenants (âge, diplôme, etc.) ?",
            "type": "choice",
            "options": ["Oui, je peux fournir un fichier complet", "Non, ces données ne sont pas disponibles"],
        })

    questions.append({
        "id": "satisfaction",
        "question": "Sur une échelle de 1 à 5, quel est le niveau de satisfaction global des apprenants ?",
        "type": "scale",
        "min": 1,
        "max": 5,
    })

    questions.append({
        "id": "incidents",
        "question": "Y a-t-il eu des incidents ou difficultés notables lors des formations ?",
        "type": "text",
    })

    if any(c.get("score_difficulte", 0) >= 0.7 for c in analysis.get("contexte_geo", [])):
        questions.append({
            "id": "adaptation_locale",
            "question": "Quelles mesures le prestataire a-t-il prises pour s'adapter aux conditions locales difficiles ?",
            "type": "text",
        })

    return questions


def generate_investment_recommendations(analysis: dict, evaluation: dict) -> list[dict]:
    """Recommandations d'investissement pour le PADESCE."""
    recs = []
    cat = evaluation["categorie"]
    score = evaluation["score_global"]

    if cat == "Faible":
        recs.append({
            "type": "alerte",
            "titre": "Risque financier eleve",
            "detail": (
                f"Le prestataire obtient {score}%. Le PADESCE risque de perdre "
                f"son investissement si les formations continuent sans amelioration. "
                f"Recommandation : suspendre le financement et exiger un plan correctif."
            ),
        })
    elif cat == "Moyen":
        recs.append({
            "type": "attention",
            "titre": "Investissement sous surveillance",
            "detail": (
                f"Score de {score}% : le prestataire repond partiellement aux attentes. "
                f"Recommandation : maintenir le financement avec un suivi renforce "
                f"et des objectifs intermediaires mesurables."
            ),
        })
    else:
        recs.append({
            "type": "positif",
            "titre": "Investissement performant",
            "detail": (
                f"Score de {score}% : le prestataire livre des resultats solides. "
                f"Recommandation : renouveler le partenariat et envisager une "
                f"extension geographique ou sectorielle."
            ),
        })

    # Zones a risque
    for ctx in analysis.get("contexte_geo", []):
        d = ctx.get("score_difficulte", 0)
        nom = ctx.get("nom", "Zone")
        if d >= 0.8:
            recs.append({
                "type": "zone_risque",
                "titre": f"Zone a risque : {nom}",
                "detail": (
                    f"Difficulte {d:.0%}. Defis : {'; '.join(ctx.get('defis', [])[:2])}. "
                    f"Le PADESCE doit prevoir un budget supplementaire de contingence "
                    f"et des mecanismes adaptes (formation mobile, generateurs, etc.)."
                ),
            })

    # Pertinence sectorielle (deduplicate by region)
    geo_contexts = analysis.get("contexte_geo", [])
    seen_regions = set()
    for ctx in geo_contexts:
        region_name = ctx.get("region", ctx.get("nom", ""))
        if region_name in seen_regions:
            continue
        seen_regions.add(region_name)
        reg_data = REGIONS_CAMEROUN.get(region_name, {})
        vocations = reg_data.get("vocations_economiques", [])
        recommandees = reg_data.get("formations_recommandees", [])
        if vocations:
            recs.append({
                "type": "sectoriel",
                "titre": f"Orientation sectorielle — {region_name}",
                "detail": (
                    f"Vocations economiques locales : {', '.join(vocations[:4])}. "
                    f"Formations recommandees : {', '.join(recommandees[:4])}. "
                    f"Le PADESCE devrait privilegier ces secteurs pour maximiser "
                    f"le retour sur investissement et l'insertion des beneficiaires."
                ),
            })

    # Completude
    if analysis["score_completude"] < 50:
        recs.append({
            "type": "donnees",
            "titre": "Perte d'information = perte d'argent",
            "detail": (
                f"Completude de {analysis['score_completude']}%. Sans donnees fiables, "
                f"le PADESCE ne peut pas evaluer le retour sur investissement. "
                f"Exiger un rapport de donnees complet avant tout prochain versement."
            ),
        })

    return recs

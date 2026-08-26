"""Analyse des donnees de prestataire pour le reporting."""

import pandas as pd
import numpy as np
from pathlib import Path
from .cameroon_context import (
    get_region_context,
    get_city_context,
    identify_region_from_city,
    REGIONS_CAMEROUN,
)


def load_excel_data(file_path: str) -> dict:
    """Charge et nettoie les donnees d'un fichier Excel de prestataire."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Fichier non trouvé : {file_path}")

    xls = pd.ExcelFile(path)
    result = {"sheets": {}, "file_name": path.name}

    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name)
        df = df.dropna(how="all")
        df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
        if not df.empty:
            result["sheets"][sheet_name] = df

    return result


def analyze_provider_data(data: dict) -> dict:
    """Analyse complete des donnees du prestataire."""
    analysis = {
        "prestataire": None,
        "nb_apprenants": 0,
        "nb_formations": 0,
        "nb_seances": 0,
        "villes": [],
        "regions": [],
        "genre_distribution": {},
        "diplome_distribution": {},
        "experience_moyenne": None,
        "completude_donnees": {},
        "formations_list": [],
        "contexte_geo": [],
        "beneficiaires": [],
        "score_completude": 0.0,
        "alertes": [],
    }

    for sheet_name, df in data["sheets"].items():
        cols_lower = {c: c.lower() for c in df.columns}

        # Detect learners sheet
        if any("nom" in v or "name" in v for v in cols_lower.values()):
            _analyze_learners(df, analysis)

        # Detect calendar sheet
        if any("date" in v or "séance" in v or "seance" in v for v in cols_lower.values()):
            _analyze_calendar(df, analysis)

    _compute_completude(analysis)
    _compute_geo_context(analysis)
    _generate_alerts(analysis)

    return analysis


def _find_col(df, keywords):
    """Find column matching any keyword."""
    for col in df.columns:
        cl = col.lower()
        for kw in keywords:
            if kw in cl:
                return col
    return None


def _analyze_learners(df: pd.DataFrame, analysis: dict):
    col_name = _find_col(df, ["nom", "name"])
    col_provider = _find_col(df, ["prestataire", "provider"])
    col_gender = _find_col(df, ["genre", "gender", "sexe"])
    col_diploma = _find_col(df, ["diplôme", "diplome", "diploma"])
    col_exp = _find_col(df, ["expérience", "experience", "exp"])
    col_city = _find_col(df, ["ville", "city", "résidence", "residence"])
    col_region = _find_col(df, ["région", "region"])
    col_training_city = _find_col(df, ["ville de la formation", "training city"])
    col_beneficiary = _find_col(df, ["bénéficiaire", "beneficiary", "beneficiaire"])
    col_formation = _find_col(df, ["formation sollicitée", "requested training", "formation dispensée"])

    if col_name:
        valid = df[col_name].dropna()
        analysis["nb_apprenants"] = len(valid)

    if col_provider:
        providers = df[col_provider].dropna().unique()
        if len(providers) > 0:
            analysis["prestataire"] = providers[0]

    if col_gender:
        dist = df[col_gender].dropna().value_counts().to_dict()
        analysis["genre_distribution"] = {str(k): int(v) for k, v in dist.items()}

    if col_diploma:
        dist = df[col_diploma].dropna().value_counts().to_dict()
        analysis["diplome_distribution"] = {str(k): int(v) for k, v in dist.items()}

    if col_exp:
        vals = pd.to_numeric(df[col_exp], errors="coerce").dropna()
        if len(vals) > 0:
            analysis["experience_moyenne"] = round(float(vals.mean()), 1)

    cities = set()
    if col_city:
        cities.update(df[col_city].dropna().astype(str).unique())
    if col_training_city:
        cities.update(df[col_training_city].dropna().astype(str).unique())
    analysis["villes"] = sorted(cities)

    if col_region:
        analysis["regions"] = sorted(df[col_region].dropna().astype(str).unique())

    if col_beneficiary:
        analysis["beneficiaires"] = sorted(df[col_beneficiary].dropna().astype(str).unique())

    if col_formation:
        formations = df[col_formation].dropna().astype(str).unique()
        analysis["formations_list"] = sorted(set(f.strip() for f in formations if f.strip()))

    # Completude par colonne
    for col in df.columns:
        non_null = df[col].notna().sum()
        total = len(df)
        analysis["completude_donnees"][col] = round(non_null / total * 100, 1) if total > 0 else 0


def _analyze_calendar(df: pd.DataFrame, analysis: dict):
    col_formation = _find_col(df, ["formation", "training"])
    col_date = _find_col(df, ["date"])
    col_lieu = _find_col(df, ["lieu", "location", "venue"])

    if col_formation:
        formations = df[col_formation].dropna().astype(str).unique()
        for f in formations:
            f = f.strip().lstrip("- ")
            if f and f not in analysis["formations_list"]:
                analysis["formations_list"].append(f)
        analysis["nb_formations"] = len(analysis["formations_list"])

    if col_date:
        analysis["nb_seances"] = int(df[col_date].notna().sum())

    if col_lieu:
        lieux = df[col_lieu].dropna().astype(str).unique()
        for l in lieux:
            if l.strip() and l.strip() not in analysis["villes"]:
                analysis["villes"].append(l.strip())


def _compute_completude(analysis: dict):
    if not analysis["completude_donnees"]:
        analysis["score_completude"] = 0.0
        return
    scores = list(analysis["completude_donnees"].values())
    analysis["score_completude"] = round(np.mean(scores), 1)


def _compute_geo_context(analysis: dict):
    contexts = []
    regions_found = set()

    for ville in analysis["villes"]:
        city_ctx = get_city_context(ville)
        if city_ctx:
            contexts.append(city_ctx)
            regions_found.add(city_ctx["region"])

    for region in analysis.get("regions", []):
        if region not in regions_found:
            reg_ctx = get_region_context(region)
            if reg_ctx:
                contexts.append({"type": "region", **reg_ctx})

    # Infer regions from cities if no explicit region
    if not analysis["regions"]:
        for ville in analysis["villes"]:
            reg = identify_region_from_city(ville)
            if reg and reg not in analysis["regions"]:
                analysis["regions"].append(reg)

    analysis["contexte_geo"] = contexts


def _generate_alerts(analysis: dict):
    alerts = []

    if analysis["score_completude"] < 50:
        alerts.append("CRITIQUE : Complétude des données inférieure à 50%")
    elif analysis["score_completude"] < 70:
        alerts.append("ATTENTION : Complétude des données inférieure à 70%")

    if analysis["nb_apprenants"] == 0:
        alerts.append("CRITIQUE : Aucun apprenant détecté")

    if analysis["nb_formations"] == 0:
        alerts.append("ATTENTION : Aucune formation identifiée dans les données")

    for ctx in analysis["contexte_geo"]:
        score = ctx.get("score_difficulte", 0)
        if score >= 0.8:
            name = ctx.get("nom", ctx.get("region", "zone"))
            alerts.append(f"ZONE DIFFICILE : {name} — conditions socio-économiques défavorables")

    nb_f = analysis["genre_distribution"].get("F", 0)
    nb_m = analysis["genre_distribution"].get("M", 0)
    total = nb_f + nb_m
    if total > 0:
        pct_f = nb_f / total * 100
        if pct_f < 30:
            alerts.append(f"GENRE : Faible représentation féminine ({pct_f:.0f}%)")

    analysis["alertes"] = alerts

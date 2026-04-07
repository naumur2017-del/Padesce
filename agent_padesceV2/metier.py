# agent_padesce/metier.py
"""Fonctions métier : extraction d'infos et filtrage de classes."""

import pandas as pd


def extraire_infos(df: pd.DataFrame, valeur: str) -> tuple[pd.DataFrame, list]:
    """
    Détecte automatiquement la colonne de recherche et retourne les infos clés.
    """
    colonnes_possibles = [
        "prestation_id",
        "prestataire",
        "bénéficaire",
        "prestataire_simplifié",
        "bénéficiaire_simplifié",
    ]

    colonne_trouvee = None
    for col in colonnes_possibles:
        if col in df.columns and valeur in df[col].astype(str).values:
            colonne_trouvee = col
            break

    if colonne_trouvee is None:
        raise ValueError(
            f"La valeur '{valeur}' n'a été trouvée dans aucune des colonnes {colonnes_possibles}"
        )

    subset = df[df[colonne_trouvee].astype(str) == str(valeur)].copy()

    colonnes_cibles = [
        "statut",
        "prestation_id",
        "prestataire",
        "bénéficaire",
        "fénetre",
        "objectifs_padesce_t",
        "apprenants_inscrits_t",
        "formation",
        "taux__de_personnes_formées_nan",
        "taux__de_présence_moyen__nan",
        "taux_de_satisfaction_formateurs_nan",
        "taux_de_satisfaction_appreannts_nan",
        "apprenants_suivis_ayant_assisté_au_moins_une_fois_à_la_formation_t",
    ]

    colonnes_existantes = [c for c in colonnes_cibles if c in subset.columns]

    def calcul_taux(row):
        try:
            inscrits = int(row.get("apprenants_inscrits_t", 0))
            objectif = int(row.get("objectifs_padesce_t", 0))
            if objectif > 0:
                return round(inscrits / objectif, 3)
            return "N/D"
        except Exception:
            return "N/D"

    subset["taux_inscription_calcule"] = subset.apply(calcul_taux, axis=1).tolist()

    return (
        subset[colonnes_existantes + ["taux_inscription_calcule"]],
        subset["prestation_id"].tolist(),
    )


def filtrer_classes(classe_df: pd.DataFrame, liste_prestations: list) -> pd.DataFrame:
    """
    Filtre le DataFrame 'classe' en fonction d'une liste de prestation_id.
    """
    subset = classe_df[
        classe_df["Prestation ID"].astype(str).isin([str(x) for x in liste_prestations])
    ]

    colonnes_cibles = [
        "Prestation ID",
        "Cohorte",
        "Nb personnes",
        "FORMATION",
        classe_df.columns[0],
    ]
    colonnes_existantes = [c for c in colonnes_cibles if c in subset.columns]

    df = subset[colonnes_existantes].copy()

    rename_map = {"FORMATION": "villes"}
    if classe_df.columns[0] in df.columns:
        rename_map[classe_df.columns[0]] = "classe"

    df = df.rename(columns=rename_map)
    return df

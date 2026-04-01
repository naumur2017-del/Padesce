# agent_padesce/data_loader.py
"""Chargement et enregistrement des données."""

import pandas as pd

from .config import set_dataframes
from .schema import build_modalities_cache, build_schema_cache


def load_data(path: str = "Decompte et facturation.xlsm") -> dict[str, pd.DataFrame]:
    """Charge les deux feuilles Excel et retourne un dict de DataFrames."""
    
    # Charger la feuille Classes
    classe = pd.read_excel(path, sheet_name="Classes", header=0, engine="openpyxl")
    classe = classe.query("Cohorte != 0")
    classe = classe.loc[:, ~classe.columns.str.startswith("Column")]

    # Charger la feuille Decompte Global
    decompte = pd.read_excel(path, sheet_name="Decompte Global", header=0, engine="openpyxl")
    first_row = decompte.iloc[0]
    new_cols = []
    for col in decompte.columns:
        col_str = str(col)
        new_cols.append(
            str(first_row[col]) if col_str.startswith("Unnamed") else f"{col_str}_{first_row[col]}"
        )
    decompte.columns = new_cols
    decompte = decompte.iloc[1:].reset_index(drop=True)
    decompte.columns = (
        decompte.columns.str.strip().str.replace(" ", "_").str.replace("'", "").str.lower()
    )
    decompte = decompte.query("`prestation_id`.notna()")
    decompte = decompte.loc[:, ~decompte.columns.str.startswith("column")]

    # Corriger les colonnes f et t
    cols = list(decompte.columns)
    new_cols = []
    for i, col in enumerate(cols):
        if col in ["f", "t"]:
            prev = new_cols[-1]
            base = prev.rsplit("_", 1)[0] if "_" in prev else prev
            new_cols.append(f"{base}_{col}")
        else:
            new_cols.append(col)
    decompte.columns = new_cols
    
    return {"classe": classe, "decompte": decompte}


def register_dataframes(dfs: dict[str, pd.DataFrame]) -> None:
    """Enregistre les DataFrames et construit les caches."""
    set_dataframes(dfs)
    build_modalities_cache()
    build_schema_cache()

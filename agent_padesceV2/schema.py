# agent_padesce/schema.py
"""Construction et gestion du schéma des données."""

import pandas as pd

from .config import (
    get_dataframes,
    get_schema_cache,
    set_modalities_cache,
    set_schema_cache,
    safe_series,
)


def build_modalities_cache() -> None:
    """Construit le cache des modalités pour la correction orthographique."""
    cache = {}
    dataframes = get_dataframes()
    
    for bdd_name in ["classe", "decompte"]:
        df = dataframes.get(bdd_name)
        if df is None:
            continue
        for col in df.columns:
            s = safe_series(df, col)
            if not pd.api.types.is_numeric_dtype(s):
                uniques = s.dropna().astype(str).unique()
                if len(uniques) <= 500:
                    key = f"{bdd_name}.{col}"
                    cache[key] = list(uniques)
    
    set_modalities_cache(cache)


def build_schema_cache() -> None:
    """Construit un schéma détaillé pour le LLM avec colonnes et valeurs possibles."""
    parts = []
    dataframes = get_dataframes()
    
    for bdd_name in ["decompte", "classe"]:
        df = dataframes.get(bdd_name)
        if df is None:
            continue
        
        parts.append(f"\n{'='*60}")
        parts.append(f"DataFrame '{bdd_name}' : {df.shape[0]} lignes, {df.shape[1]} colonnes")
        parts.append('='*60)
        
        for col in df.columns:
            s = safe_series(df, col)
            dtype_str = str(s.dtype)
            non_null = s.notna().sum()
            
            if pd.api.types.is_numeric_dtype(s):
                parts.append(f"  • {col} [NUMÉRIQUE {dtype_str}] : {non_null} valeurs, min={s.min()}, max={s.max()}")
            else:
                uniques = s.dropna().astype(str).unique()
                n_unique = len(uniques)
                if n_unique <= 15:
                    vals = ", ".join(f'"{v}"' for v in sorted(uniques)[:15])
                    parts.append(f"  • {col} [TEXTE] : {n_unique} valeurs uniques → {vals}")
                else:
                    sample = ", ".join(f'"{v}"' for v in list(uniques)[:8])
                    parts.append(f"  • {col} [TEXTE] : {n_unique} valeurs uniques → {sample} ...")
    
    set_schema_cache("\n".join(parts))


def get_schema() -> str:
    """Retourne le schéma détaillé des BDD."""
    return get_schema_cache()

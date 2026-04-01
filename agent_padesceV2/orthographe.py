# agent_padesce/orthographe.py
"""Correction orthographique et détection d'entités."""

import re
from difflib import SequenceMatcher

from .config import get_modalities_cache


def _similarity(a: str, b: str) -> float:
    """Calcule la similarité entre deux chaînes."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def corriger_orthographe(valeur: str, seuil: float = 0.75) -> tuple[str, str | None, float]:
    """
    Corrige une valeur en la comparant aux modalités connues.
    Retourne : (valeur_corrigée, colonne_source, score)
    """
    modalities_cache = get_modalities_cache()
    valeur_clean = valeur.strip()
    valeur_lower = valeur_clean.lower()
    
    # Correspondance exacte d'abord
    for key, modalities in modalities_cache.items():
        for mod in modalities:
            if mod.lower() == valeur_lower:
                return mod, key, 1.0
    
    # Fuzzy matching
    best_match, best_score, best_col = None, 0.0, None
    for key, modalities in modalities_cache.items():
        for mod in modalities:
            score = _similarity(valeur_clean, mod)
            if score > best_score and score >= seuil:
                best_score = score
                best_match = mod
                best_col = key
    
    if best_match:
        return best_match, best_col, best_score
    return valeur_clean, None, 0.0


def trouver_entite(texte: str) -> dict:
    """
    Trouve les entités (prestataire, bénéficiaire, prestation_id, fenêtre, statut) 
    mentionnées dans un texte.
    """
    entites = {
        "prestataire": None,
        "beneficiaire": None,
        "prestation_id": None,
        "fenetre": None,
        "statut": None,
    }
    
    mots = re.findall(
        r'[A-ZÀ-Ÿ][A-Za-zÀ-ÿ\-]*(?:\s+[A-ZÀ-Ÿ][A-Za-zÀ-ÿ\-]*)*|[A-Z]{2,}[\dA-Z]*|\b[Ff]\d+\b',
        texte
    )
    
    for mot in mots:
        mot_clean = mot.strip()
        if len(mot_clean) < 2:
            continue
        
        corrige, col_source, score = corriger_orthographe(mot_clean, seuil=0.7)
        
        if col_source and score >= 0.7:
            if "prestataire" in col_source:
                entites["prestataire"] = corrige
            elif "bénéficaire" in col_source or "beneficiaire" in col_source:
                entites["beneficiaire"] = corrige
            elif "prestation_id" in col_source or "Prestation ID" in col_source:
                entites["prestation_id"] = corrige
            elif "fénetre" in col_source or "fenetre" in col_source:
                entites["fenetre"] = corrige
            elif "statut" in col_source:
                entites["statut"] = corrige
    
    return {k: v for k, v in entites.items() if v is not None}

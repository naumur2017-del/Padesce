# agent_padesce/config.py
"""Configuration, constantes et registres globaux."""

import os
from typing import Any

import pandas as pd

# ═══════════════════════════════════════════════════════════════
#  RÉPERTOIRES
# ═══════════════════════════════════════════════════════════════

EXPORTS_DIR = "exports"
os.makedirs(EXPORTS_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════════════
#  COULEURS EXCEL
# ═══════════════════════════════════════════════════════════════

PURPLE     = "7030A0"
GREEN_DARK = "7030A0"
GREEN_MED  = "7030A0"
TEAL       = "7030A0"
YELLOW_HDR = "7030A0"
GRAY_LIGHT = "D9D9D9"
WHITE      = "FFFFFF"
BLACK      = "000000"

# ═══════════════════════════════════════════════════════════════
#  CONFIGURATION MÉMOIRE
# ═══════════════════════════════════════════════════════════════

_MEMORY_CONFIG = {
    "enabled": True,
    "max_conversations": 5,  # Nombre de conversations à retenir
}

# ═══════════════════════════════════════════════════════════════
#  REGISTRES GLOBAUX
# ═══════════════════════════════════════════════════════════════

_DATAFRAMES: dict[str, pd.DataFrame] = {}
_MEMORY: list[dict] = []  # Historique des conversations
_INTERMEDIATE: dict[str, Any] = {}
_MODALITIES_CACHE: dict[str, list[str]] = {}
_SCHEMA_CACHE: str = ""


def get_dataframes() -> dict[str, pd.DataFrame]:
    return _DATAFRAMES


def get_df(name: str) -> pd.DataFrame | None:
    return _DATAFRAMES.get(name)


def set_dataframes(dfs: dict[str, pd.DataFrame]) -> None:
    _DATAFRAMES.update(dfs)


def get_memory() -> list[dict]:
    return _MEMORY


def get_intermediate() -> dict[str, Any]:
    return _INTERMEDIATE


def get_modalities_cache() -> dict[str, list[str]]:
    return _MODALITIES_CACHE


def set_modalities_cache(cache: dict[str, list[str]]) -> None:
    global _MODALITIES_CACHE
    _MODALITIES_CACHE = cache


def get_schema_cache() -> str:
    return _SCHEMA_CACHE


def set_schema_cache(schema: str) -> None:
    global _SCHEMA_CACHE
    _SCHEMA_CACHE = schema


def reset_memory() -> None:
    """Réinitialise la mémoire conversationnelle."""
    _MEMORY.clear()
    _INTERMEDIATE.clear()
    print("[Mémoire] Réinitialisée.")


def configure_memory(enabled: bool = True, max_conversations: int = 5) -> None:
    """
    Configure la mémoire de l'agent.
    
    Args:
        enabled: Active/désactive la mémoire
        max_conversations: Nombre de conversations à retenir (1-20)
    
    Example:
        configure_memory(enabled=True, max_conversations=10)
    """
    _MEMORY_CONFIG["enabled"] = enabled
    _MEMORY_CONFIG["max_conversations"] = max(1, min(20, max_conversations))
    print(f"[Mémoire] Configurée : enabled={enabled}, max_conversations={_MEMORY_CONFIG['max_conversations']}")


def get_memory_config() -> dict:
    """Retourne la configuration actuelle de la mémoire."""
    return _MEMORY_CONFIG.copy()


def get_memory_context() -> str:
    """
    Retourne le contexte mémoire formaté pour le LLM.
    Limite aux K dernières conversations.
    """
    if not _MEMORY_CONFIG["enabled"] or not _MEMORY:
        return ""
    
    max_conv = _MEMORY_CONFIG["max_conversations"]
    recent = _MEMORY[-max_conv * 2:]  # 2 messages par conversation (user + assistant)
    
    if not recent:
        return ""
    
    context_parts = ["HISTORIQUE DES CONVERSATIONS PRÉCÉDENTES :"]
    for msg in recent:
        role = "👤 Utilisateur" if msg["role"] == "user" else "🤖 Assistant"
        content = msg["content"][:300] + "..." if len(msg["content"]) > 300 else msg["content"]
        context_parts.append(f"{role} : {content}")
    
    return "\n".join(context_parts)


def add_to_memory(role: str, content: str) -> None:
    """Ajoute un message à la mémoire."""
    from datetime import datetime
    
    if not _MEMORY_CONFIG["enabled"]:
        return
    
    _MEMORY.append({
        "role": role,
        "content": content,
        "ts": datetime.now().isoformat()
    })
    
    # Limiter la taille de la mémoire
    max_messages = _MEMORY_CONFIG["max_conversations"] * 2
    while len(_MEMORY) > max_messages:
        _MEMORY.pop(0)


def safe_series(df: pd.DataFrame, col: str) -> pd.Series:
    """Extrait une série de manière sécurisée."""
    raw = df.loc[:, col]
    if isinstance(raw, pd.DataFrame):
        raw = raw.iloc[:, 0]
    return raw.copy()

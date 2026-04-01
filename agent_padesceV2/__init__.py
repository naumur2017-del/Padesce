# agent_padesce/__init__.py
"""
Agent PADESCE - Analyse des données de formation avec LangGraph.

Usage en notebook:
    from agent_padesce import *
    
    # Configuration de la mémoire (optionnel)
    configure_memory(enabled=True, max_conversations=5)
    
    # Chargement des données
    dfs = load_data("Decompte et facturation.xlsm")
    register_dataframes(dfs)
    
    # Visualisation du graphe
    visualize_graph()
    
    # Utilisation de l'agent
    result = run_agent("Combien de prestataires ?")
    print(result["reponse"])
"""

# Configuration
from .config import (
    EXPORTS_DIR,
    reset_memory,
    configure_memory,
    get_memory_config,
    get_df,
)

# Chargement des données
from .data_loader import (
    load_data,
    register_dataframes,
)

# Schéma
from .schema import (
    get_schema,
)

# Orthographe
from .orthographe import (
    corriger_orthographe,
    trouver_entite,
)

# Fonctions métier
from .metier import (
    extraire_infos,
    filtrer_classes,
)

# Génération Excel
from .excel_generator import (
    generer_rapport_excel,
)

# Pipelines
from .pipelines import (
    pipeline_fiche,
    pipeline_code,
    generer_code,
    executer_code,
)

# Graphe
from .graph import (
    build_graph,
    AgentState,
)

# Visualisation
from .visualize import (
    visualize_graph,
)

# Agent
from .agent import (
    run_agent,
    get_generated_file,
    list_generated_files,
)

__all__ = [
    # Config
    "EXPORTS_DIR",
    "reset_memory",
    "configure_memory",
    "get_memory_config",
    "get_df",
    # Data
    "load_data",
    "register_dataframes",
    # Schema
    "get_schema",
    # Orthographe
    "corriger_orthographe",
    "trouver_entite",
    # Métier
    "extraire_infos",
    "filtrer_classes",
    # Excel
    "generer_rapport_excel",
    # Pipelines
    "pipeline_fiche",
    "pipeline_code",
    "generer_code",
    "executer_code",
    # Graphe
    "build_graph",
    "AgentState",
    # Visualisation
    "visualize_graph",
    # Agent
    "run_agent",
    "get_generated_file",
    "list_generated_files",
]

__version__ = "5.1.0"

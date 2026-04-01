# agent_padesce/agent.py
"""Fonction d'appel principale de l'agent."""

import json
import os

from langchain_core.messages import HumanMessage

from .graph import build_graph, AgentState
from .config import EXPORTS_DIR


def run_agent(user_prompt: str, verbose: bool = True) -> dict:
    """
    Lance l'agent et retourne la réponse.
    
    Args:
        user_prompt: La question ou demande de l'utilisateur
        verbose: Si True, affiche les étapes intermédiaires
    
    Returns:
        Dict avec 'intention', 'reponse' et optionnellement 'fichier_genere'
    """
    app = build_graph()
    initial_state: AgentState = {
        "messages": [HumanMessage(content=user_prompt)],
        "intent": "",
        "valeur_recherche": "",
        "entites": {},
        "result": {},
        "final_response": {},
    }

    final_state = None

    for step in app.stream(initial_state, stream_mode="values"):
        final_state = step
        if verbose:
            intent = step.get("intent", "")
            if intent:
                route_emoji = {"fiche": "🟢", "excel": "🔵", "question": "🟡", "hors_cadre": "🔴"}.get(intent, "⚪")
                print(f"  {route_emoji} Route : {intent.upper()}")
                entites = step.get("entites", {})
                if entites:
                    print(f"     Entités détectées : {entites}")
            
            result = step.get("result", {})
            if result.get("statut"):
                statut = result.get("statut")
                if statut == "succes":
                    print(f"  ✅ Traitement réussi")
                elif statut == "erreur_execution":
                    print(f"  ❌ Erreur d'exécution")
                elif statut == "non_trouve":
                    print(f"  🔍 Aucun résultat trouvé")
                
                if result.get("fichier"):
                    filename = os.path.basename(result["fichier"])
                    print(f"  📁 Fichier généré : {filename}")
                if result.get("nb_lignes"):
                    print(f"  📊 Données : {result['nb_lignes']} lignes")

    response = final_state.get("final_response", {})
    
    # S'assurer que le chemin du fichier est accessible si généré
    if response.get("fichier_genere"):
        response["fichier"] = response["fichier_genere"]
    
    return response


def get_generated_file(result: dict) -> str | None:
    """
    Retourne le chemin du fichier généré s'il existe.
    
    Args:
        result: Le résultat retourné par run_agent()
    
    Returns:
        Le chemin du fichier ou None
    """
    return result.get("fichier_genere") or result.get("fichier")


def list_generated_files() -> list[str]:
    """
    Liste tous les fichiers générés dans le dossier exports.
    
    Returns:
        Liste des noms de fichiers
    """
    if not os.path.exists(EXPORTS_DIR):
        return []
    return sorted([f for f in os.listdir(EXPORTS_DIR) if f.endswith(('.xlsx', '.png'))])

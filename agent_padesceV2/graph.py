# agent_padesce/graph.py
"""Construction et nœuds du graphe LangGraph."""

import json
from datetime import datetime
from typing import Annotated, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from .config import get_memory, add_to_memory, get_memory_context
from .schema import get_schema
from .orthographe import trouver_entite
from .pipelines import pipeline_fiche, pipeline_code


# ═══════════════════════════════════════════════════════════════
#  ÉTAT DU GRAPHE
# ═══════════════════════════════════════════════════════════════

class AgentState(TypedDict):
    messages:         Annotated[list, add_messages]
    intent:           str          # "fiche" | "excel" | "question" | "hors_cadre"
    valeur_recherche: str
    entites:          dict
    result:           dict
    final_response:   dict


# ═══════════════════════════════════════════════════════════════
#  LLM
# ═══════════════════════════════════════════════════════════════

_LLM_ROUTER = ChatAnthropic(model="claude-haiku-4-5-20251001", max_tokens=2048)


# ═══════════════════════════════════════════════════════════════
#  NŒUDS DU GRAPHE
# ═══════════════════════════════════════════════════════════════

def node_router(state: AgentState) -> AgentState:
    """Route vers fiche, excel, question ou hors_cadre."""
    last_human = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), ""
    )

    # Détecter les entités
    entites = trouver_entite(last_human)
    
    schema = get_schema()
    memory_context = get_memory_context()

    response = _LLM_ROUTER.invoke([
        SystemMessage(content=f"""Tu es un classificateur d'intention. Réponds UNIQUEMENT par un JSON valide.

{memory_context}

════════════════════════════════════════════════════════════════
SCHÉMA DES DONNÉES DISPONIBLES :
════════════════════════════════════════════════════════════════
{schema[:3000]}

════════════════════════════════════════════════════════════════
ENTITÉS DÉTECTÉES AUTOMATIQUEMENT :
════════════════════════════════════════════════════════════════
{json.dumps(entites, ensure_ascii=False)}

════════════════════════════════════════════════════════════════
4 INTENTIONS POSSIBLES :
════════════════════════════════════════════════════════════════

1. "fiche" → Demande de FICHE/RAPPORT pour une ou plusieurs prestations, prestataires ou bénéficiaires
   - Mots-clés : "fiche", "fiche de", "rapport de", "prestations de", "données de", "fiches"
   - Exemple : "fiche de CEW", "prestations de l'Extrême Nord", "fiche de toutes nos prestations"
   - RÈGLE ABSOLUE : Si l'utilisateur utilise explicitement le mot "fiche" ou "fiches", tu DOIS choisir cette intention "fiche".
   - La valeur extraite peut être le nom du prestataire, de la région, ou null si c'est géré par l'IA ensuite.

2. "excel" → Demande de FICHIER EXCEL personnalisé avec filtres (sans utiliser le mot "fiche")
   - Mots-clés : "fichier excel", "exporter", "créer un fichier", "tableau"
   - Exemple : "Excel des prestataires de F1", "exporter les données filtrées"

3. "question" → Question ANALYTIQUE sur les données (stats, comptages, répartitions)
   - Mots-clés : "combien", "quel est", "liste", "répartition", "total", "moyenne"
   - Exemple : "combien de prestataires ?", "répartition par région"

4. "hors_cadre" → Demande sans rapport avec les données de formation
   - Exemple : "quelle heure est-il ?", "écris un poème"

════════════════════════════════════════════════════════════════
FORMAT JSON À RETOURNER :
════════════════════════════════════════════════════════════════
{{
  "intent": "fiche" | "excel" | "question" | "hors_cadre",
  "valeur_recherche": "valeur pour fiche" | null,
  "raisonnement": "explication courte"
}}
"""),
        HumanMessage(content=f"Message utilisateur : {last_human}"),
    ])

    raw = response.content.strip()
    try:
        if "```" in raw:
            if "```json" in raw:
                raw = raw.split("```json")[-1].split("```")[0]
            else:
                raw = raw.split("```")[1].split("```")[0]
        parsed = json.loads(raw.strip())
        intent = parsed.get("intent", "hors_cadre")
        valeur_recherche = parsed.get("valeur_recherche") or ""
    except Exception:
        intent = "question"  # Par défaut, traiter comme question
        valeur_recherche = ""

    # Ajouter à la mémoire
    add_to_memory("user", last_human)

    return {**state, "intent": intent, "valeur_recherche": valeur_recherche, "entites": entites}


def node_pipeline_fiche(state: AgentState) -> AgentState:
    """Pipeline FICHE : déterministe avec fallback IA."""
    valeur = state.get("valeur_recherche", "")
    entites = state.get("entites", {})
    
    # Si pas de valeur du router, utiliser les entités détectées
    if not valeur:
        valeur = (
            entites.get("prestataire") or 
            entites.get("beneficiaire") or 
            entites.get("prestation_id") or 
            ""
        )
    
    if not valeur:
        result = {
            "statut": "erreur", 
            "message": "Aucune valeur de recherche identifiée. Précisez un prestataire, bénéficiaire ou prestation_id."
        }
    else:
        result = pipeline_fiche(valeur)
        
    # FALLBACK IA : si on n'obtient rien (erreur ou non_trouve)
    if result.get("statut") in ["erreur", "non_trouve"]:
        last_human = next(
            (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), ""
        )
        instruction = (
            f"Trouve les ID de prestation (colonne 'prestation_id') correspondant "
            f"à la demande suivante : '{last_human}'.\n"
            f"Retourne uniquement une liste de ces ID dans le champ 'donnees', "
            f"par exemple: result = {{'reponse': 'Voici les IDs', 'donnees': ['123', '456']}}"
        )
        fallback_res = pipeline_code(instruction, context="question")
        donnees = fallback_res.get("donnees", [])
        
        ids = []
        if isinstance(donnees, list):
            ids = [str(x) for x in donnees]
        
        if ids:
            nouveau_result = pipeline_fiche(ids)
            if nouveau_result.get("statut") not in ["erreur", "non_trouve"]:
                nouveau_result["valeur_utilisee"] = f"Extraction IA ({len(ids)} prestation(s))"
                return {**state, "result": nouveau_result}
            
        # Si ça échoue encore, on garde l'explication de l'IA si elle est pertinente
        if fallback_res.get("statut") not in ["erreur", "erreur_execution"]:
            result = {
                "statut": "non_trouve",
                "message": fallback_res.get("reponse", result.get("message", "Aucun résultat trouvé.")),
                "detail": fallback_res
            }
    
    return {**state, "result": result}


def node_pipeline_excel(state: AgentState) -> AgentState:
    """Pipeline EXCEL : génération de code."""
    last_human = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), ""
    )
    result = pipeline_code(last_human, context="excel")
    return {**state, "result": result}


def node_pipeline_question(state: AgentState) -> AgentState:
    """Pipeline QUESTION : génération de code."""
    last_human = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), ""
    )
    result = pipeline_code(last_human, context="question")
    return {**state, "result": result}


def node_hors_cadre(state: AgentState) -> AgentState:
    """Signale que la demande est hors périmètre."""
    last_human = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), ""
    )
    
    result = {
        "statut": "hors_cadre",
        "message": """⚠️ Cette demande ne correspond pas à mon périmètre.

Je suis spécialisé dans l'analyse des données de formation PADESCE.

🟢 **FICHE** : "Donne-moi la fiche de CEW" ou "Prestations de l'Extrême Nord"
🔵 **EXCEL** : "Crée un fichier Excel des prestataires de F1"
🟡 **QUESTION** : "Combien de prestataires ?", "Répartition par statut"

Reformulez votre demande !""",
        "demande_originale": last_human,
    }
    
    return {**state, "result": result}


def node_format_response(state: AgentState) -> AgentState:
    """Formate la réponse finale de manière professionnelle."""
    intent = state.get("intent", "")
    result = state.get("result", {})
    last_human = next(
        (m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), ""
    )
    
    if intent == "hors_cadre":
        final_response = {
            "intention": "hors_cadre",
            "reponse": result.get("message", "Demande hors périmètre."),
        }
    elif result.get("statut") == "erreur_execution":
        final_response = {
            "intention": intent,
            "reponse": "❌ Je n'ai pas pu traiter votre demande. Pourriez-vous la reformuler différemment ?",
            "details": result,
        }
    elif result.get("statut") == "non_trouve":
        final_response = {
            "intention": intent,
            "reponse": f"🔍 Je n'ai pas trouvé de résultat correspondant à votre recherche. Vérifiez l'orthographe ou essayez un autre terme.",
            "details": result,
        }
    else:
        # Utiliser la réponse générée par le code si disponible
        if "reponse" in result:
            reponse_base = result["reponse"]
        else:
            reponse_base = json.dumps(result.get("donnees", result), ensure_ascii=False, indent=2)
        
        # Déterminer si un fichier a été généré
        fichier_genere = result.get("fichier")
        
        llm = ChatAnthropic(model="claude-sonnet-4-20250514", max_tokens=1024)
        response = llm.invoke([
            SystemMessage(content="""Tu es un assistant professionnel et bienveillant. Tu reformules une réponse technique pour un utilisateur non-technicien.

RÈGLES IMPORTANTES :
1. Sois chaleureux et professionnel
2. Structure toujours ta réponse en 4 ou 5 paragraphes bien détaillés pour expliquer clairement les résultats
3. N'hésite pas à utiliser des listes à puces ou un petit tableau Markdown pour présenter les données de façon aérée et lisible
4. NE MENTIONNE JAMAIS les chemins d'accès aux fichiers (pas de "exports/...", pas de chemin technique)
5. Si un fichier a été généré, dis simplement "Le rapport complet (fichier Excel) a été généré et est disponible en téléchargement ci-dessous"
6. Utilise des emojis professionnels pour structurer les paragraphes (✅, 📊, 📁)"""),
            HumanMessage(content=f"Question : {last_human}\n\nRéponse brute : {reponse_base}\n\nFichier généré : {'Oui' if fichier_genere else 'Non'}"),
        ])
        
        final_response = {
            "intention": intent,
            "reponse": response.content.strip(),
            "details": result,
        }
    
    # Ajouter à la mémoire
    add_to_memory("assistant", final_response.get("reponse", ""))
    
    # Construire le message final (sans chemin technique visible)
    final_msg = final_response.get("reponse", "")
    
    # Stocker le fichier dans les détails mais ne pas l'afficher dans la réponse
    if result.get("fichier"):
        final_response["fichier_genere"] = result["fichier"]
    
    return {
        **state,
        "final_response": final_response,
        "messages": state["messages"] + [AIMessage(content=final_msg)],
    }


# ═══════════════════════════════════════════════════════════════
#  ROUTEUR CONDITIONNEL
# ═══════════════════════════════════════════════════════════════

def route_after_router(state: AgentState) -> Literal["pipeline_fiche", "pipeline_excel", "pipeline_question", "hors_cadre"]:
    return {
        "fiche": "pipeline_fiche",
        "excel": "pipeline_excel",
        "question": "pipeline_question",
    }.get(state.get("intent", ""), "hors_cadre")


# ═══════════════════════════════════════════════════════════════
#  CONSTRUCTION DU GRAPHE
# ═══════════════════════════════════════════════════════════════

def build_graph():
    """Construit et compile le graphe LangGraph."""
    graph = StateGraph(AgentState)

    graph.add_node("router", node_router)
    graph.add_node("pipeline_fiche", node_pipeline_fiche)
    graph.add_node("pipeline_excel", node_pipeline_excel)
    graph.add_node("pipeline_question", node_pipeline_question)
    graph.add_node("hors_cadre", node_hors_cadre)
    graph.add_node("format_response", node_format_response)

    graph.set_entry_point("router")

    graph.add_conditional_edges(
        "router",
        route_after_router,
        {
            "pipeline_fiche": "pipeline_fiche",
            "pipeline_excel": "pipeline_excel",
            "pipeline_question": "pipeline_question",
            "hors_cadre": "hors_cadre",
        },
    )

    graph.add_edge("pipeline_fiche", "format_response")
    graph.add_edge("pipeline_excel", "format_response")
    graph.add_edge("pipeline_question", "format_response")
    graph.add_edge("hors_cadre", "format_response")
    graph.add_edge("format_response", END)

    return graph.compile()

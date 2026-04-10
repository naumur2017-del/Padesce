# agent_padesce/pipelines.py
"""Pipelines de traitement : fiche, excel, question."""

import io
import json
import os
import sys
import traceback
from datetime import datetime

import pandas as pd
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from .config import EXPORTS_DIR, get_df
from .excel_generator import generer_rapport_excel
from .metier import extraire_infos, filtrer_classes
from .orthographe import corriger_orthographe, trouver_entite
from .schema import get_schema

# ═══════════════════════════════════════════════════════════════
#  PIPELINE FICHE (déterministe)
# ═══════════════════════════════════════════════════════════════


def pipeline_fiche(valeur_recherche: str | list) -> dict:
    """Pipeline déterministe pour générer une fiche de prestation."""
    decompte = get_df("decompte")
    classe = get_df("classe")

    if decompte is None:
        return {"statut": "erreur", "message": "BDD decompte non chargée"}

    # Correction orthographique
    if isinstance(valeur_recherche, str):
        valeur_originale = valeur_recherche
        valeur_corrigee, col_source, score = corriger_orthographe(valeur_recherche, seuil=0.75)
        correction_appliquee = None
        if col_source and score < 1.0 and score >= 0.75:
            correction_appliquee = {
                "original": valeur_originale,
                "corrige": valeur_corrigee,
                "score": round(score, 2),
            }
            valeur_recherche = valeur_corrigee
    else:
        valeur_originale = f"Liste de {len(valeur_recherche)} prestation(s)"
        correction_appliquee = None

    try:
        if isinstance(valeur_recherche, str):
            decomptesection, prestation_ids = extraire_infos(decompte, valeur_recherche)
        else:
            prestation_ids = valeur_recherche

        prestations_data = []
        for pid in prestation_ids:
            infos_df, pids = extraire_infos(decompte, pid)
            classes_df = filtrer_classes(classe, pids) if classe is not None else pd.DataFrame()
            prestations_data.append({"infos": infos_df, "classes": classes_df})

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(EXPORTS_DIR, f"fiche_{timestamp}.xlsx")

        result = generer_rapport_excel(prestations_data, output_path)
        result["valeur_recherchee"] = valeur_originale
        result["correction_appliquee"] = correction_appliquee
        result["valeur_utilisee"] = valeur_recherche

        return result

    except ValueError as e:
        return {
            "statut": "non_trouve",
            "message": str(e),
            "correction_appliquee": correction_appliquee,
        }
    except Exception as e:
        return {"statut": "erreur", "message": str(e), "detail": traceback.format_exc()}


# ═══════════════════════════════════════════════════════════════
#  GÉNÉRATION DE CODE
# ═══════════════════════════════════════════════════════════════


def generer_code(instruction: str, context: str, entites: dict = None) -> str:
    """Génère du code Python en utilisant le schéma EXACT des données."""
    llm = ChatAnthropic(model="claude-haiku-4-5-20251001", max_tokens=4096)

    schema = get_schema()
    entites_str = json.dumps(entites or {}, ensure_ascii=False)

    base_prompt = f"""Tu es un expert Python/pandas. Tu génères du code Python EXÉCUTABLE.

═══════════════════════════════════════════════════════════════
SCHÉMA EXACT DES DONNÉES (utilise EXACTEMENT ces noms de colonnes) :
═══════════════════════════════════════════════════════════════
{schema}

═══════════════════════════════════════════════════════════════
ENTITÉS DÉTECTÉES DANS LA DEMANDE :
═══════════════════════════════════════════════════════════════
{entites_str}

═══════════════════════════════════════════════════════════════
VARIABLES DISPONIBLES :
═══════════════════════════════════════════════════════════════
- decompte : DataFrame avec les données de décompte
- classe : DataFrame avec les données de classes
- pd : module pandas importé
- json : module json importé
- EXPORTS_DIR = "{EXPORTS_DIR}"

═══════════════════════════════════════════════════════════════
RÈGLES CRITIQUES :
═══════════════════════════════════════════════════════════════
1. Utilise UNIQUEMENT les colonnes listées dans le schéma ci-dessus
2. Les régions sont dans la colonne 'bénéficaire' (pas 'region')
3. Le statut est dans la colonne 'statut' avec valeurs : "EN COURS", "TERMINÉ", etc.
4. La fenêtre est dans 'fénetre' (avec accent)
5. Pour filtrer, utilise str.contains(..., case=False, na=False)
6. Génère du code Python BRUT sans markdown ni ```
"""

    if context == "excel":
        system_prompt = base_prompt + """
═══════════════════════════════════════════════════════════════
OBJECTIF : Créer un fichier Excel
═══════════════════════════════════════════════════════════════

À LA FIN, tu DOIS écrire :
result = {"fichier": chemin, "nb_lignes": len(df), "colonnes": list(df.columns), "description": "..."}
print(json.dumps(result, ensure_ascii=False, default=str))
"""  # noqa: E501
    else:  # question
        system_prompt = base_prompt + """
═══════════════════════════════════════════════════════════════
OBJECTIF : Répondre à une question analytique
═══════════════════════════════════════════════════════════════

À LA FIN, tu DOIS écrire :
result = {"reponse": "Phrase claire répondant à la question", "donnees": {...}}
print(json.dumps(result, ensure_ascii=False, default=str))

EXEMPLES DE BONNES RÉPONSES :
- "Il y a 25 prestataires distincts et 12 régions (bénéficiaires)"
- "Répartition par statut : EN COURS (45), TERMINÉ (30)"
"""

    response = llm.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"DEMANDE : {instruction}"),
        ]
    )

    code = response.content.strip()
    # Nettoyer le markdown
    if "```python" in code:
        code = code.split("```python")[1].split("```")[0]
    elif "```" in code:
        code = code.split("```")[1].split("```")[0]
    return code.strip()


# ═══════════════════════════════════════════════════════════════
#  EXÉCUTION DE CODE
# ═══════════════════════════════════════════════════════════════


def executer_code(code: str) -> dict:
    """Exécute du code Python et retourne le résultat."""
    decompte = get_df("decompte")
    classe = get_df("classe")

    env = {
        "pd": pd,
        "json": json,
        "os": os,
        "datetime": datetime,
        "EXPORTS_DIR": EXPORTS_DIR,
        "decompte": decompte.copy() if decompte is not None else pd.DataFrame(),
        "classe": classe.copy() if classe is not None else pd.DataFrame(),
        "corriger_orthographe": corriger_orthographe,
        "trouver_entite": trouver_entite,
    }

    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf

    try:
        exec(code, env)
        sys.stdout = old_stdout
        output = buf.getvalue().strip()

        try:
            result = json.loads(output)
            result["statut"] = "succes"
            result["code_genere"] = code[:800]
            return result
        except json.JSONDecodeError:
            return {
                "statut": "succes",
                "sortie": output if output else "(pas de sortie)",
                "code_genere": code[:800],
            }
    except Exception as e:
        sys.stdout = old_stdout
        return {
            "statut": "erreur_execution",
            "erreur": str(e),
            "traceback": traceback.format_exc(),
            "code_genere": code[:800],
        }


# ═══════════════════════════════════════════════════════════════
#  PIPELINE CODE (générique)
# ═══════════════════════════════════════════════════════════════


def pipeline_code(instruction: str, context: str) -> dict:
    """Pipeline générique : analyse, génère du code, l'exécute."""

    # Détecter les entités dans l'instruction
    entites = trouver_entite(instruction)

    # Générer le code
    code = generer_code(instruction, context=context, entites=entites)

    # Exécuter
    result = executer_code(code)

    # Si erreur, tenter de corriger
    if result.get("statut") == "erreur_execution":
        llm = ChatAnthropic(model="claude-sonnet-4-20250514", max_tokens=2048)

        schema = get_schema()
        fix_response = llm.invoke(
            [
                SystemMessage(content=f"""Corrige ce code Python. Le schéma des données est :
{schema}

ERREUR : {result.get("erreur")}

Retourne UNIQUEMENT le code corrigé, sans markdown."""),
                HumanMessage(content=f"Code à corriger :\n{code}"),
            ]
        )

        code_corrige = fix_response.content.strip()
        if "```" in code_corrige:
            if "```python" in code_corrige:
                code_corrige = code_corrige.split("```python")[-1].split("```")[0]
            else:
                code_corrige = code_corrige.split("```")[1].split("```")[0]

        result = executer_code(code_corrige.strip())
        result["correction_code"] = True

    result["entites_detectees"] = entites
    result["instruction_originale"] = instruction

    return result

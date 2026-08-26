"""Agent IA conversationnel pour le reporting — utilise Groq (Llama) ou Gemini."""

import os
import json
from groq import Groq

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY2", ""))

SYSTEM_PROMPT = """Tu es l'Agent de Reporting NAUMUR, un assistant spécialisé dans l'évaluation
de la performance des prestataires de formation pour le projet PADESCE (Banque Mondiale, Cameroun).

Tu connais parfaitement le contexte socio-géo-démographique et politique du Cameroun :
- Les 10 régions, leurs chefs-lieux, les défis spécifiques (réseau, électricité, sécurité)
- La crise anglophone dans le Nord-Ouest et Sud-Ouest
- Les zones sahéliennes du Grand Nord (insécurité Boko Haram)
- Les contraintes d'accès routier et de couverture réseau
- Les enjeux de genre et d'inclusion dans la formation professionnelle

Quand on te soumet des données sur un prestataire, tu dois :
1. Analyser les données quantitatives (nombre d'apprenants, formations, complétude)
2. Prendre en compte le contexte local (zone difficile = bonus, zone facile = standard)
3. Évaluer sur 3 catégories : Faible, Moyen, Excellent
4. Justifier ton évaluation avec des arguments précis
5. Proposer des recommandations concrètes

Réponds toujours en français. Sois précis, factuel et bienveillant.
Quand des informations manquent, pose des questions complémentaires."""


def get_ai_commentary(analysis: dict, evaluation: dict) -> str:
    """Get AI-generated commentary on the provider evaluation."""
    if not GROQ_API_KEY:
        return _fallback_commentary(analysis, evaluation)

    client = Groq(api_key=GROQ_API_KEY)

    prompt = f"""Voici les résultats de l'évaluation du prestataire "{analysis.get('prestataire', 'Inconnu')}" :

DONNÉES CLÉS :
- Apprenants : {analysis['nb_apprenants']}
- Formations : {analysis['nb_formations']} ({', '.join(analysis['formations_list'][:5])})
- Villes : {', '.join(analysis['villes'])}
- Régions : {', '.join(analysis['regions'])}
- Bénéficiaires : {', '.join(analysis.get('beneficiaires', [])[:3])}
- Genre : {analysis['genre_distribution']}
- Complétude données : {analysis['score_completude']}%
- Expérience moyenne : {analysis.get('experience_moyenne', 'N/D')} ans

ÉVALUATION :
- Score global : {evaluation['score_global']}%
- Catégorie : {evaluation['categorie']}
- Alertes : {'; '.join(evaluation['alertes'][:3])}

CONTEXTE GÉOGRAPHIQUE :
{json.dumps([c.get('nom', '') + ': ' + '; '.join(c.get('defis', [])[:2]) for c in analysis.get('contexte_geo', [])], ensure_ascii=False)}

Rédige une analyse détaillée en 3-4 paragraphes :
1. Résumé de la performance globale
2. Points forts et points à améliorer
3. Impact du contexte géographique sur l'évaluation
4. Recommandations concrètes pour améliorer la performance"""

    try:
        response = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1500,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[AI] Erreur Groq : {e}")
        return _fallback_commentary(analysis, evaluation)


def chat_with_agent(user_message: str, analysis: dict | None = None, history: list | None = None) -> str:
    """Conversational chat with the AI agent."""
    if not GROQ_API_KEY:
        return "Clé API Groq non configurée. Veuillez définir GROQ_API_KEY."

    client = Groq(api_key=GROQ_API_KEY)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if analysis:
        context = f"""Contexte actuel — Prestataire : {analysis.get('prestataire', 'Inconnu')}
Apprenants : {analysis['nb_apprenants']}, Formations : {analysis['nb_formations']}
Villes : {', '.join(analysis['villes'])}, Régions : {', '.join(analysis['regions'])}
Complétude : {analysis['score_completude']}%"""
        messages.append({"role": "system", "content": context})

    if history:
        messages.extend(history[-10:])

    messages.append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=messages,
            temperature=0.4,
            max_tokens=1000,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erreur de l'agent IA : {e}"


def _fallback_commentary(analysis: dict, evaluation: dict) -> str:
    """Commentary without API."""
    cat = evaluation["categorie"]
    score = evaluation["score_global"]
    provider = analysis.get("prestataire", "Ce prestataire")

    parts = []
    parts.append(
        f"{provider} obtient un score global de {score}%, ce qui le classe dans la catégorie "
        f"« {cat} ». Cette évaluation prend en compte sept critères pondérés couvrant la "
        f"complétude des données, le volume de formation, la diversité des contenus, "
        f"la parité de genre, la couverture géographique, l'adaptation au contexte local "
        f"et la qualité de la planification."
    )

    strengths = [j for j in evaluation["justifications"] if j["score"] >= 60]
    weaknesses = [j for j in evaluation["justifications"] if j["score"] < 40]

    if strengths:
        parts.append(
            "Points forts : " + "; ".join(f"{s['critere']} ({s['score']:.0f}%)" for s in strengths[:3]) + "."
        )
    if weaknesses:
        parts.append(
            "Points à améliorer : " + "; ".join(f"{w['critere']} ({w['score']:.0f}%)" for w in weaknesses[:3]) + "."
        )

    if analysis.get("contexte_geo"):
        zones = [c.get("nom", "") for c in analysis["contexte_geo"]]
        parts.append(
            f"Le prestataire opère dans {', '.join(zones)}, ce qui présente des défis "
            f"spécifiques en termes d'accès, de réseau et de conditions socio-économiques."
        )

    parts.append(
        "Recommandation : renforcer la collecte de données pour améliorer le score de complétude, "
        "et diversifier les lieux de formation pour accroître la couverture géographique."
    )

    return "\n\n".join(parts)

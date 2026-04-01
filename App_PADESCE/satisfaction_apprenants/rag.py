from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

import requests
from django.conf import settings


GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_RAG_MODEL = "openai/gpt-oss-20b"


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    lowered = without_marks.lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(cleaned.split())


def _tokenize(value: str) -> set[str]:
    return {token for token in _normalize_text(value).split() if token}


def _read_local_env_value(key: str) -> str:
    env_paths = [
        Path(settings.BASE_DIR) / ".env.local",
        Path(settings.BASE_DIR) / ".env",
    ]
    for env_path in env_paths:
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            current_key, current_value = line.split("=", 1)
            if current_key.strip() == key:
                return current_value.strip()
    return ""


def groq_api_key() -> str:
    return os.getenv("GROQ_API_KEY") or _read_local_env_value("GROQ_API_KEY")


def groq_rag_model() -> str:
    return (
        os.getenv("GROQ_RAG_MODEL")
        or _read_local_env_value("GROQ_RAG_MODEL")
        or DEFAULT_GROQ_RAG_MODEL
    )


def _extract_explicit_filters(prompt: str) -> dict:
    normalized = _normalize_text(prompt)
    filters: dict[str, str] = {}

    class_match = re.search(r"\bcla\s*0*([0-9]{1,4})\b", normalized)
    if class_match:
        filters["classe_code"] = f"CLA{int(class_match.group(1)):03d}"

    apprenant_match = re.search(r"\bapp\s*0*([0-9]{1,5})\b", normalized)
    if apprenant_match:
        filters["source_apprenant_id"] = f"APP{int(apprenant_match.group(1)):03d}"

    inspecteur_match = re.search(r"\bins\s*0*([0-9]{1,4})\b", normalized)
    if inspecteur_match:
        filters["inspecteur_code"] = f"INS{int(inspecteur_match.group(1)):03d}"

    cohorte_match = re.search(r"\bcohorte\s*([0-9]+)\b", normalized)
    if cohorte_match:
        filters["cohorte"] = cohorte_match.group(1)

    fenetre_match = re.search(r"\bfenetre\s*([0-9]+)\b", normalized)
    if fenetre_match:
        filters["source_fenetre"] = fenetre_match.group(1)

    status_map = {
        "termine": "TERMINÉ",
        "terminee": "TERMINÉ",
        "terminee": "TERMINÉ",
        "en cours": "EN COURS",
        "non demarre": "NON DÉMARRÉ",
        "arrete": "ARRÊTÉ",
        "arretee": "ARRÊTÉ",
        "annule": "ANNULÉ",
    }
    for phrase, canonical in status_map.items():
        if phrase in normalized:
            filters["statut_prestation"] = canonical
            break

    return filters


def _row_matches_explicit_filters(document: dict, filters: dict) -> bool:
    for field_name, expected in filters.items():
        value = str(document["metadata"].get(field_name) or "").strip()
        if not value:
            return False
        if _normalize_text(value) != _normalize_text(expected):
            return False
    return True


def _build_apprenant_documents(rows: list[dict]) -> list[dict]:
    documents = []
    for index, row in enumerate(rows, start=1):
        metadata = {
            "row_number": index,
            "classe_code": row.get("classe_code", ""),
            "source_apprenant_id": row.get("source_apprenant_id", ""),
            "apprenant_code": row.get("apprenant_code", ""),
            "apprenant_nom": row.get("apprenant_nom", ""),
            "beneficiaire": row.get("beneficiaire", ""),
            "prestataire": row.get("prestataire", ""),
            "formation": row.get("formation_intitule") or row.get("classe_intitule") or "",
            "inspecteur_code": row.get("inspecteur_code") or row.get("source_inspecteur_id") or "",
            "cohorte": row.get("cohorte", ""),
            "source_fenetre": row.get("source_fenetre", ""),
            "statut_prestation": row.get("source_statut_prestation", "") or row.get("statut_prestation", ""),
            "source_enquete_id": row.get("source_enquete_id", ""),
            "commentaire": row.get("commentaire", ""),
            "recommandations": row.get("recommandations", ""),
        }
        q_values = {
            f"Q{idx}": row.get(field)
            for idx, (field, _label) in enumerate(
                (
                    ("q1_clarte_exposes", ""),
                    ("q2_interaction_formateur", ""),
                    ("q3_maitrise_contenu", ""),
                    ("q4_salle_adequate", ""),
                    ("q5_materiel_disponible", ""),
                    ("q6_organisation_temps", ""),
                    ("q7_utilite_formation", ""),
                    ("q8_adequation_besoins", ""),
                    ("q9_satisfaction_globale", ""),
                ),
                start=1,
            )
        }
        metadata.update(q_values)
        text = (
            f"Ligne {index}. ID apprenant: {metadata['source_apprenant_id'] or metadata['apprenant_code']}. "
            f"Nom apprenant: {metadata['apprenant_nom']}. "
            f"Bénéficiaire: {metadata['beneficiaire']}. "
            f"Prestataire: {metadata['prestataire']}. "
            f"Formation: {metadata['formation']}. "
            f"Inspecteur: {metadata['inspecteur_code'] or '-'} . "
            f"Classe: {metadata['classe_code']}. "
            f"Cohorte: {metadata['cohorte']}. "
            f"Fenêtre: {metadata['source_fenetre'] or '-'}. "
            f"Statut de la prestation: {metadata['statut_prestation'] or '-'}. "
            f"Numéro enquête: {metadata['source_enquete_id'] or '-'}. "
            f"Q1 à Q9: {', '.join(f'{key}={value}' for key, value in q_values.items())}. "
            f"Commentaire: {metadata['commentaire'] or 'RAS'}. "
            f"Recommandations: {metadata['recommandations'] or 'RAS'}."
        )
        documents.append(
            {
                "id": f"apprenant-{index}",
                "kind": "apprenant",
                "label": f"{metadata['source_apprenant_id'] or metadata['apprenant_code']} - {metadata['apprenant_nom']}",
                "metadata": metadata,
                "text": text,
                "search_text": _normalize_text(text),
                "tokens": _tokenize(text),
                "display_row": {
                    "numero": index,
                    "id_apprenant": metadata["source_apprenant_id"] or metadata["apprenant_code"],
                    "nom_apprenant": metadata["apprenant_nom"],
                    "beneficiaire": metadata["beneficiaire"],
                    "prestataire": metadata["prestataire"],
                    "formation": metadata["formation"],
                    "inspecteur": metadata["inspecteur_code"],
                    "classe": metadata["classe_code"],
                    "cohorte": metadata["cohorte"],
                    "statut_prestation": metadata["statut_prestation"],
                    "enquete": metadata["source_enquete_id"],
                },
            }
        )
    return documents


def _build_summary_documents(active_tab: str, context: dict) -> list[dict]:
    documents = []
    if active_tab == "tab-classe":
        for index, item in enumerate(context.get("classe_stats", []), start=1):
            text = (
                f"Classe {item['code']}. Formation: {item['intitule']}. Cohorte: {item['cohorte']}. "
                f"Nombre d'enquêtes: {item['nb']}. Moyennes: {item['avgs']}."
            )
            documents.append(
                {
                    "id": f"classe-{index}",
                    "kind": "classe",
                    "label": item["code"],
                    "metadata": {
                        "classe_code": item["code"],
                        "formation": item["intitule"],
                        "cohorte": item["cohorte"],
                        "nb": item["nb"],
                    },
                    "text": text,
                    "search_text": _normalize_text(text),
                    "tokens": _tokenize(text),
                    "display_row": {
                        "classe": item["code"],
                        "formation": item["intitule"],
                        "cohorte": item["cohorte"],
                        "nb": item["nb"],
                    },
                }
            )
    elif active_tab == "tab-prestation":
        for index, item in enumerate(context.get("prestation_stats", []), start=1):
            text = (
                f"Prestation {item['code']}. Prestataire: {item['prestataire']}. "
                f"Bénéficiaire: {item['beneficiaire']}. Nombre d'enquêtes: {item['nb']}. "
                f"Global Q9: {item['avg']}."
            )
            documents.append(
                {
                    "id": f"prestation-{index}",
                    "kind": "prestation",
                    "label": item["code"],
                    "metadata": {
                        "prestation_code": item["code"],
                        "prestataire": item["prestataire"],
                        "beneficiaire": item["beneficiaire"],
                        "nb": item["nb"],
                    },
                    "text": text,
                    "search_text": _normalize_text(text),
                    "tokens": _tokenize(text),
                    "display_row": {
                        "prestation": item["code"],
                        "prestataire": item["prestataire"],
                        "beneficiaire": item["beneficiaire"],
                        "nb": item["nb"],
                    },
                }
            )
    elif active_tab == "tab-cohorte":
        for index, item in enumerate(context.get("cohorte_stats", []), start=1):
            text = (
                f"Cohorte {item['label']}. Nombre d'enquêtes: {item['nb']}. "
                f"Global Q9: {item['avg']}. Moyennes: {item['avgs']}."
            )
            documents.append(
                {
                    "id": f"cohorte-{index}",
                    "kind": "cohorte",
                    "label": item["label"],
                    "metadata": {
                        "cohorte": item["label"],
                        "nb": item["nb"],
                    },
                    "text": text,
                    "search_text": _normalize_text(text),
                    "tokens": _tokenize(text),
                    "display_row": {"cohorte": item["label"], "nb": item["nb"]},
                }
            )
    elif active_tab == "tab-ville":
        for index, item in enumerate(context.get("ville_stats", []), start=1):
            text = f"Ville {item['ville']}. Nombre d'enquêtes: {item['nb']}. Moyenne Q9: {item['avg']}."
            documents.append(
                {
                    "id": f"ville-{index}",
                    "kind": "ville",
                    "label": item["ville"],
                    "metadata": {"ville": item["ville"], "nb": item["nb"]},
                    "text": text,
                    "search_text": _normalize_text(text),
                    "tokens": _tokenize(text),
                    "display_row": {"ville": item["ville"], "nb": item["nb"]},
                }
            )
    else:
        for index, item in enumerate(context.get("user_stats", []), start=1):
            text = f"Utilisateur {item['username']}. Nombre d'enquêtes: {item['nb']}. Moyenne Q9: {item['avg']}."
            documents.append(
                {
                    "id": f"user-{index}",
                    "kind": "user",
                    "label": item["username"],
                    "metadata": {"user": item["username"], "nb": item["nb"]},
                    "text": text,
                    "search_text": _normalize_text(text),
                    "tokens": _tokenize(text),
                    "display_row": {"user": item["username"], "nb": item["nb"]},
                }
            )
    return documents


def build_active_tab_documents(active_tab: str, context: dict, rows: list[dict]) -> list[dict]:
    if active_tab == "tab-apprenants":
        return _build_apprenant_documents(rows)
    return _build_summary_documents(active_tab, context)


def retrieve_documents(prompt: str, active_tab: str, context: dict, rows: list[dict], limit: int = 16) -> list[dict]:
    documents = build_active_tab_documents(active_tab, context, rows)
    if not documents:
        return []

    explicit_filters = _extract_explicit_filters(prompt)
    filtered_documents = [doc for doc in documents if _row_matches_explicit_filters(doc, explicit_filters)] if explicit_filters else documents
    if not filtered_documents:
        filtered_documents = documents

    prompt_tokens = _tokenize(prompt)
    normalized_prompt = _normalize_text(prompt)

    def score(doc: dict) -> tuple[int, int, int]:
        overlap = len(prompt_tokens & doc["tokens"])
        substring_hits = sum(1 for token in prompt_tokens if token and token in doc["search_text"])
        exact_bonus = 0
        for expected in explicit_filters.values():
            if expected and _normalize_text(expected) in doc["search_text"]:
                exact_bonus += 4
        return (overlap + exact_bonus, substring_hits, -len(doc["text"]))

    ranked = sorted(filtered_documents, key=score, reverse=True)

    if not prompt_tokens and normalized_prompt:
        return ranked[:limit]

    useful = [doc for doc in ranked if score(doc)[0] > 0 or score(doc)[1] > 0]
    return (useful or ranked)[:limit]


def _extract_json_object(text: str) -> dict | None:
    if not text:
        return None
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _compact_document(doc: dict) -> dict:
    display_row = doc.get("display_row") or {}
    compact_row = {}
    for key in list(display_row.keys())[:12]:
        compact_row[key] = display_row.get(key)
    return {
        "id": doc["id"],
        "label": doc["label"],
        "kind": doc["kind"],
        "row": compact_row,
    }


def _call_groq_rag(prompt: str, active_tab: str, retrieved_documents: list[dict]) -> tuple[dict, str]:
    api_key = groq_api_key()
    if not api_key:
        raise RuntimeError("Clé Groq manquante. Définissez GROQ_API_KEY dans l'environnement ou dans le fichier .env.")

    model = groq_rag_model()
    compact_documents = [
        {
            "id": doc["id"],
            "label": doc["label"],
            "kind": doc["kind"],
            "metadata": doc["metadata"],
            "text": doc["text"],
        }
        for doc in retrieved_documents
    ]

    system_prompt = (
        "Tu es l'assistant analytique PADESCE. "
        "Tu réponds uniquement à partir du contexte fourni. "
        "Si le contexte ne suffit pas, dis-le clairement sans inventer. "
        "Quand l'utilisateur demande d'afficher ou de lister des éléments, "
        "retourne les identifiants des lignes correspondantes dans matched_doc_ids. "
        "Réponds en JSON strict avec les clés answer, matched_doc_ids et insufficient_context."
    )
    user_prompt = json.dumps(
        {
            "active_tab": active_tab,
            "question": prompt,
            "documents": compact_documents,
            "instructions": {
                "language": "fr",
                "answer_style": "court, précis, orienté données",
                "max_matched_doc_ids": 20,
            },
        },
        ensure_ascii=False,
    )

    response = requests.post(
        GROQ_CHAT_COMPLETIONS_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    data = _extract_json_object(content) or {
        "answer": content.strip(),
        "matched_doc_ids": [],
        "insufficient_context": False,
    }
    return data, model


def _call_groq_rag(prompt: str, active_tab: str, retrieved_documents: list[dict]) -> tuple[dict, str]:
    api_key = groq_api_key()
    if not api_key:
        raise RuntimeError("Cle Groq manquante. Definissez GROQ_API_KEY dans l'environnement ou dans le fichier .env.")

    model = groq_rag_model()
    compact_documents = [_compact_document(doc) for doc in retrieved_documents]
    system_prompt = (
        "Tu es l'assistant analytique PADESCE. "
        "Tu reponds uniquement a partir du contexte fourni. "
        "Si le contexte ne suffit pas, dis-le clairement sans inventer. "
        "Quand l'utilisateur demande d'afficher ou de lister des elements, "
        "retourne les identifiants des lignes correspondantes dans matched_doc_ids. "
        "Reponds en JSON strict avec les cles answer, matched_doc_ids et insufficient_context."
    )

    attempt_sizes: list[int] = []
    for candidate in (16, 12, 8, 4):
        size = min(len(compact_documents), candidate)
        if size > 0 and size not in attempt_sizes:
            attempt_sizes.append(size)

    response = None
    payload = None
    for size in attempt_sizes or [len(compact_documents)]:
        user_prompt = json.dumps(
            {
                "active_tab": active_tab,
                "question": prompt,
                "documents": compact_documents[:size],
                "instructions": {
                    "language": "fr",
                    "answer_style": "court, precis, oriente donnees",
                    "max_matched_doc_ids": min(size, 20),
                },
            },
            ensure_ascii=False,
        )

        response = requests.post(
            GROQ_CHAT_COMPLETIONS_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
            },
            timeout=45,
        )
        if response.status_code == 413 and size != attempt_sizes[-1]:
            continue
        response.raise_for_status()
        payload = response.json()
        break

    if payload is None:
        if response is not None:
            response.raise_for_status()
        raise RuntimeError("Reponse Groq indisponible.")

    content = payload["choices"][0]["message"]["content"]
    data = _extract_json_object(content) or {
        "answer": content.strip(),
        "matched_doc_ids": [],
        "insufficient_context": False,
    }
    return data, model


def answer_dashboard_prompt(prompt: str, active_tab: str, context: dict, rows: list[dict]) -> dict:
    prompt = str(prompt or "").strip()
    if not prompt:
        raise ValueError("Le prompt est vide.")

    retrieved_documents = retrieve_documents(prompt, active_tab, context, rows)
    if not retrieved_documents:
        return {
            "answer_markdown": "Aucune donnée n'est disponible dans la table active pour répondre à cette question.",
            "matched_rows": [],
            "retrieved_count": 0,
            "model": groq_rag_model(),
        }

    groq_result, model = _call_groq_rag(prompt, active_tab, retrieved_documents)
    matched_ids = set(groq_result.get("matched_doc_ids") or [])
    matched_rows = [
        {
            "doc_id": doc["id"],
            "label": doc["label"],
            **doc["display_row"],
        }
        for doc in retrieved_documents
        if doc["id"] in matched_ids
    ]

    return {
        "answer_markdown": str(groq_result.get("answer") or "").strip() or "Aucune réponse générée.",
        "matched_rows": matched_rows,
        "retrieved_count": len(retrieved_documents),
        "insufficient_context": bool(groq_result.get("insufficient_context")),
        "model": model,
    }

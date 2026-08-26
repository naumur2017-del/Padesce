"""Point d'entree principal de l'agent de reporting."""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reporting_agent.data_analyzer import load_excel_data, analyze_provider_data
from reporting_agent.evaluator import evaluate_provider, get_followup_questions, generate_investment_recommendations
from reporting_agent.report_generator import generate_charts, generate_pdf_report
from reporting_agent.ai_agent import get_ai_commentary


def run_report(excel_path: str, logo_path: str | None = None,
               extra_answers: dict | None = None) -> dict:
    """Run the full reporting pipeline on an Excel file."""
    print(f"\n{'='*60}")
    print("  AGENT DE REPORTING NAUMUR — PADESCE")
    print(f"{'='*60}\n")

    # 1. Load data
    print("[1/5] Chargement des données...")
    data = load_excel_data(excel_path)
    print(f"  → Fichier : {data['file_name']}")
    print(f"  → Feuilles : {list(data['sheets'].keys())}")

    # 2. Analyze
    print("\n[2/5] Analyse des données...")
    analysis = analyze_provider_data(data)
    print(f"  → Prestataire : {analysis['prestataire']}")
    print(f"  → Apprenants : {analysis['nb_apprenants']}")
    print(f"  → Formations : {analysis['nb_formations']}")
    print(f"  → Villes : {', '.join(analysis['villes'])}")
    print(f"  → Régions : {', '.join(analysis['regions'])}")
    print(f"  → Complétude : {analysis['score_completude']}%")

    # 3. Follow-up questions
    questions = get_followup_questions(analysis)
    if questions:
        print(f"\n[?] Questions complémentaires suggérées :")
        for q in questions:
            print(f"  → {q['question']}")

    # 4. Evaluate
    print("\n[3/5] Évaluation multicritère...")
    evaluation = evaluate_provider(analysis, extra_answers)
    print(f"  → Score global : {evaluation['score_global']}%")
    print(f"  → Catégorie : {evaluation['categorie']}")
    if evaluation["alertes"]:
        for a in evaluation["alertes"]:
            print(f"  ⚠ {a}")

    # 5. Investment recommendations
    print("\n[4/6] Recommandations d'investissement...")
    investment_recs = generate_investment_recommendations(analysis, evaluation)
    for rec in investment_recs:
        print(f"  [{rec['type']}] {rec['titre']}")

    # 6. AI Commentary
    print("\n[5/6] Génération du commentaire IA...")
    ai_commentary = get_ai_commentary(analysis, evaluation)
    print(f"  → Commentaire généré ({len(ai_commentary)} caractères)")

    # 7. Charts + PDF
    print("\n[6/6] Génération des graphiques et du rapport PDF...")
    charts = generate_charts(analysis, evaluation)
    print(f"  → {len(charts)} graphique(s) généré(s)")

    pdf_path = generate_pdf_report(analysis, evaluation, charts,
                                    ai_commentary=ai_commentary, logo_path=logo_path,
                                    investment_recs=investment_recs)
    print(f"\n{'='*60}")
    print(f"  ✅ RAPPORT GÉNÉRÉ : {pdf_path}")
    print(f"{'='*60}\n")

    return {
        "analysis": analysis,
        "evaluation": evaluation,
        "ai_commentary": ai_commentary,
        "charts": charts,
        "pdf_path": pdf_path,
        "questions": questions,
        "investment_recs": investment_recs,
    }


if __name__ == "__main__":
    excel_file = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Jack Brayan\Downloads\Liste_Apprenants_calendrier_AMIFO.xlsx"
    logo = str(Path(__file__).resolve().parent.parent / "static" / "branding" / "logo.png")
    if not Path(logo).exists():
        logo = None

    os.environ.setdefault("GROQ_API_KEY", os.environ.get("GROQ_API_KEY2", ""))

    result = run_report(excel_file, logo_path=logo)

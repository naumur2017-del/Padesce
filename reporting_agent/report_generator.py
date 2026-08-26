"""Generation du rapport PDF de performance du prestataire."""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage, PageBreak, HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT


NAUMUR_BLUE = colors.HexColor("#1A5276")
NAUMUR_LIGHT = colors.HexColor("#D4E6F1")
EXCELLENT_GREEN = colors.HexColor("#27AE60")
MOYEN_ORANGE = colors.HexColor("#F39C12")
FAIBLE_RED = colors.HexColor("#E74C3C")

EXPORTS_DIR = Path("exports")
EXPORTS_DIR.mkdir(exist_ok=True)
FIGURES_DIR = EXPORTS_DIR / "figures"
FIGURES_DIR.mkdir(exist_ok=True)


def _cat_color(cat: str):
    return {"Excellent": EXCELLENT_GREEN, "Moyen": MOYEN_ORANGE, "Faible": FAIBLE_RED}.get(cat, colors.grey)


def generate_charts(analysis: dict, evaluation: dict) -> dict:
    """Generate all charts and return paths."""
    charts = {}

    # 1. Radar / bar chart of criteria scores
    fig, ax = plt.subplots(figsize=(8, 4))
    justs = evaluation["justifications"]
    names = [j["critere"][:25] for j in justs]
    scores = [j["score"] for j in justs]
    bar_colors = ["#27AE60" if s >= 70 else "#F39C12" if s >= 40 else "#E74C3C" for s in scores]
    y_pos = range(len(names))
    ax.barh(y_pos, scores, color=bar_colors, alpha=0.8, edgecolor="white")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlim(0, 105)
    ax.set_xlabel("Score (%)")
    ax.set_title("Scores par critère d'évaluation", fontweight="bold", fontsize=11)
    ax.axvline(70, color="#27AE60", linestyle="--", alpha=0.5, label="Seuil Excellent")
    ax.axvline(45, color="#F39C12", linestyle="--", alpha=0.5, label="Seuil Moyen")
    ax.legend(fontsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    path = FIGURES_DIR / "scores_criteres.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    charts["scores_criteres"] = str(path)

    # 2. Genre distribution pie
    genre = analysis.get("genre_distribution", {})
    if genre:
        fig, ax = plt.subplots(figsize=(4, 4))
        labels = list(genre.keys())
        values = list(genre.values())
        pie_colors = ["#3498DB" if l == "M" else "#E91E63" for l in labels]
        wedges, texts, autotexts = ax.pie(values, labels=labels, colors=pie_colors,
                                          autopct="%1.0f%%", startangle=90, textprops={"fontsize": 10})
        ax.set_title("Répartition par genre", fontweight="bold", fontsize=11)
        fig.tight_layout()
        path = FIGURES_DIR / "genre_distribution.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        charts["genre_distribution"] = str(path)

    # 3. Completude heatmap
    completude = analysis.get("completude_donnees", {})
    if completude:
        fig, ax = plt.subplots(figsize=(8, max(3, len(completude) * 0.3)))
        cols = list(completude.keys())[:15]
        vals = [completude[c] for c in cols]
        clean_cols = [c.split("/")[0].strip()[:30] for c in cols]
        bar_colors = ["#27AE60" if v >= 80 else "#F39C12" if v >= 50 else "#E74C3C" for v in vals]
        ax.barh(range(len(clean_cols)), vals, color=bar_colors, alpha=0.8)
        ax.set_yticks(range(len(clean_cols)))
        ax.set_yticklabels(clean_cols, fontsize=7)
        ax.set_xlim(0, 105)
        ax.set_xlabel("Complétude (%)")
        ax.set_title("Complétude des données par champ", fontweight="bold", fontsize=10)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        path = FIGURES_DIR / "completude_donnees.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        charts["completude_donnees"] = str(path)

    # 4. Score gauge
    fig, ax = plt.subplots(figsize=(5, 3))
    score = evaluation["score_global"]
    cat = evaluation["categorie"]
    theta = np.linspace(np.pi, 0, 100)
    ax.plot(np.cos(theta), np.sin(theta), color="#DDD", linewidth=20, solid_capstyle="round")
    n_fill = int(score)
    theta_fill = np.linspace(np.pi, np.pi - (np.pi * score / 100), max(2, n_fill))
    color = "#27AE60" if score >= 70 else "#F39C12" if score >= 45 else "#E74C3C"
    ax.plot(np.cos(theta_fill), np.sin(theta_fill), color=color, linewidth=20, solid_capstyle="round")
    ax.text(0, 0.1, f"{score}%", ha="center", va="center", fontsize=28, fontweight="bold", color=color)
    ax.text(0, -0.15, cat.upper(), ha="center", va="center", fontsize=14, fontweight="bold", color=color)
    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-0.4, 1.2)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Score Global de Performance", fontweight="bold", fontsize=12, pad=10)
    fig.tight_layout()
    path = FIGURES_DIR / "score_gauge.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    charts["score_gauge"] = str(path)

    return charts


def generate_pdf_report(analysis: dict, evaluation: dict, charts: dict,
                        ai_commentary: str = "", logo_path: str | None = None,
                        investment_recs: list | None = None) -> str:
    """Generate the full PDF report."""
    provider_name = analysis.get("prestataire", "Inconnu")
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in str(provider_name))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"rapport_{safe_name}_{timestamp}.pdf"
    filepath = EXPORTS_DIR / filename

    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2.5 * cm,
        rightMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("TitleReport", parent=styles["Title"], fontSize=20,
                              textColor=NAUMUR_BLUE, spaceAfter=6))
    styles.add(ParagraphStyle("SubTitle", parent=styles["Normal"], fontSize=12,
                              textColor=colors.grey, alignment=TA_CENTER, spaceAfter=20))
    styles.add(ParagraphStyle("SectionHead", parent=styles["Heading2"], fontSize=14,
                              textColor=NAUMUR_BLUE, spaceBefore=20, spaceAfter=8))
    styles.add(ParagraphStyle("BodyJustify", parent=styles["Normal"], fontSize=10,
                              leading=14, alignment=TA_JUSTIFY, spaceAfter=6))
    styles.add(ParagraphStyle("AlertStyle", parent=styles["Normal"], fontSize=10,
                              textColor=colors.red, leading=13))
    styles.add(ParagraphStyle("SmallCenter", parent=styles["Normal"], fontSize=9,
                              alignment=TA_CENTER, textColor=colors.grey))

    elements = []

    # ── COVER PAGE ──
    if logo_path and os.path.exists(logo_path):
        elements.append(Spacer(1, 1 * cm))
        elements.append(RLImage(logo_path, width=5 * cm, height=5 * cm))
        elements.append(Spacer(1, 1 * cm))
    else:
        elements.append(Spacer(1, 3 * cm))

    elements.append(Paragraph("RAPPORT D'ÉVALUATION DE PERFORMANCE", styles["TitleReport"]))
    elements.append(Paragraph(f"Prestataire : {provider_name}", styles["SubTitle"]))
    elements.append(Paragraph(
        f"Date : {datetime.now().strftime('%d/%m/%Y')} | Généré par l'Agent de Reporting NAUMUR",
        styles["SubTitle"]
    ))
    elements.append(HRFlowable(width="80%", thickness=2, color=NAUMUR_BLUE))
    elements.append(Spacer(1, 1 * cm))

    # Score gauge
    if "score_gauge" in charts:
        elements.append(RLImage(charts["score_gauge"], width=12 * cm, height=7 * cm))
    elements.append(Spacer(1, 0.5 * cm))

    cat = evaluation["categorie"]
    cat_color_hex = {
        "Excellent": "#27AE60", "Moyen": "#F39C12", "Faible": "#E74C3C"
    }.get(cat, "#888888")
    elements.append(Paragraph(
        f'<font size="16" color="{cat_color_hex}"><b>Catégorie : {cat.upper()}</b></font>',
        ParagraphStyle("CatStyle", alignment=TA_CENTER, spaceAfter=20)
    ))

    elements.append(PageBreak())

    # ── SOMMAIRE ──
    elements.append(Paragraph("1. Informations Générales", styles["SectionHead"]))
    info_data = [
        ["Prestataire", str(provider_name)],
        ["Nombre d'apprenants", str(analysis["nb_apprenants"])],
        ["Nombre de formations", str(analysis["nb_formations"])],
        ["Nombre de séances", str(analysis.get("nb_seances", "N/D"))],
        ["Villes couvertes", ", ".join(analysis["villes"]) or "N/D"],
        ["Régions", ", ".join(analysis["regions"]) or "N/D"],
        ["Score de complétude", f"{analysis['score_completude']}%"],
    ]
    if analysis.get("beneficiaires"):
        info_data.append(["Bénéficiaires", ", ".join(analysis["beneficiaires"][:3])])
    if analysis.get("experience_moyenne"):
        info_data.append(["Expérience moyenne", f"{analysis['experience_moyenne']} ans"])

    t = Table(info_data, colWidths=[6 * cm, 10 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), NAUMUR_LIGHT),
        ("TEXTCOLOR", (0, 0), (0, -1), NAUMUR_BLUE),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.5 * cm))

    # ── FORMATIONS ──
    if analysis["formations_list"]:
        elements.append(Paragraph("2. Formations Dispensées", styles["SectionHead"]))
        for i, f in enumerate(analysis["formations_list"], 1):
            elements.append(Paragraph(f"  {i}. {f}", styles["BodyJustify"]))
        elements.append(Spacer(1, 0.3 * cm))

    # ── CONTEXTE GEO ──
    elements.append(Paragraph("3. Contexte Socio-Géographique", styles["SectionHead"]))
    for ctx in analysis.get("contexte_geo", []):
        nom = ctx.get("nom", "Zone")
        elements.append(Paragraph(f"<b>{nom}</b>", styles["BodyJustify"]))
        if ctx.get("particularites"):
            elements.append(Paragraph(f"  → {ctx['particularites']}", styles["BodyJustify"]))
        defis = ctx.get("defis", [])
        for d in defis[:3]:
            elements.append(Paragraph(f"  • {d}", styles["BodyJustify"]))
        elements.append(Spacer(1, 0.2 * cm))

    # ── EVALUATION DETAILLEE ──
    elements.append(PageBreak())
    elements.append(Paragraph("4. Évaluation Détaillée", styles["SectionHead"]))

    if "scores_criteres" in charts:
        elements.append(RLImage(charts["scores_criteres"], width=16 * cm, height=8 * cm))
        elements.append(Spacer(1, 0.3 * cm))

    eval_data = [["Critère", "Score", "Poids", "Niveau", "Détail"]]
    for j in evaluation["justifications"]:
        eval_data.append([
            j["critere"][:25],
            f"{j['score']:.0f}%",
            f"{j['poids']*100:.0f}%",
            j["niveau"].upper(),
            j["detail"][:40],
        ])
    eval_data.append(["SCORE GLOBAL", f"{evaluation['score_global']}%", "100%",
                       evaluation["categorie"].upper(), ""])

    t2 = Table(eval_data, colWidths=[4*cm, 2*cm, 1.5*cm, 2*cm, 6.5*cm])
    row_colors = []
    for i, row in enumerate(eval_data):
        if i == 0:
            row_colors.append(("BACKGROUND", (0, i), (-1, i), NAUMUR_BLUE))
            row_colors.append(("TEXTCOLOR", (0, i), (-1, i), colors.white))
        elif i == len(eval_data) - 1:
            row_colors.append(("BACKGROUND", (0, i), (-1, i), _cat_color(evaluation["categorie"])))
            row_colors.append(("TEXTCOLOR", (0, i), (-1, i), colors.white))
    t2.setStyle(TableStyle([
        *row_colors,
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 4),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    elements.append(t2)

    # ── GENRE ──
    if "genre_distribution" in charts:
        elements.append(Spacer(1, 0.5 * cm))
        elements.append(Paragraph("5. Répartition par Genre", styles["SectionHead"]))
        elements.append(RLImage(charts["genre_distribution"], width=8 * cm, height=8 * cm))

    # ── COMPLETUDE ──
    if "completude_donnees" in charts:
        elements.append(Spacer(1, 0.5 * cm))
        elements.append(Paragraph("6. Complétude des Données", styles["SectionHead"]))
        elements.append(RLImage(charts["completude_donnees"], width=16 * cm, height=8 * cm))

    # ── ALERTES ──
    if evaluation["alertes"]:
        elements.append(PageBreak())
        elements.append(Paragraph("7. Alertes et Recommandations", styles["SectionHead"]))
        for a in evaluation["alertes"]:
            elements.append(Paragraph(f"⚠ {a}", styles["AlertStyle"]))
        elements.append(Spacer(1, 0.3 * cm))

    # ── INVESTMENT RECOMMENDATIONS ──
    if investment_recs:
        elements.append(Paragraph("8. Recommandations d'Investissement PADESCE", styles["SectionHead"]))
        type_icons = {"alerte": "!!", "attention": "!", "positif": "+",
                      "zone_risque": "ZONE", "sectoriel": ">>", "donnees": "DATA"}
        type_colors = {"alerte": FAIBLE_RED, "attention": MOYEN_ORANGE, "positif": EXCELLENT_GREEN,
                       "zone_risque": FAIBLE_RED, "sectoriel": NAUMUR_BLUE, "donnees": MOYEN_ORANGE}
        for rec in investment_recs:
            t = rec.get("type", "")
            c = type_colors.get(t, colors.grey)
            elements.append(Paragraph(
                f'<font color="{c.hexval()}" size="11"><b>[{type_icons.get(t, "?")}] {rec["titre"]}</b></font>',
                ParagraphStyle("RecTitle", spaceAfter=4)
            ))
            elements.append(Paragraph(rec["detail"], styles["BodyJustify"]))
            elements.append(Spacer(1, 0.3 * cm))

    # ── AI COMMENTARY ──
    if ai_commentary:
        elements.append(Paragraph("9. Analyse par l'Agent IA", styles["SectionHead"]))
        for para in ai_commentary.split("\n\n"):
            if para.strip():
                elements.append(Paragraph(para.strip(), styles["BodyJustify"]))
        elements.append(Spacer(1, 0.3 * cm))

    # ── FOOTER ──
    elements.append(Spacer(1, 1 * cm))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
    elements.append(Paragraph(
        f"Rapport généré automatiquement par l'Agent de Reporting NAUMUR — {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        styles["SmallCenter"]
    ))
    elements.append(Paragraph(
        "Ce rapport est confidentiel. Projet PADESCE — Banque Mondiale.",
        styles["SmallCenter"]
    ))

    doc.build(elements)
    return str(filepath)

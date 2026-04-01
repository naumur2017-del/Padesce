# agent_padesce/visualize.py
"""Visualisation du graphe LangGraph."""

import os
import traceback

from .config import EXPORTS_DIR, get_df
from .graph import build_graph


def visualize_graph(output_png: str = "graph_schema.png", show: bool = True) -> str:
    """Génère un PNG détaillé du graphe avec sous-graphes."""
    app = build_graph()
    
    _in_notebook = False
    try:
        from IPython import get_ipython
        if get_ipython() is not None:
            _in_notebook = True
    except ImportError:
        pass
    
    png_path = os.path.join(EXPORTS_DIR, output_png)
    
    # Essayer Mermaid d'abord
    try:
        img_bytes = app.get_graph(xray=True).draw_mermaid_png()
        with open(png_path, "wb") as f:
            f.write(img_bytes)
        print(f"[Graphe] Mermaid PNG → {png_path}")
        
        if show and _in_notebook:
            from IPython.display import Image, display
            display(Image(data=img_bytes))
        return png_path
    except Exception as e:
        print(f"[Graphe] Mermaid indisponible : {e}")
    
    # Fallback PIL avec design amélioré
    try:
        from PIL import Image as PILImage, ImageDraw, ImageFont
        
        W, H = 1000, 850
        img = PILImage.new('RGB', (W, H), color='#FAFAFA')
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
            font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
        except:
            font = font_bold = font_title = font_small = ImageFont.load_default()
        
        # Titre principal
        draw.text((W//2, 25), "AGENT LANGGRAPH v5 - PADESCE", fill="#1a1a2e", anchor="mm", font=font_title)
        draw.text((W//2, 45), "Architecture avec sous-graphes", fill="#666666", anchor="mm", font=font_small)
        
        # ═══════════════════════════════════════════════════════════════
        # GRAPHE PRINCIPAL (en haut)
        # ═══════════════════════════════════════════════════════════════
        draw.rounded_rectangle([20, 60, W-20, 200], radius=12, outline="#2d3436", width=2)
        draw.text((W//2, 80), "GRAPHE PRINCIPAL", fill="#2d3436", anchor="mm", font=font_bold)
        
        # Nœuds principaux
        nodes = [
            ("START", 80, 140, "#dfe6e9"),
            ("router", 200, 140, "#a29bfe"),
            ("fiche", 350, 120, "#00b894"),
            ("excel", 480, 120, "#0984e3"),
            ("question", 610, 120, "#fdcb6e"),
            ("hors_cadre", 760, 120, "#ff7675"),
            ("format", 550, 175, "#81ecec"),
            ("END", 700, 175, "#dfe6e9"),
        ]
        
        # Dessiner les connexions
        connections = [
            (80, 140, 200, 140), (200, 140, 350, 120), (200, 140, 480, 120),
            (200, 140, 610, 120), (200, 140, 760, 120),
            (350, 120, 550, 175), (480, 120, 550, 175), (610, 120, 550, 175), (760, 120, 550, 175),
            (550, 175, 700, 175),
        ]
        for x1, y1, x2, y2 in connections:
            draw.line([(x1+30, y1), (x2-30, y2)], fill="#636e72", width=2)
        
        # Dessiner les nœuds
        for name, x, y, color in nodes:
            if name in ["START", "END"]:
                draw.ellipse([x-25, y-14, x+25, y+14], fill=color, outline="#2d3436", width=2)
            else:
                draw.rounded_rectangle([x-38, y-16, x+38, y+16], radius=8, fill=color, outline="#2d3436", width=1)
            draw.text((x, y), name, fill="#2d3436", anchor="mm", font=font)
        
        # ═══════════════════════════════════════════════════════════════
        # SOUS-GRAPHE FICHE (vert)
        # ═══════════════════════════════════════════════════════════════
        draw.rounded_rectangle([20, 220, 260, 460], radius=12, outline="#00b894", width=3)
        draw.rectangle([20, 220, 260, 255], fill="#00b894")
        draw.text((140, 237), "🟢 PIPELINE FICHE", fill="white", anchor="mm", font=font_bold)
        draw.text((140, 270), "(Déterministe)", fill="#00b894", anchor="mm", font=font_small)
        
        steps_fiche = [
            ("① Correction ortho", 295),
            ("② extraire_infos()", 325),
            ("③ filtrer_classes()", 355),
            ("④ generer_rapport_excel()", 385),
            ("→ fiche_XXX.xlsx", 420),
        ]
        for label, y in steps_fiche:
            draw.rounded_rectangle([35, y-12, 245, y+12], radius=5, fill="#d5f5e3", outline="#00b894")
            draw.text((140, y), label, fill="#00b894", anchor="mm", font=font_small)
        
        # ═══════════════════════════════════════════════════════════════
        # SOUS-GRAPHE EXCEL (bleu)
        # ═══════════════════════════════════════════════════════════════
        draw.rounded_rectangle([280, 220, 510, 460], radius=12, outline="#0984e3", width=3)
        draw.rectangle([280, 220, 510, 255], fill="#0984e3")
        draw.text((395, 237), "🔵 PIPELINE EXCEL", fill="white", anchor="mm", font=font_bold)
        draw.text((395, 270), "(Génération de code)", fill="#0984e3", anchor="mm", font=font_small)
        
        steps_excel = [
            ("① Analyser schéma", 295),
            ("② Détecter entités", 325),
            ("③ Générer code pandas", 355),
            ("④ Exécuter code", 385),
            ("→ export_XXX.xlsx", 420),
        ]
        for label, y in steps_excel:
            draw.rounded_rectangle([295, y-12, 495, y+12], radius=5, fill="#d6eaf8", outline="#0984e3")
            draw.text((395, y), label, fill="#0984e3", anchor="mm", font=font_small)
        
        # ═══════════════════════════════════════════════════════════════
        # SOUS-GRAPHE QUESTION (jaune)
        # ═══════════════════════════════════════════════════════════════
        draw.rounded_rectangle([530, 220, 760, 460], radius=12, outline="#f39c12", width=3)
        draw.rectangle([530, 220, 760, 255], fill="#f39c12")
        draw.text((645, 237), "🟡 PIPELINE QUESTION", fill="white", anchor="mm", font=font_bold)
        draw.text((645, 270), "(Génération de code)", fill="#f39c12", anchor="mm", font=font_small)
        
        steps_question = [
            ("① Analyser schéma", 295),
            ("② Détecter filtres", 325),
            ("③ Générer code pandas", 355),
            ("④ Exécuter & calculer", 385),
            ("→ Réponse naturelle", 420),
        ]
        for label, y in steps_question:
            draw.rounded_rectangle([545, y-12, 745, y+12], radius=5, fill="#fef9e7", outline="#f39c12")
            draw.text((645, y), label, fill="#b7950b", anchor="mm", font=font_small)
        
        # ═══════════════════════════════════════════════════════════════
        # SOUS-GRAPHE HORS CADRE (rouge)
        # ═══════════════════════════════════════════════════════════════
        draw.rounded_rectangle([780, 220, 980, 460], radius=12, outline="#e74c3c", width=3)
        draw.rectangle([780, 220, 980, 255], fill="#e74c3c")
        draw.text((880, 237), "🔴 HORS CADRE", fill="white", anchor="mm", font=font_bold)
        draw.text((880, 270), "(Signalement)", fill="#e74c3c", anchor="mm", font=font_small)
        
        steps_hors = [
            ("Demande non reconnue", 310),
            ("Message explicatif", 350),
            ("Exemples de prompts", 390),
        ]
        for label, y in steps_hors:
            draw.rounded_rectangle([795, y-15, 965, y+15], radius=5, fill="#fadbd8", outline="#e74c3c")
            draw.text((880, y), label, fill="#c0392b", anchor="mm", font=font_small)
        
        # ═══════════════════════════════════════════════════════════════
        # EXEMPLES DE PROMPTS (en bas)
        # ═══════════════════════════════════════════════════════════════
        draw.rounded_rectangle([20, 480, W-20, 680], radius=12, outline="#2d3436", width=1)
        draw.text((W//2, 500), "EXEMPLES DE PROMPTS PAR ROUTE", fill="#2d3436", anchor="mm", font=font_bold)
        
        examples_data = [
            ("🟢 FICHE", ["Fiche de CEW", "Prestations de l'Extrême Nord", "Rapport du prestataire MINEFOP"], "#00b894", 120),
            ("🔵 EXCEL", ["Excel des prestataires de F1", "Fichier avec colonnes X, Y", "Export filtré statut TERMINÉ"], "#0984e3", 360),
            ("🟡 QUESTION", ["Combien de prestataires ?", "Répartition par statut", "Total inscrits par région"], "#f39c12", 600),
            ("🔴 HORS CADRE", ["Quelle est la météo ?", "Écris-moi un poème"], "#e74c3c", 860),
        ]
        
        for title, prompts, color, x in examples_data:
            draw.text((x, 530), title, fill=color, anchor="mm", font=font)
            for i, p in enumerate(prompts):
                draw.text((x, 555 + i*22), f"• {p}", fill="#636e72", anchor="mm", font=font_small)
        
        # ═══════════════════════════════════════════════════════════════
        # SCHÉMA DES DONNÉES (aperçu)
        # ═══════════════════════════════════════════════════════════════
        draw.rounded_rectangle([20, 700, W-20, 830], radius=12, outline="#6c5ce7", width=2)
        draw.rectangle([20, 700, W-20, 730], fill="#6c5ce7")
        draw.text((W//2, 715), "📊 SCHÉMA DES DONNÉES", fill="white", anchor="mm", font=font_bold)
        
        decompte = get_df("decompte")
        classe = get_df("classe")
        
        if decompte is not None:
            cols_dec = list(decompte.columns)[:8]
            draw.text((40, 750), f"decompte ({decompte.shape[0]} lignes) :", fill="#6c5ce7", anchor="lm", font=font)
            draw.text((40, 770), ", ".join(cols_dec) + "...", fill="#636e72", anchor="lm", font=font_small)
        
        if classe is not None:
            cols_cls = list(classe.columns)[:6]
            draw.text((40, 800), f"classe ({classe.shape[0]} lignes) :", fill="#6c5ce7", anchor="lm", font=font)
            draw.text((40, 820), ", ".join(str(c) for c in cols_cls) + "...", fill="#636e72", anchor="lm", font=font_small)
        
        draw.text((W//2, 845), f"📁 Exports → {EXPORTS_DIR}/", fill="#636e72", anchor="mm", font=font_small)
        
        # Sauvegarder
        img.save(png_path)
        print(f"[Graphe] PIL PNG → {png_path}")
        
        if show and _in_notebook:
            from IPython.display import Image, display
            display(Image(filename=png_path))
        elif show:
            img.show()
        
        return png_path
        
    except Exception as e:
        print(f"[Graphe] Erreur PIL : {e}")
        traceback.print_exc()
        return ""

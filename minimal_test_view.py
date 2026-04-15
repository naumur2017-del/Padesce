#!/usr/bin/env python3
"""
Crée une vue de test minimale pour isoler le problème de l'erreur 500
"""

import os
import sys
import django
from django.conf import settings

def setup_django():
    """Configure Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
    django.setup()

def create_minimal_test_view():
    """Crée une vue de test minimale"""
    
    minimal_view_code = '''
def test_formateur_stats_minimal(request):
    """
    Vue de test minimale pour isoler l'erreur 500
    """
    from django.http import HttpResponse
    
    try:
        # Retourner une réponse HTML simple
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Stats Formateurs</title>
        </head>
        <body>
            <h1>Test Page - Stats Formateurs</h1>
            <p>Ceci est une page de test pour vérifier si le problème vient de la vue ou du template.</p>
            <p>Si vous voyez cette page, le problème n'est pas dans la vue elle-même.</p>
            <p>Status: OK</p>
        </body>
        </html>
        """
        return HttpResponse(html_content)
    except Exception as e:
        # En cas d'erreur, retourner une réponse d'erreur simple
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Erreur</title>
        </head>
        <body>
            <h1>Erreur dans la vue de test</h1>
            <p>Erreur: {e}</p>
        </body>
        </html>
        """
        return HttpResponse(error_html, status=500)

def test_formateur_stats_with_template(request):
    """
    Vue de test qui utilise le template mais avec des données minimales
    """
    from django.shortcuts import render
    
    try:
        # Context minimal
        context = {
            "scope": "formateur",
            "section": "stats",
            "stats": {
                "global_avgs": {},
                "best_rankings": [
                    {"code": "TEST001", "score_global": 95.0, "intitule": "Test Formation 1"},
                    {"code": "TEST002", "score_global": 90.0, "intitule": "Test Formation 2"},
                    {"code": "TEST003", "score_global": 85.0, "intitule": "Test Formation 3"},
                    {"code": "TEST004", "score_global": 80.0, "intitule": "Test Formation 4"},
                    {"code": "TEST005", "score_global": 75.0, "intitule": "Test Formation 5"},
                ],
                "improve_rankings": [
                    {"code": "TEST006", "score_global": 65.0, "intitule": "Test Formation 6"},
                    {"code": "TEST007", "score_global": 70.0, "intitule": "Test Formation 7"},
                    {"code": "TEST008", "score_global": 72.0, "intitule": "Test Formation 8"},
                    {"code": "TEST009", "score_global": 74.0, "intitule": "Test Formation 9"},
                    {"code": "TEST010", "score_global": 76.0, "intitule": "Test Formation 10"},
                ],
                "map_data": {},
                "summary_cards": [
                    ("Moyenne Q1-Q3", 80.0),
                    ("Appels", 100),
                    ("Appels ciblés", 90),
                    ("Avec scores", 85),
                ],
            },
            "page_tabs": [],
            "scope_tabs": [],
            "login_url": "/login/",
        }
        
        return render(request, "core/public_space.html", context)
        
    except Exception as e:
        from django.http import HttpResponse
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Erreur Template</title>
        </head>
        <body>
            <h1>Erreur avec le template</h1>
            <p>Erreur: {e}</p>
        </body>
        </html>
        """
        return HttpResponse(error_html, status=500)
'''
    
    return minimal_view_code

def add_test_views_to_urls():
    """Ajoute les vues de test au fichier URLs"""
    
    print("=== AJOUT DES VUES DE TEST AU FICHIER URLS ===\n")
    
    try:
        # Lire le fichier urls.py principal
        urls_file = 'App_PADESCE/urls.py'
        
        with open(urls_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier si les vues de test sont déjà ajoutées
        if 'test_formateur_stats_minimal' in content:
            print("Vues de test déjà présentes dans urls.py")
            return True
        
        # Ajouter les imports et les URLs de test
        import_section = '''
# Vues de test pour diagnostiquer l'erreur 500
from App_PADESCE.core.public_views import test_formateur_stats_minimal, test_formateur_stats_with_template
'''
        
        url_patterns_section = '''
    # URLs de test pour diagnostiquer l'erreur 500
    path('test-stats-minimal/', test_formateur_stats_minimal, name='test_stats_minimal'),
    path('test-stats-template/', test_formateur_stats_with_template, name='test_stats_template'),
'''
        
        # Ajouter l'import
        content = import_section + content
        
        # Trouver où ajouter les URLs (juste avant la fin de urlpatterns)
        urlpatterns_end = content.find(']')
        if urlpatterns_end != -1:
            content = content[:urlpatterns_end] + url_patterns_section + content[urlpatterns_end:]
        
        # Écrire le fichier modifié
        with open(urls_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("Vues de test ajoutées à urls.py")
        print("URLs de test disponibles:")
        print("- http://127.0.0.1:8000/test-stats-minimal/")
        print("- http://127.0.0.1:8000/test-stats-template/")
        
        return True
        
    except Exception as e:
        print(f"ERREUR LORS DE L'AJOUT DES VUES DE TEST: {e}")
        import traceback
        traceback.print_exc()
        return False

def add_test_views_to_public_views():
    """Ajoute les vues de test au fichier public_views.py"""
    
    print("=== AJOUT DES VUES DE TEST AU FICHIER public_views.py ===\n")
    
    try:
        # Lire le fichier public_views.py
        views_file = 'App_PADESCE/core/public_views.py'
        
        with open(views_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier si les vues sont déjà ajoutées
        if 'def test_formateur_stats_minimal' in content:
            print("Vues de test déjà présentes dans public_views.py")
            return True
        
        # Ajouter les vues de test à la fin du fichier
        test_views_code = create_minimal_test_view()
        
        # Trouver la fin du fichier (avant la dernière ligne vide)
        content = content.rstrip() + '\n\n' + test_views_code + '\n'
        
        # Écrire le fichier modifié
        with open(views_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("Vues de test ajoutées à public_views.py")
        return True
        
    except Exception as e:
        print(f"ERREUR LORS DE L'AJOUT DES VUES DE TEST: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    setup_django()
    
    print("CRÉATION DE VUES DE TEST POUR ISOLER L'ERREUR 500\n")
    
    # Ajouter les vues de test
    success1 = add_test_views_to_public_views()
    success2 = add_test_views_to_urls()
    
    if success1 and success2:
        print("\n" + "="*60)
        print("SUCCÈS: Vues de test créées")
        print("\nPROCHAINES ÉTAPES:")
        print("1. git add .")
        print("2. git commit -m 'Add test views to diagnose 500 error'")
        print("3. git push origin main")
        print("\nAprès déploiement, testez:")
        print("- https://call.naumur.com/test-stats-minimal/")
        print("- https://call.naumur.com/test-stats-template/")
        print("\nSi ces URLs fonctionnent, le problème est dans _build_formateur_stats.")
        print("Si elles ne fonctionnent pas, le problème est plus profond.")
    else:
        print("\nÉCHEC: Impossible de créer les vues de test")
        sys.exit(1)

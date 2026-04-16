#!/usr/bin/env python3
"""
Crée une vue de debug pour tester directement la fonction de stats
et isoler le problème de production
"""

import os
import sys
import django
from django.conf import settings

def setup_django():
    """Configure Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
    django.setup()

def create_debug_view():
    """Crée une vue de debug"""
    
    debug_view_code = '''
def debug_formateur_stats(request):
    """
    Vue de debug pour tester directement la fonction de stats
    """
    from django.http import HttpResponse
    import json
    
    try:
        # Tester la fonction simple
        result = _build_formateur_stats_simple(request)
        
        # Créer une réponse HTML avec les résultats
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Debug Formateur Stats</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .success {{ color: green; }}
                .error {{ color: red; }}
                .data {{ background: #f5f5f5; padding: 10px; margin: 10px 0; }}
                pre {{ white-space: pre-wrap; }}
            </style>
        </head>
        <body>
            <h1>Debug Formateur Stats</h1>
            
            <div class="success">
                <h2>Function executed successfully!</h2>
            </div>
            
            <div class="data">
                <h3>Result Data:</h3>
                <pre>{json.dumps(result, indent=2, default=str)}</pre>
            </div>
            
            <div class="data">
                <h3>Best Rankings ({len(result.get('best_rankings', []))}):</h3>
                <ul>
        """
        
        for item in result.get('best_rankings', []):
            html_content += f"<li>{item.get('code', 'N/A')} - {item.get('score_global', 'N/A')}</li>"
        
        html_content += f"""
                </ul>
            </div>
            
            <div class="data">
                <h3>Improve Rankings ({len(result.get('improve_rankings', []))}):</h3>
                <ul>
        """
        
        for item in result.get('improve_rankings', []):
            html_content += f"<li>{item.get('code', 'N/A')} - {item.get('score_global', 'N/A')}</li>"
        
        html_content += f"""
                </ul>
            </div>
            
            <div class="data">
                <h3>Summary Cards:</h3>
                <ul>
        """
        
        for item in result.get('summary_cards', []):
            html_content += f"<li>{item}</li>"
        
        html_content += f"""
                </ul>
            </div>
            
            <p><a href="/?scope=formateur&section=stats">Retour à la page normale</a></p>
        </body>
        </html>
        """
        
        return HttpResponse(html_content)
        
    except Exception as e:
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Debug Error</title>
        </head>
        <body>
            <h1>Debug Error</h1>
            <div class="error">
                <h2>Error: {e}</h2>
                <pre>{__import__('traceback').format_exc()}</pre>
            </div>
            <p><a href="/?scope=formateur&section=stats">Retour à la page normale</a></p>
        </body>
        </html>
        """
        return HttpResponse(error_html, status=500)
'''
    
    return debug_view_code

def add_debug_view_to_urls():
    """Ajoute la vue de debug au fichier URLs"""
    
    print("=== AJOUT DE LA VUE DE DEBUG ===\n")
    
    try:
        # Lire le fichier urls.py
        urls_file = 'App_PADESCE/urls.py'
        
        with open(urls_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier si la vue de debug est déjà ajoutée
        if 'debug_formateur_stats' in content:
            print("Vue de debug déjà présente dans urls.py")
            return True
        
        # Ajouter l'import et l'URL
        import_section = '''
# Vue de debug pour les stats formateurs
from App_PADESCE.core.public_views import debug_formateur_stats
'''
        
        url_section = '''
    # URL de debug pour les stats formateurs
    path('debug-formateur-stats/', debug_formateur_stats, name='debug_formateur_stats'),
'''
        
        # Ajouter l'import
        content = import_section + content
        
        # Trouver où ajouter l'URL
        urlpatterns_end = content.find(']')
        if urlpatterns_end != -1:
            content = content[:urlpatterns_end] + url_section + content[urlpatterns_end:]
        
        # Écrire le fichier modifié
        with open(urls_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("Vue de debug ajoutée à urls.py")
        print("URL de debug disponible: http://127.0.0.1:8000/debug-formateur-stats/")
        
        return True
        
    except Exception as e:
        print(f"ERREUR LORS DE L'AJOUT DE LA VUE DE DEBUG: {e}")
        import traceback
        traceback.print_exc()
        return False

def add_debug_view_to_public_views():
    """Ajoute la vue de debug au fichier public_views.py"""
    
    print("=== AJOUT DE LA VUE DE DEBUG À public_views.py ===\n")
    
    try:
        # Lire le fichier public_views.py
        views_file = 'App_PADESCE/core/public_views.py'
        
        with open(views_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier si la vue est déjà ajoutée
        if 'def debug_formateur_stats' in content:
            print("Vue de debug déjà présente dans public_views.py")
            return True
        
        # Ajouter la vue de debug à la fin du fichier
        debug_view = create_debug_view()
        
        # Trouver la fin du fichier
        content = content.rstrip() + '\n\n' + debug_view + '\n'
        
        # Écrire le fichier modifié
        with open(views_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("Vue de debug ajoutée à public_views.py")
        return True
        
    except Exception as e:
        print(f"ERREUR LORS DE L'AJOUT DE LA VUE DE DEBUG: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    setup_django()
    
    print("CRÉATION DE LA VUE DE DEBUG\n")
    
    # Ajouter la vue de debug
    success1 = add_debug_view_to_public_views()
    success2 = add_debug_view_to_urls()
    
    if success1 and success2:
        print("\n" + "="*60)
        print("SUCCÈS: Vue de debug créée")
        print("\nPROCHAINES ÉTAPES:")
        print("1. git add .")
        print("2. git commit -m 'Add debug view for formateur stats'")
        print("3. git push origin main")
        print("\nAprès déploiement, testez:")
        print("- https://call.naumur.com/debug-formateur-stats/")
        print("\nCette vue montrera exactement ce que retourne la fonction.")
    else:
        print("\nÉCHEC: Impossible de créer la vue de debug")
        sys.exit(1)

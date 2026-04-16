#!/usr/bin/env python3
"""
Crée une vue de debug pour afficher le contenu du contexte
et diagnostiquer pourquoi les données ne sont pas passées au template
"""

import os
import sys
import django
from django.conf import settings

def setup_django():
    """Configure Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'App_PADESCE.settings')
    django.setup()

def create_context_debug_view():
    """Crée une vue de debug du contexte"""
    
    context_debug_code = '''
def debug_context_stats(request):
    """
    Vue de debug pour afficher le contexte passé au template
    """
    from django.http import HttpResponse
    import json
    
    try:
        # Simuler exactement ce que fait la vue principale
        scope = request.GET.get("scope", "apprenant")
        section = request.GET.get("section", "principal")
        
        context = {}
        
        # Ajouter les onglets
        context["page_tabs"] = [
            {
                "label": "Principal",
                "value": "principal",
                "active": section == "principal",
                "url": _public_space_url(section="principal", scope=scope),
            },
            {
                "label": "Apercu",
                "value": "apercu",
                "active": section == "apercu",
                "url": _public_space_url(section="apercu", scope=scope),
            },
            {
                "label": "Stats",
                "value": "stats",
                "active": section == "stats",
                "url": _public_space_url(section="stats", scope=scope),
            },
        ]
        context["scope_tabs"] = [
            {
                "label": "Apprenant",
                "value": "apprenant",
                "active": scope == "apprenant",
                "url": _public_space_url(section=section, scope="apprenant"),
            },
            {
                "label": "Formateur",
                "value": "formateur",
                "active": scope == "formateur",
                "url": _public_space_url(section=section, scope="formateur"),
            },
        ]
        context["login_url"] = _login_url_for(request)
        
        # Ajouter les données de stats si c'est la bonne section
        if scope == "formateur" and section == "stats":
            print("DEBUG: Ajout des stats au contexte")
            stats_data = _build_formateur_stats_ultra_simple(request)
            print(f"DEBUG: stats_data = {stats_data}")
            context["stats"] = stats_data
            print(f"DEBUG: context['stats'] = {context.get('stats')}")
        else:
            print(f"DEBUG: Pas de stats - scope={scope}, section={section}")
        
        # Créer une réponse HTML avec le contexte
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Debug Context Stats</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .success {{ color: green; }}
                .error {{ color: red; }}
                .data {{ background: #f5f5f5; padding: 10px; margin: 10px 0; }}
                pre {{ white-space: pre-wrap; }}
            </style>
        </head>
        <body>
            <h1>Debug Context Stats</h1>
            
            <div class="data">
                <h2>Request Parameters:</h2>
                <p>Scope: {scope}</p>
                <p>Section: {section}</p>
            </div>
            
            <div class="data">
                <h2>Context Keys:</h2>
                <ul>
        """
        
        for key in context.keys():
            value = context[key]
            if key == "stats":
                html_content += f"<li><strong>{key}</strong>: {type(value)} - {len(value.get('best_rankings', []))} best_rankings</li>"
            else:
                html_content += f"<li><strong>{key}</strong>: {type(value)}</li>"
        
        html_content += f"""
                </ul>
            </div>
            
            <div class="data">
                <h2>Stats Data:</h2>
        """
        
        if "stats" in context:
            stats = context["stats"]
            html_content += f"""
                <p>Best Rankings: {len(stats.get('best_rankings', []))}</p>
                <p>Improve Rankings: {len(stats.get('improve_rankings', []))}</p>
                <p>Summary Cards: {len(stats.get('summary_cards', []))}</p>
                
                <h3>Best Rankings Content:</h3>
                <ul>
            """
            
            for item in stats.get('best_rankings', []):
                html_content += f"<li>{item.get('code', 'N/A')} - {item.get('score_global', 'N/A')}</li>"
            
            html_content += """
                </ul>
            </div>
        """
        else:
            html_content += "<p>No stats in context!</p>"
        
        html_content += f"""
            <p><a href='/?scope=formateur&section=stats'>Retour à la page normale</a></p>
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
            <p><a href='/?scope=formateur&section=stats'>Retour à la page normale</a></p>
        </body>
        </html>
        """
        return HttpResponse(error_html, status=500)
'''
    
    return context_debug_code

def add_context_debug_view():
    """Ajoute la vue de debug du contexte"""
    
    print("=== AJOUT DE LA VUE DE DEBUG CONTEXTE ===\n")
    
    try:
        # Lire le fichier public_views.py
        views_file = 'App_PADESCE/core/public_views.py'
        
        with open(views_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier si la vue est déjà ajoutée
        if 'def debug_context_stats' in content:
            print("Vue de debug contexte déjà présente")
            return True
        
        # Ajouter la vue de debug à la fin du fichier
        debug_view = create_context_debug_view()
        
        # Trouver la fin du fichier
        content = content.rstrip() + '\n\n' + debug_view + '\n'
        
        # Écrire le fichier modifié
        with open(views_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("Vue de debug contexte ajoutée")
        
        # Ajouter l'URL
        urls_file = 'App_PADESCE/urls.py'
        with open(urls_file, 'r', encoding='utf-8') as f:
            urls_content = f.read()
        
        if 'debug_context_stats' not in urls_content:
            import_section = '''
# Vue de debug du contexte
from App_PADESCE.core.public_views import debug_context_stats
'''
            url_section = '''
    path('debug-context-stats/', debug_context_stats, name='debug_context_stats'),
'''
            
            urls_content = import_section + urls_content
            urlpatterns_end = urls_content.find(']')
            if urlpatterns_end != -1:
                urls_content = urls_content[:urlpatterns_end] + url_section + urls_content[urlpatterns_end:]
            
            with open(urls_file, 'w', encoding='utf-8') as f:
                f.write(urls_content)
            
            print("URL de debug contexte ajoutée")
        
        return True
        
    except Exception as e:
        print(f"ERREUR LORS DE L'AJOUT: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    setup_django()
    
    print("CRÉATION DE LA VUE DE DEBUG CONTEXTE\n")
    
    if add_context_debug_view():
        print("\n" + "="*60)
        print("SOLUTION APPLIQUÉE")
        print("\nPROCHAINES ÉTAPES:")
        print("1. git add .")
        print("2. git commit -m 'Add context debug view'")
        print("3. git push origin main")
        print("\nAprès déploiement, testez:")
        print("- https://call.naumur.com/debug-context-stats/?scope=formateur&section=stats")
        print("\nCette vue montrera exactement ce qui est dans le contexte.")
    else:
        print("\nÉCHEC")
        sys.exit(1)

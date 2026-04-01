import json
import os
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

# Variable globale pour l'initialisation paresseuse de l'agent
_agent_initialized = False

def init_agent_if_needed():
    global _agent_initialized
    if not _agent_initialized:
        print("[Agent Padesce] Initialisation du chat...")
        try:
            # Import lazy de torch pour éviter un crash au démarrage si non installé
            try:
                import torch  # noqa: F401  # Fix for [WinError 1114] DLL init in thread
            except ImportError:
                pass

            # Charger les clés d'API depuis NAUMUR/.env s'il n'est pas déjà chargé
            env_path = os.path.join(settings.BASE_DIR.parent.parent, ".env")
            if os.path.exists(env_path):
                print(f"[Agent Padesce] Chargement du .env depuis {env_path}")
                for line in open(env_path, 'r', encoding='utf-8'):
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split("=", 1)
                        if k not in os.environ:
                            os.environ[k.strip()] = v.strip().strip("'\"")

            # Import de l'agent
            from agent_padesceV2 import configure_memory, load_data, register_dataframes
            
            # Configuration de la mémoire
            configure_memory(enabled=True, max_conversations=5)
            
            # Recherche du fichier de données
            file_path = "Decompte et facturation.xlsm"
            if not os.path.exists(file_path):
                # Tentative avec chemin absolu depuis la racine du projet Django
                file_path = os.path.join(settings.BASE_DIR, "Decompte et facturation.xlsm")
            
            if os.path.exists(file_path):
                print(f"[Agent Padesce] Chargement des données depuis {file_path}...")
                dfs = load_data(file_path)
                register_dataframes(dfs)
                print("[Agent Padesce] Initialisation terminée.")
            else:
                print(f"[Agent Padesce] AVERTISSEMENT : Fichier {file_path} introuvable.")
                
        except ImportError as e:
            print(f"[Agent Padesce] ERREUR d'importation : {e}")
            raise e
        except Exception as e:
            print(f"[Agent Padesce] ERREUR d'initialisation : {e}")
            raise e
            
        _agent_initialized = True

@csrf_exempt
@require_POST
def chat_query(request):
    """Point d'entrée de l'API REST pour le chat."""
    try:
        data = json.loads(request.body)
        message = data.get("message", "").strip()
        
        if not message:
            return JsonResponse({"error": "Message vide"}, status=400)
            
        # S'assurer que l'agent est chargé en mémoire
        init_agent_if_needed()
        
        # Appel de l'agent
        from agent_padesceV2 import run_agent
        result = run_agent(message)
        
        # Extraction des résultats
        reponse = result.get("reponse", "Désolé, je n'ai pas pu formuler de réponse.")
        fichier = result.get("fichier", "")
        
        # Le nom du fichier est juste la fin du chemin d'accès (s'il y en a un)
        filename = os.path.basename(fichier) if fichier else None
        
        return JsonResponse({
            "response": reponse,
            "filename": filename
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)

def download_export(request, filename):
    """Point de téléchargement pour les fichiers générés par l'agent."""
    # Le dossier exports est configuré dans l'agent.
    # On le cherche d'abord dans BASE_DIR/exports ou dans le dossier courant
    
    export_dir = os.path.join(settings.BASE_DIR, "exports")
    if not os.path.exists(export_dir):
        export_dir = os.path.join(os.getcwd(), "exports")
        
    file_path = os.path.join(export_dir, filename)
    
    # Securité basique : interdire les chemins relatifs dangereux
    if ".." in filename or "/" in filename or "\\" in filename:
        raise Http404("Fichier invalide")
        
    if not os.path.exists(file_path):
        raise Http404(f"Fichier {filename} introuvable")
        
    response = FileResponse(open(file_path, 'rb'), as_attachment=True, filename=filename)
    return response

import json
import logging
import os
import sys
import traceback as _tb

from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


def _safe_log(message: str) -> None:
    """Log sans jamais lever en cas de stdout non-UTF-8 (gunicorn/Gandi)."""
    try:
        logger.info(message)
    except Exception:
        pass
    try:
        sys.stdout.write(message + "\n")
        sys.stdout.flush()
    except Exception:
        # Stdout peut être en ASCII strict sous certains WSGI : ignorer.
        pass


def _ensure_stdout_utf8() -> None:
    """Force stdout/stderr en UTF-8 quand c'est possible (Python >= 3.7)."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfig = getattr(stream, "reconfigure", None)
        if callable(reconfig):
            try:
                reconfig(encoding="utf-8", errors="replace")
            except Exception:
                pass

# Pré-charger torch sur le thread principal pour éviter [WinError 1114]
# sur Windows. En production (Linux), ce n'est pas nécessaire mais ne
# pose aucun problème. Si torch n'est pas installé, on ignore silencieusement.
try:
    import torch  # noqa: F401
except Exception:
    pass

# Variable globale pour l'initialisation paresseuse de l'agent
_agent_initialized = False


def init_agent_if_needed():
    global _agent_initialized
    if not _agent_initialized:
        _ensure_stdout_utf8()
        _safe_log("[Agent Padesce] Initialisation du chat...")
        try:
            # Charger les clés d'API depuis .env
            env_paths = [
                os.path.join(settings.BASE_DIR, ".env"),
                os.path.join(settings.BASE_DIR.parent, ".env"),
                os.path.join(settings.BASE_DIR.parent.parent, ".env"),
            ]
            for env_path in env_paths:
                if os.path.exists(env_path):
                    _safe_log(f"[Agent Padesce] Chargement du .env depuis {env_path}")
                    # Certains .env en prod contiennent des octets non-UTF-8
                    # (apostrophes typographiques Windows-1252, BOM, etc.).
                    # On tente plusieurs encodages avant d'ignorer les octets
                    # invalides pour éviter un UnicodeDecodeError bloquant.
                    env_content = None
                    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
                        try:
                            with open(env_path, "r", encoding=enc) as fh:
                                env_content = fh.read()
                            break
                        except UnicodeDecodeError:
                            continue
                    if env_content is None:
                        with open(env_path, "rb") as fh:
                            env_content = fh.read().decode("utf-8", errors="replace")
                    for line in env_content.splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            if k not in os.environ:
                                os.environ[k.strip()] = v.strip().strip("'\"")
                    break

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
                _safe_log(f"[Agent Padesce] Chargement des donnees depuis {file_path}...")
                dfs = load_data(file_path)
                register_dataframes(dfs)
                _safe_log("[Agent Padesce] Initialisation terminee.")
            else:
                _safe_log(
                    f"[Agent Padesce] AVERTISSEMENT : Fichier {file_path} introuvable."
                )

        except ImportError as e:
            _safe_log(f"[Agent Padesce] ERREUR d'importation : {e}")
            raise e
        except Exception as e:
            _safe_log(f"[Agent Padesce] ERREUR d'initialisation : {e}")
            raise e

        _agent_initialized = True


@csrf_exempt
@require_POST
def chat_query(request):
    """Point d'entrée de l'API REST pour le chat."""
    try:
        _ensure_stdout_utf8()
        data = json.loads(request.body)
        message = data.get("message", "").strip()

        if not message:
            return JsonResponse({"error": "Message vide"}, status=400)

        # S'assurer que l'agent est chargé en mémoire
        init_agent_if_needed()

        # Appel de l'agent. verbose=False pour éviter que les `print`
        # avec emojis ne déclenchent une OSError (« [Errno 22] Invalid
        # argument ») sur un stdout non-UTF-8 sous gunicorn/Gandi.
        from agent_padesceV2 import run_agent

        try:
            result = run_agent(message, verbose=False)
        except TypeError:
            # Signature héritée sans paramètre verbose.
            result = run_agent(message)

        # Extraction des résultats
        reponse = result.get("reponse", "Désolé, je n'ai pas pu formuler de réponse.")
        fichier = result.get("fichier", "")

        # Le nom du fichier est juste la fin du chemin d'accès (s'il y en a un)
        filename = os.path.basename(fichier) if fichier else None

        return JsonResponse({"response": reponse, "filename": filename})

    except Exception as e:
        # Log complet côté serveur (sans jamais casser la requête).
        try:
            logger.exception("[Agent Padesce] Erreur chat_query")
        except Exception:
            pass
        try:
            _tb.print_exc()
        except Exception:
            pass
        # On renvoie aussi la dernière ligne utile de la stack pour que
        # le message affiché dans le widget indique le fichier/ligne
        # source et permette de diagnostiquer en prod sans accès logs.
        tb_tail = ""
        try:
            frames = _tb.extract_tb(e.__traceback__)
            last = None
            for fr in frames:
                path = (fr.filename or "").replace("\\", "/")
                if "/django/" in path or path.endswith("/chat_views.py"):
                    continue
                last = fr
            if last is None and frames:
                last = frames[-1]
            if last is not None:
                short = os.path.basename(last.filename or "")
                tb_tail = f" [{short}:{last.lineno} in {last.name}]"
        except Exception:
            pass
        detail = f"{type(e).__name__}: {e}{tb_tail}"
        return JsonResponse({"error": detail}, status=500)


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

    response = FileResponse(open(file_path, "rb"), as_attachment=True, filename=filename)
    return response

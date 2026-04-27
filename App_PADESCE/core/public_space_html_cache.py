"""
Cache HTML figé pour la page "Espace PADESCE".

Objectif : éviter de recalculer les dashboards (apprenant/formateur) à chaque
requête. Le rendu complet est sauvegardé sur disque et renvoyé tel quel aux
visiteurs. Un ``management command`` (``rebuild_public_space_html``) ou un
superuser via ``?refresh=1`` peuvent déclencher le recalcul.

Clé de cache : ``(scope, section, auth)`` où ``auth`` vaut ``anon`` ou
``auth`` selon l'état de connexion, car le template injecte un bouton
différent (Login / Dashboard) pour ces deux cas.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

PUBLIC_SCOPE_CHOICES = ("apprenant", "formateur")
PUBLIC_SECTION_CHOICES = ("principal", "apercu", "stats")
AUTH_VARIANTS = ("anon", "auth")


def _candidate_roots() -> list[Path]:
    env_location = str(os.getenv("PADESCE_PUBLIC_SPACE_HTML_DIR", "") or "").strip()
    candidates = [
        Path(env_location) if env_location else None,
        Path(getattr(settings, "BASE_DIR", ".")) / "data" / "public_space_html",
        Path(tempfile.gettempdir()) / "padesce-public-space-html",
    ]
    return [c for c in candidates if c is not None]


def snapshot_root() -> Path:
    """Retourne un dossier existant (créé si besoin) pour les snapshots HTML."""
    last_error: Exception | None = None
    for candidate in _candidate_roots():
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError as exc:
            last_error = exc
            continue
    raise RuntimeError(
        "Impossible d'initialiser le dossier de snapshots HTML Espace PADESCE."
    ) from last_error


def auth_variant_for(request) -> str:
    user = getattr(request, "user", None)
    if user is not None and bool(getattr(user, "is_authenticated", False)):
        return "auth"
    return "anon"


def snapshot_path(scope: str, section: str, auth: str) -> Path:
    scope = scope if scope in PUBLIC_SCOPE_CHOICES else "apprenant"
    section = section if section in PUBLIC_SECTION_CHOICES else "principal"
    auth = auth if auth in AUTH_VARIANTS else "anon"
    return snapshot_root() / f"{scope}__{section}__{auth}.html"


def load_snapshot(scope: str, section: str, auth: str) -> str | None:
    try:
        path = snapshot_path(scope, section, auth)
    except RuntimeError:
        return None
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Lecture snapshot Espace PADESCE échouée (%s): %s", path, exc)
        return None


def save_snapshot(scope: str, section: str, auth: str, html: str) -> None:
    try:
        path = snapshot_path(scope, section, auth)
    except RuntimeError as exc:
        logger.warning("Écriture snapshot Espace PADESCE impossible: %s", exc)
        return
    try:
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(html, encoding="utf-8")
        os.replace(temp_path, path)
    except OSError as exc:
        logger.warning("Écriture snapshot Espace PADESCE échouée (%s): %s", path, exc)


def clear_all_snapshots() -> int:
    """Supprime tous les snapshots. Retourne le nombre de fichiers supprimés."""
    removed = 0
    try:
        root = snapshot_root()
    except RuntimeError:
        return 0
    for child in root.glob("*.html"):
        try:
            child.unlink()
            removed += 1
        except OSError:
            continue
    return removed


def iter_all_variants() -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for scope in PUBLIC_SCOPE_CHOICES:
        for section in PUBLIC_SECTION_CHOICES:
            for auth in AUTH_VARIANTS:
                out.append((scope, section, auth))
    return out


def is_refresh_request(request) -> bool:
    """Un superuser peut forcer le recalcul via ``?refresh=1``."""
    user = getattr(request, "user", None)
    if user is None or not bool(getattr(user, "is_superuser", False)):
        return False
    value = str(request.GET.get("refresh") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def is_enabled() -> bool:
    # Cache HTML désactivé - on utilise maintenant le cache de données optimisé
    return False  # Cache désactivé pour optimisation

"""
Cache optimisé pour les contrôles de présence.

Ce module fournit des fonctions pour récupérer les contrôles de présence
par batch au lieu d'appels individuels, réduisant considérablement le nombre
de requêtes base de données pour le dashboard consultant.
"""

import hashlib
import logging
from typing import Dict, List

from django.core.cache import cache
from django.db import OperationalError, ProgrammingError

from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.presences.control_utils import (
    CONTROL_KEYS,
    _has_known_controls,
    _normalize_identifier,
    _with_presence_metadata,
    get_presence_controls,
)

logger = logging.getLogger(__name__)

# Cache TTL: 15 minutes pour les données de présence
PRESENCE_CACHE_TTL = 15 * 60  # 900 secondes
PRESENCE_CACHE_KEY_PREFIX = "presence_bulk"

# Cache version pour invalidation globale
PRESENCE_CACHE_VERSION_KEY = "presence_bulk_cache_version"


def _get_cache_version() -> str:
    """Obtient la version actuelle du cache pour invalidation."""
    version = cache.get(PRESENCE_CACHE_VERSION_KEY)
    if version is None:
        version = "v1"
        cache.set(PRESENCE_CACHE_VERSION_KEY, version, timeout=None)
    return str(version)


def _invalidate_cache() -> None:
    """Invalide le cache de présence global."""
    import time

    version = f"v{int(time.time())}"
    cache.set(PRESENCE_CACHE_VERSION_KEY, version, timeout=None)
    logger.info(f"Cache présence invalidé, nouvelle version: {version}")


def _build_cache_key(apprenant_ids: List[str]) -> str:
    """Construit une clé de cache unique pour un lot d'apprenants."""
    # Trier les IDs pour garantir la cohérence
    sorted_ids = sorted(set(apprenant_ids))
    ids_string = "|".join(sorted_ids)

    # Hash pour éviter les clés trop longues
    hash_object = hashlib.md5(ids_string.encode("utf-8"))
    hash_hex = hash_object.hexdigest()

    version = _get_cache_version()
    return f"{PRESENCE_CACHE_KEY_PREFIX}_{version}_{hash_hex}"


def get_bulk_presence_controls(apprenant_ids: List[str]) -> Dict[str, Dict]:
    """
    Récupère les contrôles de présence pour plusieurs apprenants en une fois.

    Args:
        apprenant_ids: Liste des IDs d'apprenants à récupérer

    Returns:
        Dict mapping apprenant_id -> presence_controls_dict
    """
    if not apprenant_ids:
        return {}

    # Normaliser et dédupliquer les IDs
    normalized_ids = list(set(_normalize_identifier(app_id) for app_id in apprenant_ids))

    # Vérifier le cache
    cache_key = _build_cache_key(normalized_ids)
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        logger.debug(f"Cache hit pour {len(normalized_ids)} apprenants")
        return cached_result

    # Cache miss: récupérer depuis la base de données
    result = {}

    try:
        # Récupérer tous les apprenants concernés en une requête
        apprenants = Apprenant.objects.only("code", *CONTROL_KEYS).filter(
            code__in=[aid for aid in normalized_ids if aid]
        )

        # Construire le mapping code -> apprenant
        apprenant_map = {str(app.code).upper(): app for app in apprenants}

        # Pour chaque ID demandé, récupérer les contrôles
        for apprenant_id in normalized_ids:
            if not apprenant_id:
                continue

            # Chercher l'apprenant dans la base
            apprenant = apprenant_map.get(apprenant_id.upper())
            if apprenant is None:
                # Apprenant non trouvé, utiliser get_presence_controls (fallback)
                try:
                    controls = get_presence_controls(apprenant_id)
                except Exception as e:
                    logger.warning(f"Erreur get_presence_controls pour {apprenant_id}: {e}")
                    controls = _get_default_controls()
                result[apprenant_id] = controls
                continue

            # Construire les contrôles depuis la base de données
            controls = _build_controls_from_db(apprenant)
            result[apprenant_id] = controls

        # Mettre en cache
        cache.set(cache_key, result, timeout=PRESENCE_CACHE_TTL)
        logger.debug(f"Cache miss: récupéré {len(result)} contrôles depuis BD")

    except (OperationalError, ProgrammingError) as e:
        logger.error(f"Erreur base de données dans get_bulk_presence_controls: {e}")
        # Fallback: appels individuels
        for apprenant_id in normalized_ids:
            try:
                controls = get_presence_controls(apprenant_id)
                result[apprenant_id] = controls
            except Exception as e:
                logger.warning(f"Erreur fallback pour {apprenant_id}: {e}")
                result[apprenant_id] = _get_default_controls()

    return result


def _build_controls_from_db(apprenant) -> Dict:
    """
    Construit les contrôles de présence depuis un objet Apprenant de la BD.
    """
    controls_data = {key: getattr(apprenant, key, "") or "" for key in CONTROL_KEYS}

    if not _has_known_controls(controls_data):
        return get_presence_controls(apprenant.code)

    return _with_presence_metadata(
        controls_data,
        source="database_bulk",
        excel_found=False,
        excel_controls_found=[],
    )


def _get_default_controls() -> Dict:
    """Retourne les contrôles par défaut."""
    from App_PADESCE.presences.control_utils import _default_presence

    return _default_presence()


def invalidate_presence_cache() -> None:
    """
    Invalide manuellement le cache de présence.

    À appeler lors de modifications massives des données de présence.
    """
    _invalidate_cache()
    logger.info("Cache de présence invalidé manuellement")


def get_cache_stats() -> Dict:
    """
    Retourne des statistiques sur l'utilisation du cache.
    """
    version = _get_cache_version()

    # Compter les clés de cache actives (approximation)
    cache_keys_count = 0

    try:
        # Cette approche dépend du backend de cache utilisé
        # Pour Redis/Memcached, on pourrait utiliser des commandes spécifiques
        # Pour le cache file-based de Django, c'est plus difficile
        pass
    except Exception:
        pass

    return {
        "cache_version": version,
        "ttl_seconds": PRESENCE_CACHE_TTL,
        "active_keys_estimate": cache_keys_count,
        "enabled": True,
    }


def warm_cache_for_apprenants(apprenant_ids: List[str]) -> int:
    """
    Pré-charge le cache pour une liste d'apprenants.

    Utile pour préparer les données avant un pic de trafic.

    Returns:
        Nombre d'apprenants mis en cache
    """
    if not apprenant_ids:
        return 0

    result = get_bulk_presence_controls(apprenant_ids)
    count = len(result)

    logger.info(f"Cache warmed pour {count} apprenants")
    return count


# Decorator pour invalider automatiquement le cache
def invalidate_presence_cache_on_change(func):
    """
    Décorateur qui invalide le cache de présence après modification des données.

    À utiliser sur les fonctions qui modifient les données de présence.
    """

    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        invalidate_presence_cache()
        return result

    return wrapper

"""
Utilitaires pour le cache de fragments de templates Django.

Ce module fournit des fonctions et décorateurs pour faciliter
l'utilisation du cache de fragments dans les templates.
"""

import hashlib
import logging
from typing import Any, Dict, Optional

from django.core.cache import cache
from django.template import Library, Node, TemplateSyntaxError
from django.utils import timezone

logger = logging.getLogger(__name__)

register = Library()

# Cache TTL pour différents types de fragments
CACHE_TTL = {
    'header': 3600,        # 1 heure - change rarement
    'filters': 1800,       # 30 minutes - options de filtrage
    'stats': 1800,         # 30 minutes - statistiques globales
    'table_data': 900,     # 15 minutes - données des tableaux
    'navigation': 3600,    # 1 heure - navigation
    'sidebar': 1800,       # 30 minutes - sidebar
}


def get_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Génère une clé de cache unique pour les fragments de template.
    
    Args:
        prefix: Préfixe pour identifier le type de fragment
        *args: Arguments positionnels pour la clé
        **kwargs: Arguments nommés pour la clé
        
    Returns:
        Clé de cache unique
    """
    # Créer une chaîne à partir des arguments
    key_parts = [prefix]
    
    # Ajouter les arguments positionnels
    for arg in args:
        if arg is not None:
            key_parts.append(str(arg))
    
    # Ajouter les arguments nommés (triés pour cohérence)
    for key in sorted(kwargs.keys()):
        value = kwargs[key]
        if value is not None:
            key_parts.append(f"{key}:{value}")
    
    # Joindre et hasher
    key_string = "|".join(key_parts)
    hash_object = hashlib.md5(key_string.encode('utf-8'))
    
    return f"template_fragment_{hash_object.hexdigest()}"


def get_user_context_key(request, fragment_type: str) -> str:
    """
    Génère une clé de cache qui prend en compte le contexte utilisateur.
    
    Args:
        request: Objet request Django
        fragment_type: Type de fragment de template
        
    Returns:
        Clé de cache avec contexte utilisateur
    """
    user = getattr(request, 'user', None)
    
    context_data = {
        'fragment_type': fragment_type,
        'is_authenticated': bool(user and user.is_authenticated),
        'is_superuser': bool(user and getattr(user, 'is_superuser', False)),
        'user_id': getattr(user, 'id', None),
    }
    
    return get_cache_key('user_context', **context_data)


def get_filter_context_key(filters: Dict[str, Any], fragment_type: str) -> str:
    """
    Génère une clé de cache qui prend en compte les filtres appliqués.
    
    Args:
        filters: Dictionnaire des filtres
        fragment_type: Type de fragment de template
        
    Returns:
        Clé de cache avec contexte de filtres
    """
    # Normaliser les filtres
    normalized_filters = {}
    for key, value in filters.items():
        if value is not None and value != '':
            normalized_filters[key] = str(value).strip().lower()
    
    context_data = {
        'fragment_type': fragment_type,
        **normalized_filters
    }
    
    return get_cache_key('filter_context', **context_data)


class CachedFragmentNode(Node):
    """
    Nœud de template pour le cache de fragments avec TTL dynamique.
    """
    
    def __init__(self, nodelist, cache_key_expr, ttl_expr=None):
        self.nodelist = nodelist
        self.cache_key_expr = cache_key_expr
        self.ttl_expr = ttl_expr
    
    def render(self, context):
        try:
            # Résoudre la clé de cache
            cache_key = self.cache_key_expr.resolve(context)
            
            # Résoudre le TTL (par défaut 15 minutes)
            ttl = 900
            if self.ttl_expr:
                ttl = int(self.ttl_expr.resolve(context))
            
            # Vérifier le cache
            cached_content = cache.get(cache_key)
            if cached_content is not None:
                return cached_content
            
            # Générer le contenu
            content = self.nodelist.render(context)
            
            # Mettre en cache
            cache.set(cache_key, content, timeout=ttl)
            
            return content
            
        except Exception as e:
            logger.error(f"Erreur dans CachedFragmentNode: {e}")
            # Fallback: retourner le contenu sans cache
            return self.nodelist.render(context)


@register.tag
def cached_fragment(parser, token):
    """
    Tag de template pour mettre en cache un fragment.
    
    Usage:
        {% cached_fragment "header" ttl=3600 %}
            <!-- contenu du header -->
        {% endcached_fragment %}
        
        {% cached_fragment cache_key=request.user.id %}
            <!-- contenu dépendant de l'utilisateur -->
        {% endcached_fragment %}
    """
    try:
        # Parser les arguments
        bits = token.split_contents()
        tag_name = bits[0]
        
        if len(bits) < 2:
            raise TemplateSyntaxError(f"'{tag_name}' requires at least one argument for cache key")
        
        # Extraire la clé de cache
        cache_key_expr = parser.compile_filter(bits[1])
        
        # Parser les arguments optionnels
        ttl_expr = None
        for bit in bits[2:]:
            if bit.startswith('ttl='):
                ttl_expr = parser.compile_filter(bit[4:])
        
        # Parser le contenu du nœud
        nodelist = parser.parse(('endcached_fragment',))
        parser.delete_first_token()
        
        return CachedFragmentNode(nodelist, cache_key_expr, ttl_expr)
        
    except Exception as e:
        logger.error(f"Erreur parsing cached_fragment tag: {e}")
        raise TemplateSyntaxError(f"Invalid syntax for {tag_name}: {e}")


@register.simple_tag
def cache_key_for_filters(filters: Dict[str, Any], fragment_type: str) -> str:
    """
    Génère une clé de cache pour les filtres.
    
    Usage:
        {% cache_key_for_filters filters 'table_data' as cache_key %}
        {% cached_fragment cache_key %}
            <!-- contenu -->
        {% endcached_fragment %}
    """
    return get_filter_context_key(filters, fragment_type)


@register.simple_tag
def cache_key_for_user(request, fragment_type: str) -> str:
    """
    Génère une clé de cache pour le contexte utilisateur.
    
    Usage:
        {% cache_key_for_user request 'header' as cache_key %}
        {% cached_fragment cache_key ttl=3600 %}
            <!-- contenu header -->
        {% endcached_fragment %}
    """
    return get_user_context_key(request, fragment_type)


@register.simple_tag
def get_cache_ttl(fragment_type: str) -> int:
    """
    Retourne le TTL par défaut pour un type de fragment.
    
    Usage:
        {% get_cache_ttl 'header' as ttl %}
        {% cached_fragment "header_key" ttl %}
            <!-- contenu -->
        {% endcached_fragment %}
    """
    return CACHE_TTL.get(fragment_type, 900)  # 15 minutes par défaut


def invalidate_template_cache(fragment_type: str = None, cache_key: str = None) -> int:
    """
    Invalide le cache de templates.
    
    Args:
        fragment_type: Type de fragment à invalider (optionnel)
        cache_key: Clé spécifique à invalider (optionnel)
        
    Returns:
        Nombre de clés invalidées
    """
    invalidated_count = 0
    
    try:
        if cache_key:
            # Invalider une clé spécifique
            if cache.delete(cache_key):
                invalidated_count = 1
        elif fragment_type:
            # Invalider toutes les clés d'un type de fragment
            all_keys = cache.keys('template_fragment_*')
            for key in all_keys:
                if fragment_type in str(key):
                    cache.delete(key)
                    invalidated_count += 1
        else:
            # Invalider tous les fragments de templates
            all_keys = cache.keys('template_fragment_*')
            for key in all_keys:
                cache.delete(key)
                invalidated_count += 1
    
    except Exception as e:
        logger.error(f"Erreur invalidation cache templates: {e}")
    
    logger.info(f"Cache templates invalidé: {invalidated_count} clés")
    return invalidated_count


def get_template_cache_stats() -> Dict:
    """
    Retourne des statistiques sur l'utilisation du cache de templates.
    """
    try:
        all_keys = cache.keys('template_fragment_*')
        
        stats = {
            'total_cached_fragments': len(all_keys),
            'cache_keys_by_type': {},
            'cache_health': 'healthy'
        }
        
        # Compter par type de fragment
        for fragment_type in CACHE_TTL.keys():
            type_keys = [k for k in all_keys if fragment_type in str(k)]
            stats['cache_keys_by_type'][fragment_type] = len(type_keys)
        
        # Vérifier la santé du cache
        if stats['total_cached_fragments'] > 1000:
            stats['cache_health'] = 'warning'
        elif stats['total_cached_fragments'] > 5000:
            stats['cache_health'] = 'critical'
        
        stats['last_check'] = timezone.now().isoformat()
        
        return stats
        
    except Exception as e:
        logger.error(f"Erreur statistiques cache templates: {e}")
        return {
            'total_cached_fragments': 0,
            'cache_keys_by_type': {},
            'cache_health': 'error',
            'last_check': timezone.now().isoformat()
        }


# Context processor pour ajouter les utilitaires de cache aux templates
def template_cache_context(request):
    """
    Context processor pour ajouter les fonctions de cache aux templates.
    """
    return {
        'template_cache_utils': {
            'get_user_key': lambda fragment_type: get_user_context_key(request, fragment_type),
            'get_ttl': get_cache_ttl,
            'cache_ttls': CACHE_TTL,
        }
    }

from __future__ import annotations

import json

from django.http import HttpResponse
from django.templatetags.static import static
from django.views.decorators.http import require_GET
from django.conf import settings


PWA_CACHE_VERSION = "2026-04-02-1"


def _absolute_static_path(path: str) -> str:
    return "/" + static(path).lstrip("/")


@require_GET
def service_worker(request):
    precache_urls = [
        "/manifest.webmanifest",
        _absolute_static_path("branding/logo.png"),
    ]
    template_path = settings.BASE_DIR / "templates" / "pwa" / "service_worker.js"
    body = template_path.read_text(encoding="utf-8").replace(
        "__CACHE_VERSION__",
        PWA_CACHE_VERSION,
    ).replace(
        "__PRECACHE_URLS__",
        json.dumps(precache_urls),
    )
    response = HttpResponse(body, content_type="text/javascript; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    return response


@require_GET
def web_manifest(request):
    logo_url = _absolute_static_path("branding/logo.png")
    payload = {
        "name": "PADESCE",
        "short_name": "PADESCE",
        "description": "Plateforme PADESCE pour les appels, analyses et operations terrain.",
        "start_url": "/dashboard/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#fbf9ff",
        "theme_color": "#7c3aed",
        "icons": [
            {
                "src": logo_url,
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable",
            },
            {
                "src": logo_url,
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable",
            },
        ],
    }
    response = HttpResponse(
        json.dumps(payload, ensure_ascii=False),
        content_type="application/manifest+json; charset=utf-8",
    )
    response["Cache-Control"] = "public, max-age=3600"
    return response

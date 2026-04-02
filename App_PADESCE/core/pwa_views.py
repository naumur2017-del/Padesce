from __future__ import annotations

import json

from django.http import HttpResponse
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.views.decorators.http import require_GET


PWA_CACHE_VERSION = "2026-04-02-1"


def _absolute_static_path(path: str) -> str:
    return "/" + static(path).lstrip("/")


@require_GET
def service_worker(request):
    precache_urls = [
        "/manifest.webmanifest",
        _absolute_static_path("branding/logo.png"),
    ]
    body = render_to_string(
        "pwa/service_worker.js",
        {
            "cache_version": PWA_CACHE_VERSION,
            "precache_urls_json": json.dumps(precache_urls),
        },
        request=request,
    )
    response = HttpResponse(body, content_type="application/javascript; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    response["Service-Worker-Allowed"] = "/"
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

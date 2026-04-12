from __future__ import annotations

from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.http import require_GET


@require_GET
def robots_txt(request):
    sitemap_url = request.build_absolute_uri(reverse("sitemap_xml"))
    body = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /admin/",
            "Disallow: /analyses/",
            "Disallow: /analyse/",
            "Disallow: /appels/",
            "Disallow: /appels-formateurs/",
            "Disallow: /backup/",
            "Disallow: /beneficiaire/",
            "Disallow: /cga/",
            "Disallow: /classe/",
            "Disallow: /consultant/",
            "Disallow: /deploiement/",
            "Disallow: /environnement/",
            "Disallow: /formations/",
            "Disallow: /media/",
            "Disallow: /messages/",
            "Disallow: /prestation/",
            "Disallow: /presences/",
            "Disallow: /reporting/",
            "Disallow: /satisfaction-apprenants/",
            "Disallow: /satisfaction-formateurs/",
            "Disallow: /suivi-utilisateurs/",
            f"Sitemap: {sitemap_url}",
            "",
        ]
    )
    response = HttpResponse(body, content_type="text/plain; charset=utf-8")
    response["Cache-Control"] = "public, max-age=3600"
    return response


@require_GET
def sitemap_xml(request):
    urls = [
        request.build_absolute_uri(reverse("public_space")),
        request.build_absolute_uri(reverse("login")),
    ]
    body = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url in urls:
        body.extend(
            [
                "  <url>",
                f"    <loc>{url}</loc>",
                "  </url>",
            ]
        )
    body.append("</urlset>")
    response = HttpResponse("\n".join(body), content_type="application/xml; charset=utf-8")
    response["Cache-Control"] = "public, max-age=3600"
    return response

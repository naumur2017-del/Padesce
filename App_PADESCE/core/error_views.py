from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import requires_csrf_token

ERROR_PAGE_COPY = {
    400: {
        "page_title": "Demande invalide",
        "eyebrow": "Validation de la requete",
        "headline": "La demande n'a pas pu etre comprise.",
        "lead": (
            "Certaines informations transmises au site sont incompletes, expirees ou invalides."
        ),
        "next_step": "Reprenez l'action depuis une page stable ou rechargez votre session.",
    },
    403: {
        "page_title": "Acces indisponible",
        "eyebrow": "Controle d'acces",
        "headline": "Cette page n'est pas accessible avec votre profil actuel.",
        "lead": (
            "Les droits necessaires ne sont pas disponibles pour cette "
            "operation ou la verification de securite a echoue."
        ),
        "next_step": "Reconnectez-vous ou revenez a une page autorisee pour votre role.",
    },
    404: {
        "page_title": "Page introuvable",
        "eyebrow": "Navigation",
        "headline": "La page demandee est introuvable ou a ete deplacee.",
        "lead": (
            "Le lien utilise n'est peut-etre plus valide ou la ressource "
            "n'est plus disponible a cette adresse."
        ),
        "next_step": "Retournez a l'accueil puis reprenez votre navigation depuis le menu principal.",
    },
    500: {
        "page_title": "Service temporairement indisponible",
        "eyebrow": "Incident applicatif",
        "headline": "Une interruption technique a empeche l'affichage de cette page.",
        "lead": (
            "Le site a rencontre une erreur interne. Les details techniques "
            "sont masques pour proteger l'application."
        ),
        "next_step": "Patientez quelques instants puis reessayez l'action.",
    },
}


def request_prefers_json(request: HttpRequest, response=None) -> bool:
    headers = getattr(request, "headers", {})
    accept = str(headers.get("Accept", "") or "")
    requested_with = str(headers.get("X-Requested-With", "") or "")
    content_type = str(
        getattr(request, "content_type", "") or request.META.get("CONTENT_TYPE", "") or ""
    )
    path = str(getattr(request, "path", "") or "")
    response_content_type = str(getattr(response, "headers", {}).get("Content-Type", "") or "")
    lowered_accept = accept.lower()
    lowered_content_type = content_type.lower()
    lowered_response_type = response_content_type.lower()
    return (
        requested_with.lower() == "xmlhttprequest"
        or "application/json" in lowered_accept
        or "application/json" in lowered_content_type
        or "application/json" in lowered_response_type
        or path.startswith("/reporting/api/")
        or path.startswith("/backup/api/")
        or path.endswith("/analyse/rag/")
        or path.endswith("/api/excel-reseau/")
    )


def _home_url(request: HttpRequest) -> str:
    user = getattr(request, "user", None)
    if getattr(user, "is_authenticated", False):
        return "/dashboard/"
    return "/"


def _maintenance_url(request: HttpRequest) -> str:
    user = getattr(request, "user", None)
    if getattr(user, "is_authenticated", False):
        return "/messages/support/"
    return "/"


def _error_context(request: HttpRequest, status_code: int) -> dict:
    copy = ERROR_PAGE_COPY[status_code]
    environment_label = "developpement" if settings.DEBUG else "production"
    return {
        **copy,
        "status_code": status_code,
        "environment_label": environment_label,
        "home_url": _home_url(request),
        "maintenance_url": _maintenance_url(request),
        "show_maintenance_link": bool(
            getattr(getattr(request, "user", None), "is_authenticated", False)
        ),
        "maintenance_message": (
            "Si le probleme persiste, contactez l'equipe de maintenance en precisant "
            "la page concernee, l'heure de l'incident et, si possible, une capture d'ecran."
        ),
        "request_path": str(getattr(request, "path", "") or ""),
    }


def json_error_response(status_code: int) -> JsonResponse:
    messages = {
        400: "La requete n'a pas pu etre traitee.",
        403: "Acces refuse.",
        404: "Ressource introuvable.",
        500: "Une erreur interne est survenue.",
    }
    return JsonResponse(
        {"error": messages.get(status_code, "Une erreur est survenue.")}, status=status_code
    )


@requires_csrf_token
def render_error_page(request: HttpRequest, status_code: int):
    response = render(
        request,
        f"{status_code}.html",
        _error_context(request, status_code),
        status=status_code,
    )
    response["X-Friendly-Error-Page"] = "1"
    return response


@requires_csrf_token
def bad_request(request: HttpRequest, exception=None):
    return render_error_page(request, 400)


@requires_csrf_token
def permission_denied(request: HttpRequest, exception=None):
    return render_error_page(request, 403)


@requires_csrf_token
def page_not_found(request: HttpRequest, exception=None):
    return render_error_page(request, 404)


@requires_csrf_token
def server_error(request: HttpRequest, exception=None):
    return render_error_page(request, 500)


@requires_csrf_token
def csrf_failure(request: HttpRequest, reason: str = "", template_name: str | None = None):
    return render_error_page(request, 403)

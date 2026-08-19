from __future__ import annotations

from django.conf import settings
from django.urls import NoReverseMatch, reverse

from App_PADESCE.core.access import has_analysis_access, has_consultant_access
from App_PADESCE.core.middleware import strip_path_prefix

PAGE_TITLE_BY_PREFIX: tuple[tuple[str, str], ...] = (
    ("/appels-formateurs/", "Appels Padesce"),
    ("/appels/", "Appels Padesce"),
    ("/backup/", "Backup"),
    ("/recherche/", "Recherche"),
    ("/reporting/documentation/", "Documentation Reporting"),
    ("/satisfaction-apprenants/analyse/", "Analyse PADESCE"),
    ("/satisfaction-apprenants/", "Enquête apprenants"),
    ("/satisfaction-formateurs/analyse/", "Analyse PADESCE"),
    ("/satisfaction-formateurs/", "Enquête formateurs"),
    ("/reporting/concordance-campagnes/", "Concordance & campagnes"),
    ("/reporting/", "Rapport"),
    ("/suivi-utilisateurs/", "Suivi utilisateurs"),
    ("/analyses-cga/", "Analyses CGA"),
    ("/cga/", "CGA"),
    ("/consultant/", "Espace PADESCE"),
    ("/guide-operateur/", "Guide opérateur"),
    ("/messages/support/", "Support"),
    ("/admin/", "Admin"),
    ("/dashboard/", "Call Center"),
)


def _safe_reverse(url_name: str) -> str:
    try:
        return reverse(url_name)
    except NoReverseMatch:
        return "#"


def _is_consultant_only(user) -> bool:
    if not has_consultant_access(user):
        return False
    if getattr(user, "is_superuser", False):
        return False

    groups = getattr(user, "groups", None)
    if groups is None:
        return False

    try:
        return (
            groups.filter(name="consultant").exists()
            and not groups.filter(name__in=("manager_padesce", "manager_cga")).exists()
        )
    except Exception:
        return False


def _page_title_for_path(path: str) -> str:
    for prefix, title in PAGE_TITLE_BY_PREFIX:
        if path.startswith(prefix):
            return title
    return "PADESCE"


def _build_menu_items(user, path: str, consultant_only: bool) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    analysis_access = has_analysis_access(user)
    staff_access = bool(
        getattr(user, "is_authenticated", False) and getattr(user, "is_staff", False)
    )
    superadmin_access = bool(
        getattr(user, "is_authenticated", False) and getattr(user, "is_superuser", False)
    )

    def add_item(label: str, url: str, *active_prefixes: str) -> None:
        items.append(
            {
                "label": label,
                "url": url,
                "active": any(
                    (prefix == "/" and path == "/") or (prefix != "/" and path.startswith(prefix))
                    for prefix in active_prefixes
                ),
            }
        )

    add_item("Call Center", _safe_reverse("home"), "/dashboard/")

    if superadmin_access:
        add_item("Backup", _safe_reverse("backup_dashboard"), "/backup/")

    if analysis_access:
        add_item("Recherche", _safe_reverse("data_search"), "/recherche/")
        add_item(
            "Documentation Reporting",
            _safe_reverse("reporting_manual"),
            "/reporting/documentation/",
        )
        add_item("Espace Padesce", _safe_reverse("public_space"), "/")

        add_item(
            "Concordance & campagnes",
            _safe_reverse("concordance_campaigns"),
            "/reporting/concordance-campagnes/",
        )
        add_item(
            "Analyse PADESCE",
            _safe_reverse("satisfaction_dashboard"),
            "/satisfaction-apprenants/analyse/",
        )
        add_item("Analyses CGA", _safe_reverse("cga_analysis_dashboard"), "/analyses-cga/")

    if superadmin_access:
        add_item("Suivi utilisateurs", _safe_reverse("user_tracking"), "/suivi-utilisateurs/")

    if staff_access:
        add_item("Admin", _safe_reverse("admin:index"), "/admin/")

    return items


def navbar(request):
    path = strip_path_prefix(
        str(getattr(request, "path_info", "") or getattr(request, "path", "") or "")
    )
    if path.startswith("/admin/"):
        return {}

    user = getattr(request, "user", None)
    is_authenticated = bool(user and getattr(user, "is_authenticated", False))
    consultant_only = _is_consultant_only(user)

    return {
        "nav_page_title": _page_title_for_path(path),
        "nav_menu_items": (
            _build_menu_items(user, path, consultant_only) if is_authenticated else []
        ),
        "nav_is_consultant_only": consultant_only,
        "activity_tracking_enabled": bool(
            getattr(settings, "PADESCE_ENABLE_ACTIVITY_TRACKING", True)
        )
        and str(settings.DATABASES.get("default", {}).get("ENGINE", "") or "")
        != "django.db.backends.sqlite3",
    }

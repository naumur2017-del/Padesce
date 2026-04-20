from __future__ import annotations

from django.urls import NoReverseMatch, reverse

from App_PADESCE.core.access import has_analysis_access, has_consultant_access
from App_PADESCE.core.middleware import strip_path_prefix

PAGE_TITLE_BY_PREFIX: tuple[tuple[str, str], ...] = (
    ("/appels-formateurs/", "Appels Padesce"),
    ("/appels/", "Appels Padesce"),
    ("/backup/", "Backup"),
    ("/reporting/documentation/", "Documentation Reporting"),
    ("/satisfaction-apprenants/analyse/", "Analyses de satisfaction"),
    ("/satisfaction-apprenants/", "Enquête apprenants"),
    ("/satisfaction-formateurs/analyse/", "Analyses de satisfaction"),
    ("/satisfaction-formateurs/", "Enquête formateurs"),
    ("/reporting/", "Rapport"),
    ("/suivi-utilisateurs/", "Suivi utilisateurs"),
    ("/cga/", "CGA"),
    ("/consultant/", "Espace PADESCE"),
    ("/guide-operateur/", "Guide opérateur"),
    ("/messages/support/", "Support"),
    ("/admin/", "Admin"),
    ("/dashboard/", "Dashboard"),
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

    add_item("Dashboard", _safe_reverse("home"), "/dashboard/")

    if superadmin_access:
        add_item("Backup", _safe_reverse("backup_dashboard"), "/backup/")

    if analysis_access:
        if not consultant_only:
            add_item(
                "Rapport",
                _safe_reverse("application_report_view"),
                "/reporting/rapport/",
                "/reporting/rapport/view/",
            )
        add_item(
            "Documentation Reporting",
            _safe_reverse("reporting_manual"),
            "/reporting/documentation/",
        )
        add_item("Espace Padesce", _safe_reverse("public_space"), "/")

        add_item(
            "Excel Source", _safe_reverse("reporting_network_excel"), "/reporting/excel-reseau/"
        )
        
        # Ajout du lien vers les Analyses de satisfaction (Apprenants)
        add_item(
            "Analyses de satisfaction",
            _safe_reverse("satisfaction_apprenants_dashboard"),
            "/satisfaction-apprenants/analyse/",
        )

    if superadmin_access:
        add_item("Suivi utilisateurs", _safe_reverse("user_tracking"), "/suivi-utilisateurs/")

    add_item("CGA", _safe_reverse("cga_index"), "/cga/")

    if staff_access:
        add_item("Admin", _safe_reverse("admin:index"), "/admin/")

    return items


def navbar(request):
    path = strip_path_prefix(
        str(getattr(request, "path_info", "") or getattr(request, "path", "") or "")
    )
    user = getattr(request, "user", None)
    is_authenticated = bool(user and getattr(user, "is_authenticated", False))
    consultant_only = _is_consultant_only(user)

    return {
        "nav_page_title": _page_title_for_path(path),
        "nav_menu_items": (
            _build_menu_items(user, path, consultant_only) if is_authenticated else []
        ),
        "nav_is_consultant_only": consultant_only,
    }

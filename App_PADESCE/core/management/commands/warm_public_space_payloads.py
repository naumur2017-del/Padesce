from __future__ import annotations

import time

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.management.base import BaseCommand
from django.test import RequestFactory

from App_PADESCE.core.public_space_html_cache import (
    AUTH_VARIANTS,
    PUBLIC_SCOPE_CHOICES,
    PUBLIC_SECTION_CHOICES,
    clear_all_snapshots,
    save_snapshot,
    snapshot_path,
)
from App_PADESCE.core.public_views import public_space


class Command(BaseCommand):
    help = (
        "Précalcule et fige le HTML des 12 variantes (scope, section, auth) "
        "de la page Espace PADESCE. Les visites suivantes servent le fichier "
        "HTML sauvegardé sans toucher à la base de données."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Supprime tous les snapshots avant reconstruction.",
        )
        parser.add_argument(
            "--anon-only",
            action="store_true",
            help="Ne génère que la variante anonyme (6 rendus au lieu de 12).",
        )

    def handle(self, *args, **options):
        if options.get("clear"):
            removed = clear_all_snapshots()
            self.stdout.write(self.style.WARNING(f"Snapshots supprimés: {removed}"))

        factory = RequestFactory()
        User = get_user_model()
        # Un superuser fictif n'est pas persisté : on en prend un existant
        # seulement pour distinguer la variante "auth" (bouton "Dashboard").
        staff_user = None
        if not options.get("anon_only"):
            staff_user = (
                User.objects.filter(is_active=True, is_superuser=True).order_by("id").first()
                or User.objects.filter(is_active=True, is_staff=True).order_by("id").first()
                or User.objects.filter(is_active=True).order_by("id").first()
            )
            if staff_user is None:
                self.stdout.write(
                    self.style.WARNING(
                        "Aucun utilisateur actif : la variante 'auth' sera ignorée."
                    )
                )

        total = 0
        for scope in PUBLIC_SCOPE_CHOICES:
            for section in PUBLIC_SECTION_CHOICES:
                variants = ["anon"]
                if staff_user is not None and not options.get("anon_only"):
                    variants.append("auth")
                for auth in variants:
                    if auth not in AUTH_VARIANTS:
                        continue
                    request = factory.get(
                        "/", data={"scope": scope, "section": section, "refresh": "1"}
                    )
                    if auth == "auth" and staff_user is not None:
                        request.user = staff_user
                    else:
                        request.user = AnonymousUser()

                    started = time.monotonic()
                    try:
                        response = public_space(request)
                        html = (
                            response.content.decode("utf-8")
                            if hasattr(response, "content")
                            else ""
                        )
                        if html:
                            save_snapshot(scope, section, auth, html)
                            total += 1
                            elapsed = time.monotonic() - started
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"[OK] {scope}/{section}/{auth} → "
                                    f"{snapshot_path(scope, section, auth)} "
                                    f"({elapsed:.1f}s)"
                                )
                            )
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"[SKIP] {scope}/{section}/{auth}: réponse vide"
                                )
                            )
                    except Exception as exc:  # noqa: BLE001
                        self.stdout.write(
                            self.style.ERROR(
                                f"[ERR] {scope}/{section}/{auth}: {exc}"
                            )
                        )

        self.stdout.write(self.style.SUCCESS(f"Snapshots écrits: {total}"))

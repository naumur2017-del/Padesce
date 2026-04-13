from __future__ import annotations

from django.contrib.auth.models import AnonymousUser
from django.core.management.base import BaseCommand
from django.test import RequestFactory

from App_PADESCE.core.public_views import (
    _build_apprenant_overview_materialized,
    _build_apprenant_principal_materialized,
    _build_apprenant_stats_materialized,
    _build_formateur_overview_materialized,
    _build_formateur_principal_materialized,
    _build_formateur_stats_materialized,
)


class Command(BaseCommand):
    help = "Prechauffe les payloads materalises des espaces publics PADESCE."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="cutoff",
            help="Source a utiliser pour les vues apprenant apercu/stats.",
        )

    def handle(self, *args, **options):
        request_factory = RequestFactory()
        source = str(options.get("source") or "cutoff").strip() or "cutoff"
        jobs = [
            (
                "apprenant principal",
                {"scope": "apprenant", "section": "principal"},
                _build_apprenant_principal_materialized,
            ),
            (
                "apprenant apercu",
                {"scope": "apprenant", "section": "apercu", "source": source},
                _build_apprenant_overview_materialized,
            ),
            (
                "apprenant stats",
                {"scope": "apprenant", "section": "stats", "source": source},
                _build_apprenant_stats_materialized,
            ),
            (
                "formateur principal",
                {"scope": "formateur", "section": "principal"},
                _build_formateur_principal_materialized,
            ),
            (
                "formateur apercu",
                {"scope": "formateur", "section": "apercu"},
                _build_formateur_overview_materialized,
            ),
            (
                "formateur stats",
                {"scope": "formateur", "section": "stats"},
                _build_formateur_stats_materialized,
            ),
        ]

        for label, query, builder in jobs:
            request = request_factory.get("/", data=query)
            request.user = AnonymousUser()
            payload = builder(request)
            self.stdout.write(
                self.style.SUCCESS(f"{label}: payload charge ({len(payload or {})} cles)")
            )

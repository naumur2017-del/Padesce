"""Non-destructive audit of accounts that may be used by call-centre operators."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from App_PADESCE.core.operator_auth import normalize_login_identifier


_PHONE_LIKE_IDENTIFIER = re.compile(r"^\+?[0-9][0-9 .()\-]{5,}$")


def _has_invisible_characters(value: str) -> bool:
    return any(unicodedata.category(character) == "Cf" for character in value)


class Command(BaseCommand):
    help = (
        "Audite les comptes de connexion sans les modifier et sans afficher de mot de passe, "
        "hash ou identifiant brut."
    )

    def add_arguments(self, parser):
        parser.add_argument("--format", choices=("table", "json"), default="table")
        parser.add_argument("--output", help="Fichier de rapport à créer (refuse d'écraser un fichier existant).")
        parser.add_argument("--identifier", help="Filtre un identifiant après normalisation, sans l'afficher.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Explicite le mode audit ; la commande ne modifie jamais les comptes.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        user_model = get_user_model()
        username_field = user_model.USERNAME_FIELD
        supplied_identifier = options.get("identifier")
        normalized_filter = normalize_login_identifier(supplied_identifier)
        if supplied_identifier is not None and not normalized_filter:
            raise CommandError("L'identifiant est vide après normalisation.")

        users = list(user_model._default_manager.all().prefetch_related("groups"))
        if normalized_filter:
            users = [
                user
                for user in users
                if normalize_login_identifier(getattr(user, username_field, "")) == normalized_filter
            ]

        issues: list[dict[str, Any]] = []
        normalized_users: dict[str, list[Any]] = defaultdict(list)
        summary = Counter()
        known_role_names = {
            "admin_systeme",
            "inspecteur_enqueteur",
            "prestataire_beneficiaire",
            "consultation",
            "manager_padesce",
            "manager_cga",
            "consultant",
        }

        for user in users:
            raw_identifier = str(getattr(user, username_field, "") or "")
            normalized_identifier = normalize_login_identifier(raw_identifier)
            normalized_users[normalized_identifier].append(user)
            user_issue_codes: list[str] = []

            if not normalized_identifier:
                user_issue_codes.append("AUTH_IDENTIFIER_EMPTY")
                summary["empty_identifiers"] += 1
            if raw_identifier != raw_identifier.strip():
                user_issue_codes.append("AUTH_IDENTIFIER_OUTER_WHITESPACE")
                summary["identifiers_with_outer_whitespace"] += 1
            if _has_invisible_characters(raw_identifier):
                user_issue_codes.append("AUTH_IDENTIFIER_INVISIBLE_CHARACTER")
                summary["identifiers_with_invisible_characters"] += 1
            if raw_identifier and raw_identifier != normalized_identifier:
                summary["identifiers_changed_by_normalization"] += 1
            if "@" in raw_identifier:
                user_issue_codes.append("AUTH_EMAIL_LIKE_IDENTIFIER")
                summary["email_like_identifiers"] += 1
            if _PHONE_LIKE_IDENTIFIER.fullmatch(raw_identifier):
                user_issue_codes.append("AUTH_PHONE_LIKE_IDENTIFIER")
                summary["phone_like_identifiers"] += 1
            if not user.is_active:
                user_issue_codes.append("AUTH_USER_INACTIVE")
                summary["inactive_users"] += 1
            if not user.has_usable_password():
                user_issue_codes.append("AUTH_PASSWORD_UNUSABLE")
                summary["users_with_unusable_password"] += 1

            group_names = {group.name for group in user.groups.all()}
            if not group_names:
                user_issue_codes.append("AUTH_ROLE_MISSING")
                summary["users_without_roles"] += 1
            elif not group_names.intersection(known_role_names):
                user_issue_codes.append("AUTH_ROLE_UNRECOGNIZED")
                summary["users_with_unrecognized_roles"] += 1

            if user_issue_codes:
                issues.append({"user_pk": user.pk, "codes": user_issue_codes})

        collision_buckets = [
            collision_users
            for identifier, collision_users in normalized_users.items()
            if identifier and len(collision_users) > 1
        ]
        for collision_users in collision_buckets:
            summary["normalized_identifier_collisions"] += 1
            summary["users_in_normalized_collisions"] += len(collision_users)
            for user in collision_users:
                issues.append({"user_pk": user.pk, "codes": ["AUTH_IDENTIFIER_COLLISION"]})

        report = {
            "command": "audit_operator_accounts",
            "read_only": True,
            "dry_run": bool(options.get("dry_run")),
            "identifier_field": username_field,
            "filtered_user_count": len(users),
            "operator_profile_model": None,
            "operator_profile_check": "not_applicable_no_operator_profile_model_found",
            "summary": {
                "normalized_identifier_collisions": summary["normalized_identifier_collisions"],
                "users_in_normalized_collisions": summary["users_in_normalized_collisions"],
                **{
                    key: summary[key]
                    for key in sorted(summary)
                    if key
                    not in {"normalized_identifier_collisions", "users_in_normalized_collisions"}
                },
            },
            "issues": issues,
        }

        rendered = self._render(report, options["format"])
        output_path = options.get("output")
        if output_path:
            path = Path(output_path).expanduser()
            if path.exists():
                raise CommandError(f"Le rapport existe deja : {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(rendered, encoding="utf-8")
            self.stdout.write(f"Rapport ecrit : {path}")
            return
        self.stdout.write(rendered, ending="")

    @staticmethod
    def _render(report: dict[str, Any], report_format: str) -> str:
        if report_format == "json":
            return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

        summary_lines = [
            "Audit des comptes operatrices (lecture seule)",
            f"Champ identifiant actuel : {report['identifier_field']}",
            f"Comptes analyses : {report['filtered_user_count']}",
            f"Problemes detectes : {len(report['issues'])}",
        ]
        for key, value in report["summary"].items():
            summary_lines.append(f"- {key}: {value}")
        return "\n".join(summary_lines) + "\n"

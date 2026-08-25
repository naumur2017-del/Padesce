"""Explicit, transactional repair actions for operator account administration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Prepare ou applique des corrections explicites de comptes operatrices."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--create-operator-group", action="store_true")
        parser.add_argument("--operator-group-name", default="operatrice")
        parser.add_argument("--retain-superuser-pk", type=int)
        parser.add_argument(
            "--restore-superuser-pks",
            help="Liste comma-separee de PK a re-promouvoir, uniquement avec --apply.",
        )
        parser.add_argument("--format", choices=("table", "json"), default="table")
        parser.add_argument("--output", help="Fichier de rapport a creer, sans ecraser un existant.")
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true", dest="dry_run", default=True)
        mode.add_argument("--apply", action="store_false", dest="dry_run")

    def handle(self, *args: Any, **options: Any) -> None:
        group_name = str(options["operator_group_name"] or "").strip()
        if options["create_operator_group"] and not group_name:
            raise CommandError("Le nom du groupe operatrice est obligatoire.")

        restore_pks = self._parse_pks(options.get("restore_superuser_pks"))
        retained_pk = options.get("retain_superuser_pk")
        if restore_pks and retained_pk:
            raise CommandError("--restore-superuser-pks et --retain-superuser-pk sont incompatibles.")
        if restore_pks and options["dry_run"]:
            raise CommandError("La restauration exige --apply et une liste explicite de PK.")
        if not (options["create_operator_group"] or retained_pk or restore_pks):
            raise CommandError("Selectionnez au moins une action explicite.")

        user_model = get_user_model()
        retained_user = None
        if retained_pk:
            try:
                retained_user = user_model.objects.get(pk=retained_pk)
            except user_model.DoesNotExist as exc:
                raise CommandError("Le superadministrateur a conserver est introuvable.") from exc
            if not retained_user.is_superuser or not retained_user.is_active:
                raise CommandError("Le compte a conserver doit etre superadministrateur et actif.")

        superuser_pks_to_demote = []
        if retained_user is not None:
            superuser_pks_to_demote = list(
                user_model.objects.filter(is_superuser=True)
                .exclude(pk=retained_user.pk)
                .order_by("pk")
                .values_list("pk", flat=True)
            )

        missing_restore_pks = sorted(set(restore_pks).difference(user_model.objects.values_list("pk", flat=True)))
        if missing_restore_pks:
            raise CommandError("Un ou plusieurs comptes a restaurer sont introuvables.")

        report = {
            "command": "repair_operator_accounts",
            "dry_run": bool(options["dry_run"]),
            "operator_group": {
                "name": group_name,
                "requested": bool(options["create_operator_group"]),
                "already_exists": Group.objects.filter(name=group_name).exists()
                if options["create_operator_group"]
                else False,
            },
            "superuser_pk_retained": retained_user.pk if retained_user else None,
            "superuser_pks_to_demote": superuser_pks_to_demote,
            "superuser_pks_to_restore": restore_pks,
            "rollback": {
                "command": "repair_operator_accounts --apply --restore-superuser-pks "
                + ",".join(str(pk) for pk in superuser_pks_to_demote)
                if superuser_pks_to_demote
                else None
            },
        }

        if not options["dry_run"]:
            with transaction.atomic():
                if options["create_operator_group"]:
                    Group.objects.get_or_create(name=group_name)
                if superuser_pks_to_demote:
                    user_model.objects.filter(pk__in=superuser_pks_to_demote).update(is_superuser=False)
                if restore_pks:
                    user_model.objects.filter(pk__in=restore_pks).update(is_superuser=True)
            report["applied"] = True
        else:
            report["applied"] = False

        rendered = self._render(report, options["format"])
        self._write(rendered, options.get("output"))

    @staticmethod
    def _parse_pks(raw_value: str | None) -> list[int]:
        if not raw_value:
            return []
        try:
            values = sorted({int(value.strip()) for value in raw_value.split(",") if value.strip()})
        except ValueError as exc:
            raise CommandError("Les PK a restaurer doivent etre des entiers separes par des virgules.") from exc
        if any(value <= 0 for value in values):
            raise CommandError("Les PK a restaurer doivent etre strictement positifs.")
        return values

    def _write(self, rendered: str, output_path: str | None) -> None:
        if not output_path:
            self.stdout.write(rendered, ending="")
            return
        path = Path(output_path).expanduser()
        if path.exists():
            raise CommandError(f"Le rapport existe deja : {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
        self.stdout.write(f"Rapport ecrit : {path}")

    @staticmethod
    def _render(report: dict[str, Any], report_format: str) -> str:
        if report_format == "json":
            return json.dumps(report, indent=2, sort_keys=True) + "\n"
        return "\n".join(
            [
                "Reparation comptes operatrices",
                f"Mode: {'dry-run' if report['dry_run'] else 'apply'}",
                f"Groupe operatrice: {report['operator_group']['name']}",
                f"Superadmin conserve: {report['superuser_pk_retained']}",
                f"Superadmins a retrograder: {report['superuser_pks_to_demote']}",
                f"Superadmins a restaurer: {report['superuser_pks_to_restore']}",
            ]
        ) + "\n"

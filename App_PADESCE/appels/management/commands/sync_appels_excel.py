import unicodedata
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from App_PADESCE.appels.models import Appel, AppelImportArchive
from App_PADESCE.appels.views import _parse_excel, _parse_excel_non_forme
from App_PADESCE.formations.models import Classe


def _normalize_lookup(value) -> str:
    text = " ".join(str(value or "").strip().lower().split())
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _resolve_classe(item: dict) -> Classe | None:
    classe_label = str(item.get("classe_label") or "").strip()
    if not classe_label:
        return None
    return Classe.objects.filter(code=classe_label).first()


def _find_existing_appel(item: dict) -> tuple[Appel | None, str]:
    code = str(item.get("code") or "").strip()
    if code:
        appel = Appel.objects.filter(code__iexact=code).first()
        if appel:
            return appel, "code"

    nom_key = _normalize_lookup(item.get("nom"))
    classe_key = _normalize_lookup(item.get("classe_label"))
    prestataire_key = _normalize_lookup(item.get("prestataire"))
    if not nom_key or not classe_key:
        return None, ""

    candidates = list(
        Appel.objects.filter(classe_label__iexact=str(item.get("classe_label") or "").strip()).only(
            "id",
            "code",
            "nom",
            "prestataire",
            "classe_label",
        )
    )
    if prestataire_key:
        matches = [
            appel
            for appel in candidates
            if _normalize_lookup(appel.nom) == nom_key
            and _normalize_lookup(appel.prestataire) == prestataire_key
        ]
        if len(matches) == 1:
            return matches[0], "nom+classe+prestataire"

    matches = [appel for appel in candidates if _normalize_lookup(appel.nom) == nom_key]
    if len(matches) == 1:
        return matches[0], "nom+classe"
    return None, ""


def _archive_before_update(appel: Appel, import_mode: str) -> None:
    AppelImportArchive.objects.create(
        appel=appel,
        import_mode=import_mode,
        source_code=appel.code or "",
        snapshot={
            "id": appel.id,
            "code": appel.code,
            "nom": appel.nom,
            "prestataire": appel.prestataire,
            "beneficiaire": appel.beneficiaire,
            "lieu": appel.lieu,
            "classe_label": appel.classe_label,
            "fenetre": appel.fenetre,
            "is_active": appel.is_active,
            "classe_id": appel.classe_id,
            "telephone1": appel.telephone1,
            "telephone2": appel.telephone2,
            "taux_presence": str(appel.taux_presence or 0),
            "status": appel.status,
            "type_formation_declaree": appel.type_formation_declaree,
            "formation_padesce": appel.formation_padesce,
            "deja_forme": appel.deja_forme,
            "flag_pas_forme": appel.flag_pas_forme,
            "flag_faux_nom": appel.flag_faux_nom,
            "flag_vrai_nom": appel.flag_vrai_nom,
            "flag_deja_appele": appel.flag_deja_appele,
            "flag_numero_double": appel.flag_numero_double,
        },
    )


def _apply_item(appel: Appel, item: dict, *, preserve_code: bool) -> None:
    for key, value in item.items():
        if preserve_code and key == "code":
            continue
        setattr(appel, key, value)


def _format_breakdown(matched_by: dict[str, int]) -> str:
    parts = []
    for key in ("code", "nom+classe+prestataire", "nom+classe"):
        count = int(matched_by.get(key) or 0)
        if count:
            parts.append(f"{key}={count}")
    return f" Correspondances: {', '.join(parts)}." if parts else ""


def _sync_payload(payload: list[dict], mode: str) -> dict:
    replace_display = mode in {"replace", "non_forme_feuil2", "capef_sheet1"}
    if replace_display:
        Appel.objects.update(is_active=False)

    created = 0
    updated = 0
    skipped = 0
    matched_by: dict[str, int] = {}

    for item in payload:
        code = str(item.get("code") or "").strip()
        nom = str(item.get("nom") or "").strip()
        if not code and not nom:
            skipped += 1
            continue

        classe_obj = _resolve_classe(item)
        appel, match_type = _find_existing_appel(item)
        if appel:
            _archive_before_update(appel, mode)
            _apply_item(appel, item, preserve_code=match_type != "code")
            appel.classe = classe_obj
            appel.is_active = True
            appel.save()
            updated += 1
            matched_by[match_type or "code"] = matched_by.get(match_type or "code", 0) + 1
            continue

        Appel.objects.create(**item, classe=classe_obj, is_active=True)
        created += 1

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "matched_by": matched_by,
    }


class Command(BaseCommand):
    help = "Importe un fichier Excel d'appels et met a jour les lignes existantes par code ou par nom+classe."

    def add_arguments(self, parser):
        parser.add_argument("file_path", help="Chemin du fichier Excel a importer.")
        parser.add_argument(
            "--mode",
            default="append",
            choices=["append", "replace", "non_forme_feuil2", "capef_sheet1", "training_only"],
            help="Mode d'import. Par defaut: append.",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file_path"]).expanduser()
        mode = options["mode"]

        if not file_path.exists():
            raise CommandError(f"Fichier introuvable: {file_path}")

        with file_path.open("rb") as fh:
            try:
                if mode == "non_forme_feuil2":
                    payload = _parse_excel_non_forme(fh)
                else:
                    payload = _parse_excel(fh)
            except Exception as exc:
                raise CommandError(f"Impossible de lire le fichier : {exc}") from exc

        with transaction.atomic():
            result = _sync_payload(payload, mode)

        breakdown = _format_breakdown(result["matched_by"])
        summary = (
            f"Import termine. {result['created']} cree(s), {result['updated']} mis a jour, "
            f"{result['skipped']} ignore(s)."
        )
        self.stdout.write(self.style.SUCCESS(summary + breakdown))

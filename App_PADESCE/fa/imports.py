"""Idempotent, non-destructive import of the supplied company register."""

import hashlib
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zipfile import BadZipFile

from django.db import transaction

from .campaigns import PME
from .models import Enterprise


def normalize(value):
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def as_text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return " ".join(str(value).strip().split())


def normalize_phone(value):
    raw = value if isinstance(value, str) else as_text(value)
    numbers = []
    for part in re.split(r"[/;,\r\n]+", raw.replace("(0)", "")):
        digits = re.sub(r"[^\d+]", "", part)
        if digits and digits not in numbers:
            numbers.append(digits)
    return " / ".join(numbers)[:150]


def records_from_file(source, campaign=PME):
    name = str(getattr(source, "name", source)).lower()
    if name.endswith(".json"):
        if hasattr(source, "read"):
            records = json.load(source)
        else:
            records = json.loads(Path(source).read_text(encoding="utf-8"))
        if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
            raise ValueError("Le fichier JSON doit contenir une liste d’entreprises.")
        return records
    if not name.endswith(".xlsx"):
        raise ValueError("Utilisez un fichier .xlsx ou le registre JSON FA.")
    import openpyxl

    try:
        workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    except (BadZipFile, openpyxl.utils.exceptions.InvalidFileException) as exc:
        raise ValueError(
            "Le fichier Excel est endommagé ou n’est pas un classeur .xlsx valide."
        ) from exc
    aliases = {
        "#": "source_number",
        "n°": "source_number",
        "numero": "source_number",
        "nom de l'entreprise": "name",
        "nom de l’entreprise": "name",
        "entreprise": "name",
        "nom": "name",
        "raison sociale": "name",
        "tel": "phone_raw",
        "telephone": "phone_raw",
        "ville": "city",
        "ca fcfa": "annual_revenue_fcfa",
        "filieres": "sector",
        "secteur": "sector",
        **campaign.aliases,
    }
    records = []
    try:
        for sheet_index, sheet in enumerate(workbook.worksheets, 1):
            mapping = None
            for row_number, values in enumerate(sheet.iter_rows(values_only=True), 1):
                if row_number > 10001:
                    raise ValueError("Le fichier dépasse 10 000 entreprises par feuille.")
                if mapping is None:
                    candidate = {
                        i: aliases[normalize(v)]
                        for i, v in enumerate(values)
                        if normalize(v) in aliases
                    }
                    if "name" in candidate.values():
                        mapping = candidate
                    elif row_number > 20:
                        break
                    continue
                row = {key: values[index] for index, key in mapping.items()}
                if not any(v not in (None, "") for v in row.values()):
                    continue
                row["source_sheet"] = sheet.title
                row["source_sheet_index"] = sheet_index
                row["source_row"] = row_number
                records.append(row)
    finally:
        workbook.close()
    if not records:
        raise ValueError("Aucune entreprise trouvée. Vérifiez les en-têtes du fichier.")
    return records


def is_blank(value):
    return value in (None, "") or normalize(value) == "non renseigne"


def merge_same_names(records, warnings):
    """Fusionne une structure présente sur plusieurs feuilles du même répertoire."""
    merged = {}
    for row in records:
        row = {key: None if is_blank(value) else value for key, value in row.items()}
        first = merged.setdefault(normalize(row.get("name")) or id(row), row)
        if first is row:
            continue
        warnings.append(f"{as_text(row.get('name'))} : doublon fusionné ({row['source_sheet']}).")
        for key, value in row.items():
            if is_blank(value) or key.startswith("source_"):
                continue
            current = first.get(key)
            if is_blank(current):
                first[key] = value
            elif key in {"phone_raw", "email"}:
                extras = [v for v in str(value).split("\n") if v.strip() not in str(current)]
                first[key] = "\n".join([str(current), *extras])
    return list(merged.values())


@transaction.atomic
def import_records(records, *, campaign=PME, dry_run=False):
    result = {"created": 0, "updated": 0, "skipped": 0, "warnings": []}
    if len(records) > 20000:
        raise ValueError("Le registre dépasse la limite de 20 000 entreprises.")
    if campaign.merge_same_name:
        records = merge_same_names(records, result["warnings"])
    seen = set()
    for index, row in enumerate(records, 1):
        name = as_text(row.get("name"))[:255]
        source_phone = row.get("phone_raw", row.get("phone"))
        phone = normalize_phone(source_phone)
        if not name and campaign.unnamed_contacts and phone:
            name = f"Contact sans nom ({phone})"
            result["warnings"].append(f"Ligne {index} : nom absent, {name}.")
        if not name:
            result["skipped"] += 1
            result["warnings"].append(f"Ligne {index} : nom absent.")
            continue
        number = as_text(row.get("source_number"))[:60]
        city = as_text(row.get("city"))[:150]
        prefix = campaign.reference_prefix
        # Un répertoire multi-feuilles renumérote chaque feuille à partir de 1.
        sheet = f"{row.get('source_sheet_index', 1)}-" if campaign.merge_same_name else ""
        reference = (
            f"{prefix}-{sheet}{number.zfill(3)}"
            if number
            else f"{prefix}-"
            + hashlib.sha256(f"{normalize(name)}|{normalize(city)}".encode()).hexdigest()[:20]
        )
        if reference in seen:
            raise ValueError(f"Référence en double dans le fichier : {reference}.")
        seen.add(reference)
        raw_phone = as_text(source_phone)[:255]
        revenue = row.get("annual_revenue_fcfa")
        if revenue in (None, ""):
            revenue = None
        else:
            try:
                revenue = Decimal(str(revenue).replace(" ", "").replace(",", "."))
                if (
                    not revenue.is_finite()
                    or revenue < 0
                    or revenue >= Decimal("1e20")
                    or revenue != revenue.to_integral_value()
                ):
                    raise InvalidOperation
            except (InvalidOperation, ValueError):
                raise ValueError(f"Chiffre d’affaires invalide pour {reference}.") from None
        sector = as_text(row.get("sector"))[:180]
        sector = {
            "volaile de chair": "Volaille de chair",
            "poissons d'eau douce": "Poissons d’eau douce",
        }.get(normalize(sector), sector)
        for part in phone.split(" / "):
            digits = re.sub(r"\D", "", part)
            if digits and len(digits) not in {9, 12, 14}:
                result["warnings"].append(f"{reference} : numéro à vérifier ({part}).")
        if not phone:
            result["warnings"].append(f"{reference} : téléphone absent.")
        safe_source = {k: str(v) if isinstance(v, Decimal) else v for k, v in row.items()}
        values = dict(
            campaign=campaign.key,
            name=name,
            source_number=number,
            phone=phone,
            phone_raw=raw_phone,
            city=city,
            sector=sector,
            annual_revenue_fcfa=revenue,
            source_data=safe_source,
        )
        enterprise, created = Enterprise.objects.get_or_create(reference=reference, defaults=values)
        if enterprise.campaign != campaign.key:
            raise ValueError(f"La référence {reference} appartient à une autre campagne.")
        if created:
            result["created"] += 1
        else:
            # Preserve work already done by agents and enrich only the register fields.
            changed = []
            for key, value in values.items():
                if key == "phone" and enterprise.answers.get("q4_phone"):
                    continue
                if key not in {"source_data", "source_number"} and value in (None, ""):
                    continue
                if getattr(enterprise, key) != value:
                    setattr(enterprise, key, value)
                    changed.append(key)
            if changed:
                enterprise.save(update_fields=changed + ["updated_at"])
            result["updated"] += 1
    if dry_run:
        transaction.set_rollback(True)
    return result

"""Idempotent, non-destructive import of the supplied company register."""

import hashlib
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zipfile import BadZipFile

from django.db import transaction

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
    raw = as_text(value)
    numbers = []
    for part in re.split(r"[/;,\n]+", raw):
        digits = re.sub(r"[^\d+]", "", part)
        if digits and digits not in numbers:
            numbers.append(digits)
    return " / ".join(numbers)[:150]


def records_from_file(source):
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
    }
    records = []
    try:
        for sheet in workbook.worksheets:
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
                row["source_row"] = row_number
                records.append(row)
    finally:
        workbook.close()
    if not records:
        raise ValueError("Aucune entreprise trouvée. Vérifiez les en-têtes du fichier.")
    return records


@transaction.atomic
def import_records(records, *, dry_run=False):
    result = {"created": 0, "updated": 0, "skipped": 0, "warnings": []}
    if len(records) > 20000:
        raise ValueError("Le registre dépasse la limite de 20 000 entreprises.")
    seen = set()
    for index, row in enumerate(records, 1):
        name = as_text(row.get("name"))[:255]
        if not name:
            result["skipped"] += 1
            result["warnings"].append(f"Ligne {index} : nom absent.")
            continue
        number = as_text(row.get("source_number"))[:60]
        city = as_text(row.get("city"))[:150]
        reference = (
            f"FA-{number.zfill(3)}"
            if number
            else "FA-"
            + hashlib.sha256(f"{normalize(name)}|{normalize(city)}".encode()).hexdigest()[:20]
        )
        if reference in seen:
            raise ValueError(f"Référence en double dans le fichier : {reference}.")
        seen.add(reference)
        raw_phone = as_text(row.get("phone_raw", row.get("phone")))[:255]
        phone = normalize_phone(raw_phone)
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
            campaign=Enterprise.CAMPAIGN_PME,
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
        if enterprise.campaign != Enterprise.CAMPAIGN_PME:
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

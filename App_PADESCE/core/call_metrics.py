from __future__ import annotations

from collections import Counter, defaultdict


def normalize_phone_digits(value: object) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def phone_variants(*values: object) -> tuple[str, ...]:
    normalized = []
    seen = set()
    for value in values:
        digits = normalize_phone_digits(value)
        if not digits or digits in seen:
            continue
        seen.add(digits)
        normalized.append(digits)
    return tuple(normalized)


def has_usable_phone(*values: object) -> bool:
    return bool(phone_variants(*values))


def source_record_phone_variants(record: dict | None) -> tuple[str, ...]:
    record = record or {}
    return phone_variants(record.get("telephone1"), record.get("telephone2"))


def source_record_has_usable_phone(record: dict | None) -> bool:
    return bool(source_record_phone_variants(record))


def count_callable_source_records_by_class(source_bundle: dict | None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in (source_bundle or {}).get("records", {}).values():
        classe_code = str(record.get("classe_id") or record.get("classe_label") or "").strip()
        if not classe_code or not source_record_has_usable_phone(record):
            continue
        counts[classe_code] = counts.get(classe_code, 0) + 1
    return counts


def summarize_source_class_phone_coverage(source_bundle: dict | None) -> dict[str, dict[str, int]]:
    callable_counts: dict[str, int] = defaultdict(int)
    phone_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for record in (source_bundle or {}).get("records", {}).values():
        classe_code = str(record.get("classe_id") or record.get("classe_label") or "").strip()
        if not classe_code:
            continue
        phones = source_record_phone_variants(record)
        if not phones:
            continue
        callable_counts[classe_code] += 1
        for phone in phones:
            phone_counts[classe_code][phone] += 1

    summary: dict[str, dict[str, int]] = {}
    for classe_code in set(callable_counts) | set(phone_counts):
        duplicates = sum(count - 1 for count in phone_counts[classe_code].values() if count > 1)
        summary[classe_code] = {
            "callable_total": int(callable_counts.get(classe_code) or 0),
            "unique_phone_total": len(phone_counts[classe_code]),
            "duplicate_phone_total": duplicates,
        }
    return summary

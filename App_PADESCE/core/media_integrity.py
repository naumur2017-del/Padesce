"""Audit non destructif des références de fichiers Django."""

from __future__ import annotations

import os
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.db.models import FileField


def audit_media_integrity() -> dict[str, object]:
    root = Path(settings.MEDIA_ROOT)
    referenced: set[str] = set()
    missing: list[dict[str, str]] = []
    fields_checked = 0
    for model in apps.get_models():
        for field in model._meta.fields:
            if not isinstance(field, FileField):
                continue
            fields_checked += 1
            for pk, name in model._default_manager.exclude(
                **{f"{field.name}__isnull": True}
            ).values_list("pk", field.name):
                value = str(name or "").lstrip("/")
                if not value:
                    continue
                referenced.add(value)
                if not (root / value).is_file():
                    missing.append(
                        {
                            "model": model._meta.label,
                            "pk": str(pk),
                            "field": field.name,
                            "path": value,
                        }
                    )
    present: set[str] = set()
    total_size = 0
    if root.exists():
        for directory, _, filenames in os.walk(root):
            for filename in filenames:
                path = Path(directory) / filename
                present.add(str(path.relative_to(root)))
                total_size += path.stat().st_size
    return {
        "media_root": str(root),
        "fields_checked": fields_checked,
        "referenced_count": len(referenced),
        "files_count": len(present),
        "total_size": total_size,
        "missing_references": missing,
        "orphan_files": sorted(present - referenced),
    }

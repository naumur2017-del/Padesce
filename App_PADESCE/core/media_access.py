from __future__ import annotations

import mimetypes
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core import signing
from django.core.files.storage import default_storage
from django.urls import reverse
from django.utils import timezone

PROTECTED_MEDIA_SALT = "padesce-protected-media"


def secure_media_upload_path(namespace: str, filename: str, *, default_ext: str = "bin") -> str:
    now = timezone.now()
    suffix = Path(str(filename or "")).suffix.lower()
    ext = suffix or f".{default_ext}"
    return f"{namespace}/{now:%Y}/{now:%m}/{now:%d}/{uuid4().hex}{ext}"


def build_protected_media_token(path: str) -> str:
    normalized_path = str(path or "").lstrip("/")
    if not normalized_path:
        return ""
    return signing.dumps({"path": normalized_path}, salt=PROTECTED_MEDIA_SALT, compress=True)


def resolve_protected_media_token(token: str) -> str:
    max_age = int(getattr(settings, "PROTECTED_MEDIA_TOKEN_MAX_AGE", 28800) or 28800)
    payload = signing.loads(token, salt=PROTECTED_MEDIA_SALT, max_age=max_age)
    path = str(payload.get("path") or "").lstrip("/")
    if not path:
        raise signing.BadSignature("Missing protected media path.")
    return path


def build_protected_storage_url(path: str) -> str:
    normalized_path = str(path or "").strip().lstrip("/")
    if not normalized_path:
        return ""
    try:
        exists = default_storage.exists(normalized_path)
    except Exception:
        exists = False
    if not exists:
        return ""
    token = build_protected_media_token(normalized_path)
    return reverse("protected_media_download", args=[token]) if token else ""


def build_protected_media_url(file_field) -> str:
    if not file_field:
        return ""
    name = str(getattr(file_field, "name", "") or "").strip()
    if not name:
        return ""
    return build_protected_storage_url(name)


def guess_media_content_type(path: str) -> str:
    content_type, _encoding = mimetypes.guess_type(str(path or ""))
    return content_type or "application/octet-stream"

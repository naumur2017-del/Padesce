from __future__ import annotations

from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET

from App_PADESCE.core.media_access import guess_media_content_type, resolve_protected_media_token


@login_required
@require_GET
def protected_media_download(request, token: str):
    try:
        relative_path = resolve_protected_media_token(token)
    except signing.BadSignature as exc:
        raise Http404("Fichier protege introuvable.") from exc

    if not default_storage.exists(relative_path):
        raise Http404("Fichier protege introuvable.")

    try:
        media_file = default_storage.open(relative_path, "rb")
    except OSError as exc:
        raise Http404("Fichier protege introuvable.") from exc

    filename = Path(relative_path).name or "media.bin"
    download_requested = request.GET.get("download") == "1"
    response = FileResponse(
        media_file,
        as_attachment=download_requested,
        filename=filename,
        content_type=guess_media_content_type(relative_path),
    )
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response

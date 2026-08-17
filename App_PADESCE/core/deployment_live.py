from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LIVE_MARKER_FILENAME = ".naumur-deploy-live.json"
APP_BOOTED_AT = datetime.now(timezone.utc).isoformat()


def load_live_marker(base_dir: Path) -> dict[str, Any]:
    path = Path(base_dir) / LIVE_MARKER_FILENAME
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def live_status_payload(base_dir: Path) -> dict[str, Any]:
    cga_template = Path(base_dir) / "templates" / "appels" / "cga.html"
    cga_template_hash = ""
    cga_argumentaire_present = False
    try:
        template_bytes = cga_template.read_bytes()
        cga_template_hash = hashlib.sha256(template_bytes).hexdigest()
        cga_argumentaire_present = b'id="js-call-script-modal"' in template_bytes
    except OSError:
        pass
    marker = load_live_marker(base_dir)
    return {
        "ok": True,
        "app_booted_at": APP_BOOTED_AT,
        "process_id": os.getpid(),
        "cga_ui": {
            "version": "argumentaire-v2",
            "template_sha256": cga_template_hash,
            "argumentaire_present": cga_argumentaire_present,
        },
        "marker": marker,
    }

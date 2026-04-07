from __future__ import annotations

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
    marker = load_live_marker(base_dir)
    return {
        "ok": True,
        "app_booted_at": APP_BOOTED_AT,
        "process_id": os.getpid(),
        "marker": marker,
    }

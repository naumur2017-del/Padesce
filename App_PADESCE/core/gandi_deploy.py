from __future__ import annotations

import hashlib
import json
import os
import posixpath
import stat
import time
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

import requests
from django.conf import settings

from App_PADESCE.core.deployment_live import LIVE_MARKER_FILENAME
from App_PADESCE.core.deployment_reporting import record_and_notify_deployment

try:
    import paramiko
except Exception:  # pragma: no cover - handled at runtime when dependency is missing
    paramiko = None


MANIFEST_FILENAME = ".naumur-deploy-manifest.json"
RUN_FILE_PREFIX = "run-"
RUN_FILE_SUFFIX = ".json"
LOCK_FILENAME = "active.lock"
RUNTIME_CONFIG_FILENAME = "runtime-config.json"


def _int_env(name: str, default: int, *, minimum: int = 1) -> int:
    try:
        value = int(str(os.getenv(name, str(default)) or str(default)))
    except (TypeError, ValueError):
        return default
    return max(minimum, value)


HTTP_TIMEOUT_SECONDS = _int_env("GANDI_HTTP_TIMEOUT_SECONDS", 15)
LIVE_REFRESH_TIMEOUT_SECONDS = _int_env("GANDI_LIVE_REFRESH_TIMEOUT_SECONDS", 300)
LIVE_REFRESH_POLL_INTERVAL_SECONDS = _int_env("GANDI_LIVE_REFRESH_POLL_INTERVAL_SECONDS", 5)
PUBLIC_HTTP_CHECK_ATTEMPTS = _int_env("GANDI_PUBLIC_HTTP_CHECK_ATTEMPTS", 6)
PUBLIC_HTTP_CHECK_RETRY_DELAY_SECONDS = _int_env("GANDI_PUBLIC_HTTP_CHECK_RETRY_DELAY_SECONDS", 10)
MAX_HISTORY_ITEMS = 10
MAX_LOG_LINES = 400
REMOTE_UWSGI_LOG_PATH = "/lamp0/var/log/www/uwsgi.log"

STEP_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("prepare", "Preparation"),
    ("connect", "Connexion Gandi"),
    ("discover", "Detection de la cible"),
    ("local_scan", "Analyse locale"),
    ("remote_scan", "Analyse distante"),
    ("diff", "Calcul des changements"),
    ("upload", "Transfert des fichiers"),
    ("delete", "Suppression distante"),
    ("verify", "Verification finale"),
)

IGNORE_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "logs",
    "media",
    "staticfiles",
    "node_modules",
}
IGNORE_FILE_NAMES = {
    ".env",
    ".env.local",
    "db.sqlite3",
    "cert.crt",
    "cert.key",
    "token-call-gandi.txt",
    MANIFEST_FILENAME,
    LIVE_MARKER_FILENAME,
}
IGNORE_FILE_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".pyd",
    ".log",
    ".sqlite3-journal",
    ".sqlite3-wal",
    ".sqlite3-shm",
)
DEFAULT_INCLUDE_PATHS = (
    "App_PADESCE",
    "templates",
    "static",
    "data",
    "docs",
    "admin",
    "manage.py",
    "requirements.txt",
    "Dockerfile",
    "docker-compose.yml",
    "start-command",
)
APP_ENV_SYNC_KEYS = (
    # Django runtime — toujours synchronisés pour garantir la config de prod
    "DJANGO_DEBUG",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "DATABASE_URL",
    "DB_ENGINE",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_SSLMODE",
    "POSTGRES_CONN_MAX_AGE",
    "PADESCE_CACHE_BACKEND",
    "PADESCE_CACHE_LOCATION",
    "PADESCE_CACHE_TIMEOUT",
    "PADESCE_CACHE_MAX_ENTRIES",
    "PADESCE_SOURCE_CACHE_TIMEOUT",
    "PADESCE_ANALYSIS_CACHE_TIMEOUT",
    "WEB_CONCURRENCY",
    "WEB_TIMEOUT",
    "WEB_KEEP_ALIVE",
    # Microsoft Graph / Teams
    "MICROSOFT_GRAPH_CLIENT_ID",
    "MICROSOFT_GRAPH_CLIENT_SECRET",
    "MICROSOFT_GRAPH_TENANT_ID",
    "MICROSOFT_GRAPH_PRIMARY_DOMAIN",
    "MICROSOFT_GRAPH_REDIRECT_URI",
    "MICROSOFT_TEAMS_DEFAULT_TEAM_ID",
)


class DeploymentError(RuntimeError):
    """Raised when the deployment pipeline cannot continue."""


class DeploymentBusyError(DeploymentError):
    """Raised when another deployment run is already in progress."""


@dataclass(slots=True)
class DeploymentConfig:
    host: str
    port: int
    username: str
    token: str
    domain: str
    remote_path: str
    verify_url: str
    local_root: Path
    include_paths: tuple[str, ...]

    @property
    def masked_username(self) -> str:
        value = self.username.strip()
        if len(value) <= 10:
            return value
        return f"{value[:6]}...{value[-4:]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def deployment_dir() -> Path:
    base_dir = Path(settings.BASE_DIR)
    path = base_dir / "logs" / "deployments"
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_state_path(run_id: str) -> Path:
    return deployment_dir() / f"{RUN_FILE_PREFIX}{run_id}{RUN_FILE_SUFFIX}"


def lock_path() -> Path:
    return deployment_dir() / LOCK_FILENAME


def runtime_config_path() -> Path:
    return deployment_dir() / RUNTIME_CONFIG_FILENAME


def make_run_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"


def _safe_json_load(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_run_state(run_id: str) -> dict[str, Any] | None:
    return _safe_json_load(run_state_path(run_id))


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, ensure_ascii=True, indent=2)
    last_error: Exception | None = None
    for _attempt in range(5):
        tmp_path = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
        try:
            tmp_path.write_text(content, encoding="utf-8")
            os.replace(tmp_path, path)
            return
        except PermissionError as exc:
            last_error = exc
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
            time.sleep(0.15)
    try:
        path.write_text(content, encoding="utf-8")
        return
    except Exception:
        if last_error is not None:
            raise last_error
        raise


RUNTIME_CONFIG_KEYS = (
    "GANDI_SFTP_HOST",
    "GANDI_SFTP_PORT",
    "GANDI_SFTP_DOMAIN",
    "GANDI_SFTP_USERNAME",
    "GANDI_SFTP_TOKEN",
    "GANDI_SFTP_REMOTE_PATH",
    "GANDI_DEPLOY_VERIFY_URL",
    "GANDI_DEPLOY_LOCAL_ROOT",
    "GANDI_DEPLOY_INCLUDE_PATHS",
)


def load_runtime_config() -> dict[str, str]:
    payload = _safe_json_load(runtime_config_path()) or {}
    config: dict[str, str] = {}
    for key in RUNTIME_CONFIG_KEYS:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            config[key] = text
    updated_at = payload.get("updated_at")
    if updated_at:
        config["updated_at"] = str(updated_at).strip()
    return config


def save_runtime_config(values: dict[str, Any]) -> dict[str, str]:
    current = load_runtime_config()
    for key in RUNTIME_CONFIG_KEYS:
        if key not in values:
            continue
        raw_value = values.get(key)
        text = str(raw_value or "").strip()
        if text:
            current[key] = text
    payload = {**current, "updated_at": now_iso()}
    save_json(runtime_config_path(), payload)
    return current


def cleanup_stale_lock() -> None:
    current_lock = _safe_json_load(lock_path())
    if not current_lock:
        if lock_path().exists():
            try:
                lock_path().unlink()
            except Exception:
                return
        return
    run_id = str(current_lock.get("run_id", "") or "").strip()
    if not run_id:
        try:
            lock_path().unlink()
        except Exception:
            return
        return
    run_state = load_run_state(run_id)
    if not run_state:
        try:
            lock_path().unlink()
        except Exception:
            return
        return
    pid = int(current_lock.get("pid", 0) or 0)
    if run_state.get("status") != "running" or (pid and not process_exists(pid)):
        if run_state.get("status") == "running" and pid and not process_exists(pid):
            run_state["status"] = "failed"
            run_state["completed_at"] = now_iso()
            run_state["error"] = "Processus de deploiement interrompu avant la fin du pipeline."
            save_json(run_state_path(run_id), run_state)
        try:
            lock_path().unlink()
        except Exception:
            return


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def get_active_run() -> dict[str, Any] | None:
    cleanup_stale_lock()
    active_lock = _safe_json_load(lock_path())
    if not active_lock:
        return None
    run_id = str(active_lock.get("run_id", "") or "").strip()
    if not run_id:
        return None
    run_state = load_run_state(run_id)
    if not run_state or run_state.get("status") != "running":
        return None
    return run_state


def acquire_run_lock(run_id: str) -> None:
    cleanup_stale_lock()
    payload = {
        "run_id": run_id,
        "pid": os.getpid(),
        "locked_at": now_iso(),
    }
    try:
        fd = os.open(lock_path(), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        active = get_active_run()
        active_id = active.get("id", "") if active else ""
        raise DeploymentBusyError(
            f"Un autre deploiement est deja en cours{f' ({active_id})' if active_id else ''}."
        ) from exc
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)


def release_run_lock(run_id: str) -> None:
    current_lock = _safe_json_load(lock_path())
    if not current_lock:
        return
    if str(current_lock.get("run_id", "") or "") != run_id:
        return
    try:
        lock_path().unlink()
    except Exception:
        return


def iter_recent_runs(limit: int = MAX_HISTORY_ITEMS) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in deployment_dir().glob(f"{RUN_FILE_PREFIX}*{RUN_FILE_SUFFIX}"):
        payload = _safe_json_load(path)
        if not payload:
            continue
        items.append(payload)
    items.sort(key=lambda item: item.get("started_at", ""), reverse=True)
    return items[:limit]


def deployment_config_from_env() -> tuple[DeploymentConfig | None, list[str]]:
    runtime_config = load_runtime_config()

    def _config_value(name: str, default: str = "") -> str:
        env_value = str(os.getenv(name, "") or "").strip()
        if env_value:
            return env_value
        runtime_value = str(runtime_config.get(name, "") or "").strip()
        if runtime_value:
            return runtime_value
        return default

    local_root = Path(_config_value("GANDI_DEPLOY_LOCAL_ROOT", str(settings.BASE_DIR))).resolve()
    host = _config_value("GANDI_SFTP_HOST", "sftp.sd3.gpaas.net")
    username = _config_value("GANDI_SFTP_USERNAME", "")
    token = _config_value("GANDI_SFTP_TOKEN", "")
    domain = _config_value("GANDI_SFTP_DOMAIN", "call.naumur.com")
    remote_path = _config_value("GANDI_SFTP_REMOTE_PATH", "")
    verify_url = _config_value("GANDI_DEPLOY_VERIFY_URL", "")
    include_paths_env = _config_value("GANDI_DEPLOY_INCLUDE_PATHS", "")
    port_value = _config_value("GANDI_SFTP_PORT", "22")
    include_paths = (
        tuple(
            item.strip().replace("\\", "/") for item in include_paths_env.split(",") if item.strip()
        )
        or DEFAULT_INCLUDE_PATHS
    )

    errors: list[str] = []
    if not host:
        errors.append("Variable manquante: GANDI_SFTP_HOST")
    if not username:
        errors.append("Variable manquante: GANDI_SFTP_USERNAME")
    if not token:
        errors.append("Variable manquante: GANDI_SFTP_TOKEN")
    if not domain:
        errors.append("Variable manquante: GANDI_SFTP_DOMAIN")
    if not local_root.exists():
        errors.append(f"Racine locale introuvable: {local_root}")
    try:
        port = int(port_value)
    except ValueError:
        errors.append("Variable invalide: GANDI_SFTP_PORT")
        port = 22

    if not verify_url and domain:
        verify_url = f"https://{domain}"

    if errors:
        return None, errors

    return (
        DeploymentConfig(
            host=host,
            port=port,
            username=username,
            token=token,
            domain=domain,
            remote_path=remote_path,
            verify_url=verify_url,
            local_root=local_root,
            include_paths=include_paths,
        ),
        [],
    )


def deployment_config_summary() -> dict[str, Any]:
    config, errors = deployment_config_from_env()
    runtime_config = load_runtime_config()
    username_value = ""
    if config:
        username_value = config.masked_username
    else:
        fallback_username = str(
            os.getenv("GANDI_SFTP_USERNAME", runtime_config.get("GANDI_SFTP_USERNAME", "")) or ""
        ).strip()
        if fallback_username:
            username_value = (
                f"{fallback_username[:6]}...{fallback_username[-4:]}"
                if len(fallback_username) > 10
                else fallback_username
            )
    return {
        "ready": not errors,
        "errors": errors,
        "host": (
            config.host
            if config
            else str(
                os.getenv(
                    "GANDI_SFTP_HOST", runtime_config.get("GANDI_SFTP_HOST", "sftp.sd3.gpaas.net")
                )
            )
        ),
        "port": (
            config.port
            if config
            else int(
                str(
                    os.getenv("GANDI_SFTP_PORT", runtime_config.get("GANDI_SFTP_PORT", "22"))
                    or "22"
                )
            )
        ),
        "domain": (
            config.domain
            if config
            else str(
                os.getenv(
                    "GANDI_SFTP_DOMAIN", runtime_config.get("GANDI_SFTP_DOMAIN", "call.naumur.com")
                )
            )
        ),
        "remote_path": (
            config.remote_path
            if config
            else str(
                os.getenv(
                    "GANDI_SFTP_REMOTE_PATH", runtime_config.get("GANDI_SFTP_REMOTE_PATH", "")
                )
            )
        ),
        "verify_url": (
            config.verify_url
            if config
            else str(
                os.getenv(
                    "GANDI_DEPLOY_VERIFY_URL", runtime_config.get("GANDI_DEPLOY_VERIFY_URL", "")
                )
            )
        ),
        "local_root": str(config.local_root if config else Path(settings.BASE_DIR)),
        "include_paths": list(config.include_paths if config else DEFAULT_INCLUDE_PATHS),
        "username_masked": username_value,
        "token_present": (
            bool(config.token)
            if config
            else bool(os.getenv("GANDI_SFTP_TOKEN", runtime_config.get("GANDI_SFTP_TOKEN", "")))
        ),
        "runtime_config_present": bool(runtime_config),
        "runtime_config_updated_at": runtime_config.get("updated_at", ""),
        "active_run": get_active_run(),
    }


def _include_paths_allow_staticfiles(
    include_paths: tuple[str, ...] = DEFAULT_INCLUDE_PATHS,
) -> bool:
    for include in include_paths:
        normalized = str(include or "").replace("\\", "/").strip("/")
        if normalized == "staticfiles" or normalized.startswith("staticfiles/"):
            return True
    return False


def should_ignore(
    relative_path: str,
    *,
    allow_staticfiles: bool = False,
) -> bool:
    normalized = relative_path.replace("\\", "/").strip("/")
    if not normalized:
        return False
    parts = normalized.split("/")
    name = parts[-1]
    ignored_dir_names = IGNORE_DIR_NAMES - {"staticfiles"} if allow_staticfiles else IGNORE_DIR_NAMES
    if any(part in ignored_dir_names for part in parts[:-1]):
        return True
    if name in IGNORE_FILE_NAMES:
        return True
    if any(name.endswith(suffix) for suffix in IGNORE_FILE_SUFFIXES):
        return True
    if (
        normalized.startswith("logs/")
        or normalized.startswith("media/")
        or (normalized.startswith("staticfiles/") and not allow_staticfiles)
    ):
        return True
    return False


def relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def remote_file_sha256(sftp, remote_path: str) -> str:
    hasher = hashlib.sha256()
    with sftp.open(remote_path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _add_manifest_file(
    manifest: dict[str, dict[str, Any]],
    *,
    local_root: Path,
    path: Path,
    allow_staticfiles: bool = False,
) -> None:
    if not path.is_file():
        return
    relative = relative_posix(path, local_root)
    entry = local_manifest_entry(local_root, relative, allow_staticfiles=allow_staticfiles)
    if entry is None:
        return
    manifest[relative] = entry


def local_manifest_entry(
    local_root: Path,
    relative_path: str,
    *,
    allow_staticfiles: bool = False,
) -> dict[str, Any] | None:
    normalized = relative_path.replace("\\", "/").strip("/")
    if not normalized or should_ignore(normalized, allow_staticfiles=allow_staticfiles):
        return None
    local_root_resolved = local_root.resolve()
    path = (local_root_resolved / normalized).resolve()
    try:
        path.relative_to(local_root_resolved)
    except ValueError:
        return None
    if not path.exists() or not path.is_file():
        return None
    stat_result = path.stat()
    return {
        "size": stat_result.st_size,
        "mtime": int(stat_result.st_mtime),
        "sha256": file_sha256(path),
    }


def build_local_manifest(
    local_root: Path, include_paths: tuple[str, ...] = DEFAULT_INCLUDE_PATHS
) -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = {}
    local_root_resolved = local_root.resolve()
    allow_staticfiles = _include_paths_allow_staticfiles(include_paths)
    for include in include_paths:
        candidate = (local_root_resolved / include).resolve()
        try:
            candidate.relative_to(local_root_resolved)
        except ValueError:
            continue
        if not candidate.exists():
            continue
        if candidate.is_file():
            _add_manifest_file(
                manifest,
                local_root=local_root_resolved,
                path=candidate,
                allow_staticfiles=allow_staticfiles,
            )
            continue
        for path in sorted(candidate.rglob("*")):
            _add_manifest_file(
                manifest,
                local_root=local_root_resolved,
                path=path,
                allow_staticfiles=allow_staticfiles,
            )
    return manifest


def remote_join(root: str, relative_path: str) -> str:
    return posixpath.join(root.rstrip("/"), relative_path.replace("\\", "/"))


def ensure_remote_dir(sftp, remote_dir: str) -> None:
    remote_dir = posixpath.normpath(remote_dir)
    if remote_dir in {"", "/", "."}:
        return
    parent = posixpath.dirname(remote_dir)
    if parent and parent not in {"", "/", "."} and parent != remote_dir:
        ensure_remote_dir(sftp, parent)
    try:
        sftp.stat(remote_dir)
    except OSError:
        sftp.mkdir(remote_dir)


def remote_path_exists(sftp, remote_path: str) -> bool:
    try:
        sftp.stat(remote_path)
        return True
    except OSError:
        return False


def remote_read_json(sftp, remote_path: str) -> dict[str, Any] | None:
    try:
        with sftp.open(remote_path, "r") as handle:
            return json.loads(handle.read())
    except Exception:
        return None


def remote_write_json(sftp, remote_path: str, payload: dict[str, Any]) -> None:
    ensure_remote_dir(sftp, posixpath.dirname(remote_path))
    with sftp.open(remote_path, "w") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, indent=2))


def remote_read_text(sftp, remote_path: str) -> str:
    try:
        with sftp.open(remote_path, "r") as handle:
            content = handle.read()
    except OSError:
        return ""
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace")
    return str(content)


def remote_write_text(sftp, remote_path: str, content: str) -> None:
    ensure_remote_dir(sftp, posixpath.dirname(remote_path))
    with sftp.open(remote_path, "w") as handle:
        handle.write(content)


def _app_env_values_from_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for key in APP_ENV_SYNC_KEYS:
        text = str(os.getenv(key, "") or "").strip()
        if text:
            values[key] = text
    return values


def _merge_env_content(existing_content: str, updates: dict[str, str]) -> str:
    if not updates:
        return existing_content

    remaining = dict(updates)
    rendered_lines: list[str] = []
    for raw_line in str(existing_content or "").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            rendered_lines.append(raw_line)
            continue

        key, _value = raw_line.split("=", 1)
        normalized_key = key.strip()
        if normalized_key in remaining:
            rendered_lines.append(f"{normalized_key}={remaining.pop(normalized_key)}")
        else:
            rendered_lines.append(raw_line)

    if rendered_lines and rendered_lines[-1].strip():
        rendered_lines.append("")
    for key in APP_ENV_SYNC_KEYS:
        if key in remaining:
            rendered_lines.append(f"{key}={remaining[key]}")
    return "\n".join(rendered_lines).rstrip() + "\n"


def sync_remote_app_env(sftp, *, remote_root: str) -> dict[str, Any]:
    updates = _app_env_values_from_env()
    remote_path = remote_join(remote_root, ".env.local")
    if not updates:
        return {
            "written": False,
            "remote_path": remote_path,
            "keys": [],
        }

    existing_content = remote_read_text(sftp, remote_path)
    if not existing_content.strip():
        # Le fichier .env.local est absent ou illisible sur le serveur distant.
        # On refuse de le créer de zéro pour éviter d'écraser la configuration
        # de production (DATABASE_URL, SECRET_KEY, etc.).
        return {
            "written": False,
            "remote_path": remote_path,
            "keys": [],
            "skipped_reason": ".env.local absent ou illisible — ecriture ignoree",
        }

    merged_content = _merge_env_content(existing_content, updates)
    remote_write_text(sftp, remote_path, merged_content)
    return {
        "written": True,
        "remote_path": remote_path,
        "keys": list(updates.keys()),
    }


def parse_iso_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def base_site_url(url: str) -> str:
    parsed = urlsplit(str(url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return ""
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def deployment_page_url(url: str) -> str:
    base_url = base_site_url(url)
    return f"{base_url}/deploiement/" if base_url else ""


def live_status_check_url(url: str) -> str:
    base_url = base_site_url(url)
    return f"{base_url}/deploiement/live/" if base_url else ""


def _cache_busted_url(url: str, *, run_id: str, attempt: int) -> str:
    if not url:
        return url
    parsed = urlsplit(url)
    extra_query = urlencode(
        {
            "_deploy_run": str(run_id or "").strip(),
            "_deploy_attempt": str(attempt),
        }
    )
    query = f"{parsed.query}&{extra_query}" if parsed.query else extra_query
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))


def requires_python_refresh(paths: list[str]) -> bool:
    return any(not path.startswith("static/") for path in paths)


def _http_json_check(url: str) -> dict[str, Any]:
    if not url:
        return {"ok": False, "message": "URL JSON de verification absente"}

    try:
        response = requests.get(
            url,
            timeout=HTTP_TIMEOUT_SECONDS,
            allow_redirects=True,
            headers={
                "Accept": "application/json",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
        )
        payload: dict[str, Any] | None = None
        try:
            raw_payload = response.json()
            if isinstance(raw_payload, dict):
                payload = raw_payload
        except ValueError:
            payload = None
        return {
            "ok": 200 <= response.status_code < 400 and payload is not None,
            "status_code": response.status_code,
            "final_url": response.url,
            "content_type": response.headers.get("Content-Type", ""),
            "payload": payload,
        }
    except requests.RequestException as exc:
        return {
            "ok": False,
            "message": str(exc),
        }


def read_remote_text_tail(
    sftp,
    remote_path: str,
    *,
    max_lines: int = 25,
    max_bytes: int = 24 * 1024,
) -> dict[str, Any]:
    try:
        stat_result = sftp.stat(remote_path)
    except OSError:
        return {"available": False, "path": remote_path, "lines": []}

    start_at = max(0, int(getattr(stat_result, "st_size", 0) or 0) - max_bytes)
    try:
        with sftp.open(remote_path, "rb") as handle:
            if start_at:
                handle.seek(start_at)
            raw = handle.read()
    except Exception as exc:
        return {
            "available": False,
            "path": remote_path,
            "lines": [],
            "error": str(exc),
        }

    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="replace")
    else:
        text = str(raw)

    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    return {
        "available": True,
        "path": remote_path,
        "lines": lines[-max_lines:],
    }


def request_python_refresh(
    sftp,
    *,
    remote_root: str,
    verify_url: str,
    run_id: str,
    mode: str,
) -> dict[str, Any]:
    requested_at = now_iso()
    marker_payload = {
        "run_id": run_id,
        "mode": mode,
        "status": "refresh_requested",
        "requested_refresh_at": requested_at,
        "deployment_page_url": deployment_page_url(verify_url),
        "live_status_url": live_status_check_url(verify_url),
        "site_url": base_site_url(verify_url),
    }
    marker_remote_path = remote_join(remote_root, LIVE_MARKER_FILENAME)
    remote_write_json(sftp, marker_remote_path, marker_payload)

    remote_wsgi_path = remote_join(remote_root, "wsgi.py")
    result = {
        "required": True,
        "requested_at": requested_at,
        "marker_written": True,
        "marker_remote_path": marker_remote_path,
        "wsgi_path": remote_wsgi_path,
        "deployment_page_url": marker_payload["deployment_page_url"],
        "live_status_url": marker_payload["live_status_url"],
        "site_url": marker_payload["site_url"],
        "reload_requested": False,
        "reload_method": "",
        "reloaded": False,
        "marker_seen": False,
        "message": "",
    }

    if not remote_path_exists(sftp, remote_wsgi_path):
        result["message"] = "Le fichier wsgi.py est introuvable sur le serveur."
        return result

    touch_time = int(time.time())
    try:
        sftp.utime(remote_wsgi_path, (touch_time, touch_time))
        result["reload_requested"] = True
        result["reload_method"] = "utime"
        result["message"] = "Le rechargement Python a ete demande en mettant a jour wsgi.py."
        return result
    except Exception as exc:
        result["reload_error"] = str(exc)

    try:
        with sftp.open(remote_wsgi_path, "rb") as handle:
            content = handle.read()
        with sftp.open(remote_wsgi_path, "wb") as handle:
            handle.write(content)
        result["reload_requested"] = True
        result["reload_method"] = "rewrite"
        result["message"] = "Le rechargement Python a ete demande en reecrivant wsgi.py."
    except Exception as exc:
        result["reload_error"] = str(exc)
        result["message"] = (
            "Le deploiement a ete transfere, mais le rechargement Python n'a pas pu etre demande automatiquement."  # noqa: E501
        )
    return result


def confirm_python_refresh(
    sftp,
    *,
    verify_url: str,
    run_id: str,
    refresh_request: dict[str, Any],
    state: "DeploymentRunState",
) -> dict[str, Any]:
    live_url = str(
        refresh_request.get("live_status_url", "") or live_status_check_url(verify_url)
    ).strip()
    if not refresh_request.get("required", True):
        refresh_request["reloaded"] = True
        refresh_request["message"] = (
            "Aucun fichier Python ou template n'a change, le rechargement du serveur n'etait pas necessaire."  # noqa: E501
        )
        return refresh_request

    if not live_url:
        refresh_request["message"] = (
            "Le lien public de verification du serveur Python est indisponible."
        )
        refresh_request["uwsgi_log_tail"] = read_remote_text_tail(sftp, REMOTE_UWSGI_LOG_PATH)
        return refresh_request

    if not refresh_request.get("reload_requested"):
        refresh_request["uwsgi_log_tail"] = read_remote_text_tail(sftp, REMOTE_UWSGI_LOG_PATH)
        return refresh_request

    requested_at = parse_iso_datetime(refresh_request.get("requested_at"))
    started_monotonic = time.monotonic()
    attempts = 0
    last_status_code: int | None = None
    last_message = ""
    last_final_url = live_url
    last_payload: dict[str, Any] | None = None

    while (time.monotonic() - started_monotonic) < LIVE_REFRESH_TIMEOUT_SECONDS:
        attempts += 1
        elapsed = time.monotonic() - started_monotonic
        progress = 96 + min(3, int((elapsed / LIVE_REFRESH_TIMEOUT_SECONDS) * 3))
        state.update_step(
            "verify",
            message=f"Attente du rechargement Python ({attempts})",
            progress=progress,
        )
        response = _http_json_check(_cache_busted_url(live_url, run_id=run_id, attempt=attempts))
        last_status_code = response.get("status_code")
        last_final_url = response.get("final_url", last_final_url) or last_final_url
        if response.get("message"):
            last_message = str(response["message"])
        payload = response.get("payload")
        if isinstance(payload, dict):
            last_payload = payload
            marker = payload.get("marker", {}) or {}
            app_booted_at = payload.get("app_booted_at")
            booted_at = parse_iso_datetime(app_booted_at)
            marker_seen = str(marker.get("run_id", "") or "") == run_id
            reloaded = bool(
                marker_seen and requested_at and booted_at and booted_at >= requested_at
            )
            if reloaded:
                refresh_request.update(
                    {
                        "reloaded": True,
                        "marker_seen": True,
                        "checked_url": response.get("final_url", live_url),
                        "status_code": last_status_code,
                        "attempts": attempts,
                        "app_booted_at": str(app_booted_at or ""),
                        "process_id": payload.get("process_id"),
                        "message": "Le serveur Python a confirme son rechargement apres le deploiement.",  # noqa: E501
                        "uwsgi_log_tail": read_remote_text_tail(sftp, REMOTE_UWSGI_LOG_PATH),
                    }
                )
                return refresh_request
            if marker_seen:
                refresh_request["marker_seen"] = True
            last_message = "La page de controle est joignable, mais le process Python n'a pas encore annonce son nouveau demarrage."  # noqa: E501
        time.sleep(LIVE_REFRESH_POLL_INTERVAL_SECONDS)

    refresh_request.update(
        {
            "reloaded": False,
            "checked_url": last_final_url,
            "status_code": last_status_code,
            "attempts": attempts,
            "marker_seen": bool(refresh_request.get("marker_seen")),
            "app_booted_at": str((last_payload or {}).get("app_booted_at", "") or ""),
            "process_id": (last_payload or {}).get("process_id"),
            "message": last_message
            or "Le serveur Python n'a pas confirme son rechargement dans le delai attendu.",
            "uwsgi_log_tail": read_remote_text_tail(sftp, REMOTE_UWSGI_LOG_PATH),
        }
    )
    return refresh_request


def _walk_remote_dir(
    sftp,
    remote_root: str,
    current_dir: str,
    *,
    allow_staticfiles: bool = False,
) -> dict[str, dict[str, Any]]:
    files: dict[str, dict[str, Any]] = {}
    stack = [current_dir]
    while stack:
        current_dir = stack.pop()
        for item in sftp.listdir_attr(current_dir):
            name = item.filename
            if name in {".", ".."}:
                continue
            full_path = posixpath.join(current_dir, name)
            relative = PurePosixPath(posixpath.relpath(full_path, remote_root)).as_posix()
            if should_ignore(relative, allow_staticfiles=allow_staticfiles):
                continue
            mode = item.st_mode
            if stat.S_ISDIR(mode):
                stack.append(full_path)
                continue
            if not stat.S_ISREG(mode):
                continue
            files[relative] = {
                "size": int(getattr(item, "st_size", 0) or 0),
                "mtime": int(getattr(item, "st_mtime", 0) or 0),
            }
    return files


def walk_remote_files(
    sftp,
    remote_root: str,
    *,
    include_paths: tuple[str, ...] = DEFAULT_INCLUDE_PATHS,
) -> dict[str, dict[str, Any]]:
    files: dict[str, dict[str, Any]] = {}
    allow_staticfiles = _include_paths_allow_staticfiles(include_paths)
    for include in include_paths:
        remote_path = remote_join(remote_root, include)
        try:
            remote_stat = sftp.stat(remote_path)
        except OSError:
            continue
        if stat.S_ISDIR(remote_stat.st_mode):
            files.update(
                _walk_remote_dir(
                    sftp,
                    remote_root,
                    remote_path,
                    allow_staticfiles=allow_staticfiles,
                )
            )
            continue
        if not stat.S_ISREG(remote_stat.st_mode):
            continue
        relative = PurePosixPath(posixpath.relpath(remote_path, remote_root)).as_posix()
        if should_ignore(relative, allow_staticfiles=allow_staticfiles):
            continue
        files[relative] = {
            "size": int(getattr(remote_stat, "st_size", 0) or 0),
            "mtime": int(getattr(remote_stat, "st_mtime", 0) or 0),
        }
    return files


def _candidate_remote_paths(config: DeploymentConfig) -> list[str]:
    domain = config.domain.strip().strip("/")
    candidates: list[str] = []
    if config.remote_path:
        candidates.append(config.remote_path)
    candidates.extend(
        [
            f"/vhosts/{domain}/htdocs",
            f"/lamp0/web/vhosts/{domain}/htdocs",
            f"/vhosts/{domain}",
            f"/lamp0/web/vhosts/{domain}",
            "/vhosts/default",
            "/lamp0/web/vhosts/default",
        ]
    )
    unique: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        normalized = posixpath.normpath(item)
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def discover_remote_root(sftp, config: DeploymentConfig) -> str:
    for candidate in _candidate_remote_paths(config):
        if remote_path_exists(sftp, candidate):
            return candidate

    for candidate in ("/vhosts", "/lamp0/web/vhosts"):
        if not remote_path_exists(sftp, candidate):
            continue
        try:
            entries = sorted(sftp.listdir(candidate))
        except OSError:
            continue
        if config.domain in entries:
            domain_path = posixpath.join(candidate, config.domain)
            htdocs_path = posixpath.join(domain_path, "htdocs")
            if remote_path_exists(sftp, htdocs_path):
                return htdocs_path
            return domain_path
        if "default" in entries:
            return posixpath.join(candidate, "default")

    raise DeploymentError(
        "Impossible de detecter automatiquement le dossier distant. "
        "Renseignez GANDI_SFTP_REMOTE_PATH dans .env.local."
    )


def compute_diff(
    *,
    local_manifest: dict[str, dict[str, Any]],
    remote_manifest: dict[str, dict[str, Any]] | None,
    remote_scan: dict[str, dict[str, Any]] | None,
    remote_root: str,
    sftp,
    state: "DeploymentRunState",
) -> tuple[list[str], list[str], list[str], list[str]]:
    local_paths = set(local_manifest)
    if remote_manifest is not None:
        remote_paths = set(remote_manifest)
        additions = sorted(local_paths - remote_paths)
        deletions = sorted(remote_paths - local_paths)
        modifications = sorted(
            path
            for path in (local_paths & remote_paths)
            if local_manifest[path]["sha256"] != str(remote_manifest[path].get("sha256", ""))
        )
        return additions, modifications, deletions, []

    remote_scan = remote_scan or {}
    remote_paths = set(remote_scan)
    additions = sorted(local_paths - remote_paths)
    common_paths = sorted(local_paths & remote_paths)
    modifications: list[str] = []
    for index, relative in enumerate(common_paths, start=1):
        local_item = local_manifest[relative]
        remote_item = remote_scan[relative]
        if int(local_item["size"]) != int(remote_item.get("size", 0)):
            modifications.append(relative)
            continue
        remote_hash = remote_file_sha256(sftp, remote_join(remote_root, relative))
        if remote_hash != local_item["sha256"]:
            modifications.append(relative)
        if index % 20 == 0:
            progress = 44 + int((index / max(len(common_paths), 1)) * 6)
            state.update_step(
                "diff",
                message=f"Comparaison de contenu {index}/{len(common_paths)}",
                progress=progress,
            )
    remote_untracked = sorted(remote_paths - local_paths)
    return additions, modifications, [], remote_untracked


def prune_empty_remote_dirs(sftp, remote_dir: str, stop_at: str) -> None:
    current = posixpath.normpath(remote_dir)
    stop_root = posixpath.normpath(stop_at)
    while current and current not in {".", "/"} and current.startswith(stop_root):
        if current == stop_root:
            return
        try:
            if sftp.listdir(current):
                return
            sftp.rmdir(current)
        except OSError:
            return
        current = posixpath.dirname(current)


class DeploymentRunState:
    def __init__(self, *, run_id: str, mode: str, config_summary: dict[str, Any]):
        self.run_id = run_id
        self.path = run_state_path(run_id)
        self.data = {
            "id": run_id,
            "mode": mode,
            "status": "pending",
            "progress_pct": 0,
            "started_at": now_iso(),
            "updated_at": now_iso(),
            "completed_at": None,
            "current_step": None,
            "config": config_summary,
            "summary": {
                "additions": 0,
                "modifications": 0,
                "deletions": 0,
                "remote_untracked": 0,
                "uploaded_files": 0,
                "deleted_files": 0,
                "uploaded_bytes": 0,
                "remote_path": "",
            },
            "diff": {
                "additions": [],
                "modifications": [],
                "deletions": [],
                "remote_untracked": [],
            },
            "verification": {},
            "report": {},
            "error": "",
            "logs": [],
            "steps": [
                {
                    "key": key,
                    "label": label,
                    "status": "pending",
                    "started_at": None,
                    "completed_at": None,
                    "message": "",
                }
                for key, label in STEP_DEFINITIONS
            ],
        }
        self._last_save_monotonic = 0.0
        self.save(force=True)

    def save(self, *, force: bool = False) -> None:
        if not force and (time.monotonic() - self._last_save_monotonic) < 0.2:
            return
        self.data["updated_at"] = now_iso()
        save_json(self.path, self.data)
        self._last_save_monotonic = time.monotonic()

    def _step(self, key: str) -> dict[str, Any]:
        for step in self.data["steps"]:
            if step["key"] == key:
                return step
        raise KeyError(f"Etape inconnue: {key}")

    def log(self, message: str, *, level: str = "info") -> None:
        self.data["logs"].append(
            {
                "at": now_iso(),
                "level": level,
                "message": message,
            }
        )
        if len(self.data["logs"]) > MAX_LOG_LINES:
            self.data["logs"] = self.data["logs"][-MAX_LOG_LINES:]
        self.save()

    def set_status(self, status: str, *, progress: int | None = None, error: str = "") -> None:
        self.data["status"] = status
        if progress is not None:
            self.data["progress_pct"] = max(0, min(100, int(progress)))
        if error:
            self.data["error"] = error
        self.save(force=status in {"completed", "failed"})

    def start_step(self, key: str, *, message: str = "", progress: int | None = None) -> None:
        step = self._step(key)
        if step["started_at"] is None:
            step["started_at"] = now_iso()
        step["status"] = "running"
        if message:
            step["message"] = message
        self.data["current_step"] = key
        self.data["status"] = "running"
        if progress is not None:
            self.data["progress_pct"] = max(0, min(100, int(progress)))
        self.save(force=True)

    def update_step(self, key: str, *, message: str = "", progress: int | None = None) -> None:
        step = self._step(key)
        if step["started_at"] is None:
            step["started_at"] = now_iso()
        step["status"] = "running"
        if message:
            step["message"] = message
        self.data["current_step"] = key
        if progress is not None:
            self.data["progress_pct"] = max(0, min(100, int(progress)))
        self.save()

    def complete_step(self, key: str, *, message: str = "", progress: int | None = None) -> None:
        step = self._step(key)
        if step["started_at"] is None:
            step["started_at"] = now_iso()
        step["completed_at"] = now_iso()
        step["status"] = "completed"
        if message:
            step["message"] = message
        if progress is not None:
            self.data["progress_pct"] = max(0, min(100, int(progress)))
        self.save(force=True)

    def skip_step(self, key: str, *, message: str = "") -> None:
        step = self._step(key)
        if step["started_at"] is None:
            step["started_at"] = now_iso()
        step["completed_at"] = now_iso()
        step["status"] = "skipped"
        if message:
            step["message"] = message
        self.save()

    def set_diff(
        self,
        *,
        additions: list[str],
        modifications: list[str],
        deletions: list[str],
        remote_untracked: list[str],
        remote_path: str,
    ) -> None:
        self.data["diff"] = {
            "additions": additions,
            "modifications": modifications,
            "deletions": deletions,
            "remote_untracked": remote_untracked,
        }
        self.data["summary"].update(
            {
                "additions": len(additions),
                "modifications": len(modifications),
                "deletions": len(deletions),
                "remote_untracked": len(remote_untracked),
                "remote_path": remote_path,
            }
        )
        self.save(force=True)

    def set_verification(self, payload: dict[str, Any]) -> None:
        self.data["verification"] = payload
        self.save()

    def finalize(self, *, status: str, progress: int, error: str = "") -> None:
        self.data["status"] = status
        self.data["progress_pct"] = max(0, min(100, int(progress)))
        self.data["completed_at"] = now_iso()
        if error:
            self.data["error"] = error
        self.save(force=True)


def _sftp_put_with_retry(
    sftp, local_path: str, remote_path: str, callback=None, retries: int = 3
) -> None:
    """Upload a file over SFTP, retrying on 'size mismatch in put!' errors."""
    for attempt in range(1, retries + 1):
        try:
            sftp.put(local_path, remote_path, callback=callback)
            return
        except OSError as exc:
            msg = str(exc).lower()
            if "size mismatch" not in msg or attempt >= retries:
                raise
            time.sleep(1 * attempt)


def _connect_sftp(config: DeploymentConfig):
    if paramiko is None:
        raise DeploymentError(
            "La dependance 'paramiko' est absente. Installez-la pour activer le deploiement Gandi."
        )
    transport = paramiko.Transport((config.host, config.port))
    transport.banner_timeout = 30
    transport.auth_timeout = 30
    transport.connect(username=config.username, password=config.token)
    sftp = paramiko.SFTPClient.from_transport(transport)
    return transport, sftp


def _http_check(url: str) -> dict[str, Any]:
    if not url:
        return {"ok": False, "message": "URL de verification absente"}

    try:
        response = requests.get(
            url,
            timeout=HTTP_TIMEOUT_SECONDS,
            allow_redirects=True,
            headers={
                "Accept": "text/html,*/*",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
        )
        return {
            "ok": 200 <= response.status_code < 400,
            "status_code": response.status_code,
            "final_url": response.url,
        }
    except requests.RequestException as exc:
        return {
            "ok": False,
            "message": str(exc),
        }


def _http_check_with_retries(
    url: str,
    *,
    attempts: int = PUBLIC_HTTP_CHECK_ATTEMPTS,
    delay_seconds: int = PUBLIC_HTTP_CHECK_RETRY_DELAY_SECONDS,
) -> dict[str, Any]:
    total_attempts = max(1, attempts)
    last_result: dict[str, Any] = {}
    for attempt in range(1, total_attempts + 1):
        last_result = _http_check(url)
        last_result["attempts"] = attempt
        if last_result.get("ok"):
            return last_result
        if attempt < total_attempts:
            time.sleep(max(0, delay_seconds))
    return last_result


def _live_refresh_error_message(live_refresh: dict[str, Any]) -> str:
    parts = ["Le serveur Python n'a pas confirme son rechargement."]
    message = str(live_refresh.get("message", "") or "").strip()
    if message:
        parts.append(message)
    status_code = live_refresh.get("status_code")
    if status_code:
        parts.append(f"Dernier statut live: HTTP {status_code}.")
    if live_refresh.get("marker_seen"):
        parts.append("Le marqueur du run a ete vu.")
    app_booted_at = str(live_refresh.get("app_booted_at", "") or "").strip()
    if app_booted_at:
        parts.append(f"Dernier demarrage observe: {app_booted_at}.")
    checked_url = str(live_refresh.get("checked_url", "") or "").strip()
    if checked_url:
        parts.append(f"URL controlee: {checked_url}.")
    return " ".join(parts)


def _http_check_error_message(http_result: dict[str, Any]) -> str:
    parts = ["Le site public n'a pas repondu correctement apres le deploiement."]
    attempts = http_result.get("attempts")
    if attempts:
        parts.append(f"Tentatives: {attempts}.")
    status_code = http_result.get("status_code")
    if status_code:
        parts.append(f"Dernier statut HTTP: {status_code}.")
    message = str(http_result.get("message", "") or "").strip()
    if message:
        parts.append(message)
    final_url = str(http_result.get("final_url", "") or "").strip()
    if final_url:
        parts.append(f"URL controlee: {final_url}.")
    return " ".join(parts)


def _record_report_and_notification(state: DeploymentRunState) -> None:
    try:
        state.log("Generation du rapport de deploiement.")
        report_meta = record_and_notify_deployment(state.data)
        state.data["report"] = report_meta
        email_meta = report_meta.get("email", {}) or {}
        if email_meta.get("sent"):
            state.log(
                "Notification email envoyee a " + ", ".join(email_meta.get("recipients", []) or []),
            )
        else:
            state.log(
                "Notification email non envoyee: "
                + str(email_meta.get("error", "raison inconnue")),
                level="warning",
            )
        state.save(force=True)
    except Exception as exc:
        state.data["report"] = {
            "email": {"sent": False, "error": str(exc)},
        }
        state.log(
            f"Echec lors de l'enregistrement du rapport ou de l'envoi email: {exc}", level="error"
        )
        state.log(traceback.format_exc(), level="error")
        state.save(force=True)


def run_deployment(*, run_id: str, mode: str = "deploy") -> dict[str, Any]:
    config, errors = deployment_config_from_env()
    summary = deployment_config_summary()
    state = DeploymentRunState(run_id=run_id, mode=mode, config_summary=summary)
    if errors or config is None:
        error_message = " ; ".join(errors) if errors else "Configuration Gandi incomplete."
        state.log(error_message, level="error")
        state.finalize(status="failed", progress=0, error=error_message)
        _record_report_and_notification(state)
        return state.data

    transport = None
    sftp = None
    uploaded_paths: list[str] = []
    deleted_paths: list[str] = []
    remote_root = ""

    try:
        acquire_run_lock(run_id)
        state.log("Preparation du pipeline de deploiement.")
        state.start_step("prepare", message="Verification de la configuration", progress=3)
        state.complete_step("prepare", message="Configuration validee", progress=8)

        state.start_step("connect", message=f"Connexion a {config.host}", progress=10)
        transport, sftp = _connect_sftp(config)
        state.log(f"Connexion SFTP etablie vers {config.host}:{config.port}.")
        state.complete_step("connect", message="Connexion reussie", progress=18)

        state.start_step("discover", message="Detection du repertoire cible", progress=20)
        remote_root = discover_remote_root(sftp, config)
        state.log(f"Repertoire distant detecte: {remote_root}")
        state.complete_step("discover", message=remote_root, progress=24)

        state.start_step("local_scan", message="Calcul du manifeste local", progress=26)
        local_manifest = build_local_manifest(config.local_root, include_paths=config.include_paths)
        state.log(f"{len(local_manifest)} fichiers locaux prets a etre compares.")
        state.complete_step("local_scan", message=f"{len(local_manifest)} fichiers", progress=34)

        state.start_step("remote_scan", message="Chargement du manifeste distant", progress=36)
        remote_manifest_path = remote_join(remote_root, MANIFEST_FILENAME)
        raw_remote_manifest = remote_read_json(sftp, remote_manifest_path)
        remote_manifest = None
        remote_scan = None
        if isinstance(raw_remote_manifest, dict) and isinstance(
            raw_remote_manifest.get("files"), dict
        ):
            remote_manifest = raw_remote_manifest["files"]
            state.log(f"Manifeste distant charge ({len(remote_manifest)} fichiers suivis).")
        else:
            remote_scan = walk_remote_files(sftp, remote_root, include_paths=config.include_paths)
            state.log(
                "Aucun manifeste distant detecte. Analyse initiale en mode securise, "
                "sans suppression des fichiers distants deja presents."
            )
        state.complete_step(
            "remote_scan",
            message=(
                f"{len(remote_manifest)} fichiers suivis"
                if remote_manifest is not None
                else f"{len(remote_scan or {})} fichiers detectes"
            ),
            progress=42,
        )

        state.start_step("diff", message="Comparaison locale / distante", progress=44)
        additions, modifications, deletions, remote_untracked = compute_diff(
            local_manifest=local_manifest,
            remote_manifest=remote_manifest,
            remote_scan=remote_scan,
            remote_root=remote_root,
            sftp=sftp,
            state=state,
        )
        state.set_diff(
            additions=additions,
            modifications=modifications,
            deletions=deletions,
            remote_untracked=remote_untracked,
            remote_path=remote_root,
        )
        state.log(
            f"Changements detects: {len(additions)} ajouts, {len(modifications)} modifications, "
            f"{len(deletions)} suppressions."
        )
        if remote_untracked:
            state.log(
                f"{len(remote_untracked)} fichiers distants existants restent non suivis "
                "tant qu'un premier manifeste n'a pas ete pose."
            )
        state.complete_step("diff", message="Comparaison terminee", progress=50)

        if mode == "preview":
            state.skip_step("upload", message="Aucun transfert en mode previsualisation")
            state.skip_step("delete", message="Aucune suppression en mode previsualisation")
            state.skip_step("verify", message="Verification reservee au deploiement")
            state.finalize(status="completed", progress=100)
            _record_report_and_notification(state)
            return state.data

        transfer_paths = additions + modifications
        refreshed_transfer_paths: list[str] = []
        for relative in transfer_paths:
            entry = local_manifest_entry(config.local_root, relative)
            if entry is None:
                raise DeploymentError(
                    f"Fichier local introuvable juste avant transfert: {relative}"
                )
            if local_manifest.get(relative) != entry:
                local_manifest[relative] = entry
                refreshed_transfer_paths.append(relative)
        if refreshed_transfer_paths:
            state.log(
                f"{len(refreshed_transfer_paths)} fichier(s) ont change localement pendant l'analyse. "  # noqa: E501
                "Le snapshot de transfert a ete mis a jour juste avant l'envoi.",
                level="warning",
            )
        total_upload_bytes = sum(int(local_manifest[path]["size"]) for path in transfer_paths) or 1
        uploaded_bytes = 0

        state.start_step("upload", message="Transfert des fichiers modifies", progress=54)
        for index, relative in enumerate(transfer_paths, start=1):
            local_path = config.local_root / relative
            remote_path = remote_join(remote_root, relative)
            ensure_remote_dir(sftp, posixpath.dirname(remote_path))

            last_sent = -1

            def _callback(bytes_sent: int, total_bytes: int) -> None:
                nonlocal last_sent, uploaded_bytes
                delta = max(0, bytes_sent - last_sent)
                last_sent = bytes_sent
                uploaded_bytes += delta
                progress = 54 + int((uploaded_bytes / total_upload_bytes) * 28)
                state.update_step(
                    "upload",
                    message=f"{index}/{len(transfer_paths)} - {relative}",
                    progress=progress,
                )

            _sftp_put_with_retry(sftp, str(local_path), remote_path, callback=_callback)
            if last_sent < 0:
                uploaded_bytes += int(local_manifest[relative]["size"])
            uploaded_paths.append(relative)
            state.log(f"Transfert termine: {relative}")

        app_env_sync = sync_remote_app_env(sftp, remote_root=remote_root)
        if app_env_sync.get("written"):
            state.log(
                "Configuration applicative synchronisee vers .env.local: "
                + ", ".join(app_env_sync.get("keys", [])),
            )
        else:
            state.log("Aucune variable applicative Microsoft a synchroniser pour ce deploiement.")

        manifest_payload = {
            "generated_at": now_iso(),
            "domain": config.domain,
            "remote_root": remote_root,
            "files": local_manifest,
        }
        remote_write_json(sftp, remote_manifest_path, manifest_payload)
        state.data["summary"]["uploaded_files"] = len(uploaded_paths)
        state.data["summary"]["uploaded_bytes"] = sum(
            int(local_manifest[path]["size"]) for path in uploaded_paths
        )
        state.data["summary"]["app_env_sync"] = app_env_sync
        state.complete_step(
            "upload",
            message=f"{len(uploaded_paths)} fichiers transferes",
            progress=84,
        )

        state.start_step(
            "delete", message="Suppression des fichiers suivis supprimes localement", progress=86
        )
        for index, relative in enumerate(deletions, start=1):
            remote_path = remote_join(remote_root, relative)
            sftp.remove(remote_path)
            prune_empty_remote_dirs(sftp, posixpath.dirname(remote_path), remote_root)
            deleted_paths.append(relative)
            state.update_step(
                "delete",
                message=f"{index}/{len(deletions)} - {relative}",
                progress=86 + int((index / max(len(deletions), 1)) * 8),
            )
            state.log(f"Suppression distante terminee: {relative}")
        state.data["summary"]["deleted_files"] = len(deleted_paths)
        state.complete_step(
            "delete",
            message=f"{len(deleted_paths)} fichiers supprimes",
            progress=94,
        )

        state.start_step("verify", message="Verification des hashes et du site public", progress=95)
        verification_errors: list[str] = []
        for relative in uploaded_paths:
            remote_path = remote_join(remote_root, relative)
            expected_size = int(local_manifest[relative]["size"])
            remote_stat = None
            for _attempt in range(6):
                try:
                    remote_stat = sftp.stat(remote_path)
                except OSError:
                    break
                actual = int(getattr(remote_stat, "st_size", 0) or 0)
                if actual == expected_size:
                    break
                time.sleep(2)
            if remote_stat is None:
                verification_errors.append(
                    f"Fichier distant introuvable apres transfert: {relative}"
                )
                continue
            if int(getattr(remote_stat, "st_size", 0) or 0) != expected_size:
                verification_errors.append(f"Taille distante invalide: {relative}")

        for relative in deleted_paths:
            if remote_path_exists(sftp, remote_join(remote_root, relative)):
                verification_errors.append(f"Fichier encore present apres suppression: {relative}")

        manifest_remote = remote_read_json(sftp, remote_manifest_path)
        if not manifest_remote:
            verification_errors.append("Le manifeste distant n'a pas pu etre relu.")

        changed_paths = uploaded_paths + deleted_paths
        if requires_python_refresh(changed_paths):
            live_refresh = request_python_refresh(
                sftp,
                remote_root=remote_root,
                verify_url=config.verify_url,
                run_id=run_id,
                mode=mode,
            )
            state.log(live_refresh.get("message", "Demande de rechargement Python envoyee."))
            live_refresh = confirm_python_refresh(
                sftp,
                verify_url=config.verify_url,
                run_id=run_id,
                refresh_request=live_refresh,
                state=state,
            )
            state.log(live_refresh.get("message", "Verification du rechargement Python terminee."))
            if not live_refresh.get("reloaded"):
                verification_errors.append(_live_refresh_error_message(live_refresh))
        else:
            live_refresh = {
                "required": False,
                "reloaded": True,
                "message": "Aucun fichier Python ou template n'a change, le rechargement du serveur n'etait pas necessaire.",  # noqa: E501
                "deployment_page_url": deployment_page_url(config.verify_url),
                "live_status_url": live_status_check_url(config.verify_url),
                "site_url": base_site_url(config.verify_url),
            }
            state.log(live_refresh["message"])

        http_result = _http_check_with_retries(config.verify_url)
        if not http_result.get("ok"):
            verification_errors.append(_http_check_error_message(http_result))
        verification_payload = {
            "uploaded_checked": len(uploaded_paths),
            "deleted_checked": len(deleted_paths),
            "remote_manifest": bool(manifest_remote),
            "http_check": http_result,
            "live_refresh": live_refresh,
            "errors": verification_errors,
        }
        state.set_verification(verification_payload)

        if verification_errors:
            raise DeploymentError(" ; ".join(verification_errors))

        if http_result.get("ok"):
            state.log(
                f"Verification HTTP reussie ({http_result.get('status_code')}) via "
                f"{http_result.get('final_url', config.verify_url)}."
            )
        else:
            state.log(
                "Verification HTTP non concluante: "
                f"{http_result.get('message') or http_result.get('status_code')}",
                level="warning",
            )

        state.complete_step("verify", message="Verification terminee", progress=100)
        state.finalize(status="completed", progress=100)
        _record_report_and_notification(state)
        return state.data
    except Exception as exc:
        state.log(str(exc), level="error")
        state.log(traceback.format_exc(), level="error")
        state.finalize(status="failed", progress=state.data.get("progress_pct", 0), error=str(exc))
        _record_report_and_notification(state)
        return state.data
    finally:
        if sftp is not None:
            try:
                sftp.close()
            except Exception:
                pass
        if transport is not None:
            try:
                transport.close()
            except Exception:
                pass
        release_run_lock(run_id)

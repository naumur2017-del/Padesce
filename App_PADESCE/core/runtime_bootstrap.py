from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_STATE_DIR = ".runtime"
RUNTIME_REQUIREMENTS_STAMP = "requirements.sha256"
RUNTIME_REQUIRED_MODULES = (
    "langchain_core",
    "langchain_anthropic",
    "langgraph",
)


def _project_root(base_dir: Path | str | None = None) -> Path:
    return Path(base_dir).resolve() if base_dir is not None else PROJECT_ROOT


def requirements_path(base_dir: Path | str | None = None) -> Path:
    return _project_root(base_dir) / "requirements.txt"


def requirements_stamp_path(base_dir: Path | str | None = None) -> Path:
    return _project_root(base_dir) / RUNTIME_STATE_DIR / RUNTIME_REQUIREMENTS_STAMP


def requirements_hash(requirements_file: Path) -> str:
    return hashlib.sha256(requirements_file.read_bytes()).hexdigest()


def required_modules_available(module_names: Iterable[str] = RUNTIME_REQUIRED_MODULES) -> bool:
    return all(importlib.util.find_spec(name) is not None for name in module_names)


def runtime_dependencies_ready(
    *,
    base_dir: Path | str | None = None,
    module_checker: Callable[[Iterable[str]], bool] = required_modules_available,
) -> bool:
    requirements_file = requirements_path(base_dir)
    stamp_file = requirements_stamp_path(base_dir)
    if not requirements_file.exists() or not stamp_file.exists():
        return False

    current_hash = requirements_hash(requirements_file)
    stamped_hash = stamp_file.read_text(encoding="utf-8").strip()
    if stamped_hash != current_hash:
        return False

    return module_checker(RUNTIME_REQUIRED_MODULES)


def ensure_runtime_dependencies(
    *,
    base_dir: Path | str | None = None,
    runner: Callable[..., object] = subprocess.run,
    module_checker: Callable[[Iterable[str]], bool] = required_modules_available,
) -> bool:
    root = _project_root(base_dir)
    requirements_file = requirements_path(root)
    if not requirements_file.exists():
        raise FileNotFoundError(f"requirements.txt introuvable: {requirements_file}")

    if runtime_dependencies_ready(base_dir=root, module_checker=module_checker):
        print("[runtime] Dependances deja satisfaites.")
        return False

    pip_commands: Sequence[list[str]] = (
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--upgrade",
            "pip",
        ],
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            str(requirements_file),
        ],
    )

    for command in pip_commands:
        runner(command, check=True, cwd=str(root))

    stamp_file = requirements_stamp_path(root)
    stamp_file.parent.mkdir(parents=True, exist_ok=True)
    stamp_file.write_text(requirements_hash(requirements_file), encoding="utf-8")
    print("[runtime] Dependances runtime synchronisees.")
    return True


def main() -> int:
    ensure_runtime_dependencies()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

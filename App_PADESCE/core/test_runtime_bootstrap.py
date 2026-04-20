from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from django.test import SimpleTestCase

from App_PADESCE.core.runtime_bootstrap import (
    RUNTIME_REQUIRED_MODULES,
    ensure_runtime_dependencies,
    requirements_hash,
    requirements_path,
    requirements_stamp_path,
    runtime_dependencies_ready,
)


class RuntimeBootstrapTests(SimpleTestCase):
    def test_runtime_dependencies_ready_is_false_without_stamp(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            requirements_path(root).write_text("django==6.0\n", encoding="utf-8")

            ready = runtime_dependencies_ready(
                base_dir=root,
                module_checker=lambda module_names: True,
            )

        self.assertFalse(ready)

    def test_runtime_dependencies_ready_is_true_with_matching_stamp(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            requirements_file = requirements_path(root)
            requirements_file.write_text("langchain-core>=0.3.0\n", encoding="utf-8")
            requirements_stamp_path(root).parent.mkdir(parents=True, exist_ok=True)
            requirements_stamp_path(root).write_text(
                requirements_hash(requirements_file),
                encoding="utf-8",
            )

            ready = runtime_dependencies_ready(
                base_dir=root,
                module_checker=lambda module_names: tuple(module_names) == RUNTIME_REQUIRED_MODULES,
            )

        self.assertTrue(ready)

    def test_ensure_runtime_dependencies_runs_pip_and_writes_stamp(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            requirements_file = requirements_path(root)
            requirements_file.write_text("langchain-core>=0.3.0\n", encoding="utf-8")
            runner = Mock()
            expected_hash = requirements_hash(requirements_file)

            changed = ensure_runtime_dependencies(
                base_dir=root,
                runner=runner,
                module_checker=lambda module_names: False,
            )

            stamp_value = requirements_stamp_path(root).read_text(encoding="utf-8").strip()

        self.assertTrue(changed)
        self.assertEqual(runner.call_count, 2)
        self.assertEqual(stamp_value, expected_hash)

    def test_ensure_runtime_dependencies_skips_install_when_runtime_is_ready(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            requirements_file = requirements_path(root)
            requirements_file.write_text("langchain-core>=0.3.0\n", encoding="utf-8")
            requirements_stamp_path(root).parent.mkdir(parents=True, exist_ok=True)
            requirements_stamp_path(root).write_text(
                requirements_hash(requirements_file),
                encoding="utf-8",
            )
            runner = Mock()

            changed = ensure_runtime_dependencies(
                base_dir=root,
                runner=runner,
                module_checker=lambda module_names: True,
            )

        self.assertFalse(changed)
        runner.assert_not_called()

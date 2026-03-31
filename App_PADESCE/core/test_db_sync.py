from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from App_PADESCE.core.db_sync import sync_sqlite_databases


class SqliteSyncTests(SimpleTestCase):
    def test_dry_run_reports_changes_without_writing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            target = base / "target.sqlite3"
            source = base / "source.sqlite3"
            self._create_people_db(target, [(1, "Alice", "2026-03-19 08:00:00")])
            self._create_people_db(
                source,
                [(1, "Alice maj", "2026-03-19 09:00:00"), (2, "Bob", "2026-03-19 09:05:00")],
            )

            result = sync_sqlite_databases(
                target_path=target,
                source_paths=[source],
                include_tables=["people"],
                dry_run=True,
                backup=False,
            )

            self.assertEqual(result.inserted, 1)
            self.assertEqual(result.updated, 1)
            with closing(sqlite3.connect(target)) as conn:
                rows = conn.execute("SELECT id, name FROM people ORDER BY id").fetchall()
            self.assertEqual(rows, [(1, "Alice")])

    def test_newer_strategy_keeps_latest_row(self) -> None:
        with TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            target = base / "target.sqlite3"
            source = base / "source.sqlite3"
            self._create_people_db(
                target,
                [(1, "Alice cible", "2026-03-19 10:00:00"), (2, "Bob cible", "2026-03-19 12:00:00")],
            )
            self._create_people_db(
                source,
                [(1, "Alice source", "2026-03-19 11:00:00"), (2, "Bob source", "2026-03-19 11:30:00"), (3, "Charly source", "2026-03-19 11:45:00")],
            )

            result = sync_sqlite_databases(
                target_path=target,
                source_paths=[source],
                include_tables=["people"],
                backup=False,
            )

            self.assertEqual(result.inserted, 1)
            self.assertEqual(result.updated, 1)
            self.assertEqual(result.skipped_conflicts, 1)
            with closing(sqlite3.connect(target)) as conn:
                rows = conn.execute("SELECT id, name, updated_at FROM people ORDER BY id").fetchall()
            self.assertEqual(
                rows,
                [(1, "Alice source", "2026-03-19 11:00:00"), (2, "Bob cible", "2026-03-19 12:00:00"), (3, "Charly source", "2026-03-19 11:45:00")],
            )

    def test_source_strategy_updates_without_timestamp(self) -> None:
        with TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            target = base / "target.sqlite3"
            source = base / "source.sqlite3"
            self._create_notes_db(target, [(1, "ancienne valeur")])
            self._create_notes_db(source, [(1, "nouvelle valeur"), (2, "autre note")])

            result = sync_sqlite_databases(
                target_path=target,
                source_paths=[source],
                include_tables=["notes"],
                conflict_strategy="source",
                backup=False,
            )

            self.assertEqual(result.inserted, 1)
            self.assertEqual(result.updated, 1)
            with closing(sqlite3.connect(target)) as conn:
                rows = conn.execute("SELECT id, body FROM notes ORDER BY id").fetchall()
            self.assertEqual(rows, [(1, "nouvelle valeur"), (2, "autre note")])

    def _create_people_db(self, path: Path, rows: list[tuple[int, str, str]]) -> None:
        with closing(sqlite3.connect(path)) as conn:
            conn.execute("CREATE TABLE people (id INTEGER PRIMARY KEY, name TEXT NOT NULL, updated_at TEXT)")
            conn.executemany("INSERT INTO people (id, name, updated_at) VALUES (?, ?, ?)", rows)
            conn.commit()

    def _create_notes_db(self, path: Path, rows: list[tuple[int, str]]) -> None:
        with closing(sqlite3.connect(path)) as conn:
            conn.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT NOT NULL)")
            conn.executemany("INSERT INTO notes (id, body) VALUES (?, ?)", rows)
            conn.commit()

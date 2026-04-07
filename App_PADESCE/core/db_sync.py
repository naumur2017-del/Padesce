from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

DEFAULT_EXCLUDED_TABLES = {
    "django_admin_log",
    "django_migrations",
    "django_session",
    "core_useractivity",
}
TIMESTAMP_CANDIDATE_COLUMNS = (
    "updated_at",
    "modified_at",
    "resolved_at",
    "seen_at",
    "last_seen",
    "timestamp",
    "date_heure",
    "sent_at",
    "heure_enregistrement",
    "last_login",
    "date_joined",
    "created_at",
)
CONFLICT_STRATEGIES = {"newer", "source", "target"}


@dataclass(slots=True)
class TableSyncResult:
    table_name: str
    source_rows: int = 0
    inserted: int = 0
    updated: int = 0
    skipped_conflicts: int = 0
    identical: int = 0
    skipped: bool = False
    reason: str = ""


@dataclass(slots=True)
class SourceSyncResult:
    source_path: Path
    tables: list[TableSyncResult] = field(default_factory=list)
    missing_in_target: list[str] = field(default_factory=list)
    missing_in_source: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def inserted(self) -> int:
        return sum(item.inserted for item in self.tables)

    @property
    def updated(self) -> int:
        return sum(item.updated for item in self.tables)

    @property
    def skipped_conflicts(self) -> int:
        return sum(item.skipped_conflicts for item in self.tables)


@dataclass(slots=True)
class SyncResult:
    target_path: Path
    source_results: list[SourceSyncResult]
    dry_run: bool
    conflict_strategy: str
    backup_path: Path | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def inserted(self) -> int:
        return sum(source.inserted for source in self.source_results)

    @property
    def updated(self) -> int:
        return sum(source.updated for source in self.source_results)

    @property
    def skipped_conflicts(self) -> int:
        return sum(source.skipped_conflicts for source in self.source_results)


@dataclass(slots=True)
class TablePlan:
    table_name: str
    columns: list[str]
    pk_columns: list[str]
    timestamp_columns: list[str]

    @property
    def non_pk_columns(self) -> list[str]:
        return [column for column in self.columns if column not in self.pk_columns]


def sync_sqlite_databases(
    *,
    target_path: str | Path,
    source_paths: Sequence[str | Path],
    include_tables: Sequence[str] | None = None,
    exclude_tables: Sequence[str] | None = None,
    conflict_strategy: str = "newer",
    dry_run: bool = False,
    backup: bool = True,
    backup_dir: str | Path | None = None,
    timeout_seconds: int = 60,
) -> SyncResult:
    if conflict_strategy not in CONFLICT_STRATEGIES:
        raise ValueError(f"Strategie invalide: {conflict_strategy}")
    target = _normalize_path(target_path)
    if not target.exists():
        raise FileNotFoundError(f"Base cible introuvable: {target}")
    sources = _normalize_source_paths(source_paths, target)
    include_set = set(include_tables or [])
    exclude_set = set(DEFAULT_EXCLUDED_TABLES)
    exclude_set.update(exclude_tables or [])
    if include_set:
        exclude_set.difference_update(include_set)
    backup_path = None
    if not dry_run and backup:
        backup_path = _create_sqlite_backup(target, backup_dir)

    warnings: list[str] = []
    source_results: list[SourceSyncResult] = []
    target_conn = sqlite3.connect(target, timeout=timeout_seconds)
    try:
        target_conn.row_factory = sqlite3.Row
        _execute(target_conn, "PRAGMA busy_timeout = 60000")
        target_tables = _get_table_names(target_conn, schema="main")
        for source_path in sources:
            source_results.append(
                _sync_one_source(
                    target_conn=target_conn,
                    source_path=source_path,
                    target_tables=target_tables,
                    include_tables=include_set,
                    exclude_tables=exclude_set,
                    conflict_strategy=conflict_strategy,
                    dry_run=dry_run,
                    warnings=warnings,
                )
            )
    finally:
        target_conn.close()
    return SyncResult(
        target_path=target,
        source_results=source_results,
        dry_run=dry_run,
        conflict_strategy=conflict_strategy,
        backup_path=backup_path,
        warnings=warnings,
    )


def _sync_one_source(
    *,
    target_conn: sqlite3.Connection,
    source_path: Path,
    target_tables: set[str],
    include_tables: set[str],
    exclude_tables: set[str],
    conflict_strategy: str,
    dry_run: bool,
    warnings: list[str],
) -> SourceSyncResult:
    alias = "source_db"
    result = SourceSyncResult(source_path=source_path)
    _execute(target_conn, f"ATTACH DATABASE ? AS {alias}", (str(source_path),))
    try:
        source_tables = _get_table_names(target_conn, schema=alias)
        selected_tables = include_tables or (source_tables & target_tables)
        common_tables = (selected_tables & target_tables & source_tables) - exclude_tables
        result.missing_in_target.extend(sorted((selected_tables & source_tables) - target_tables))
        result.missing_in_source.extend(sorted((selected_tables & target_tables) - source_tables))
        if result.missing_in_target:
            result.warnings.append(
                "Tables absentes de la cible: " + ", ".join(result.missing_in_target)
            )
        if result.missing_in_source:
            result.warnings.append(
                "Tables absentes de la source: " + ", ".join(result.missing_in_source)
            )
        if not dry_run:
            _execute(target_conn, "PRAGMA foreign_keys = OFF")
            _execute(target_conn, "BEGIN IMMEDIATE")
        try:
            for table_name in _order_tables_by_dependencies(
                target_conn, common_tables, schema="main"
            ):
                plan = _build_table_plan(target_conn, table_name, schema="main")
                source_columns = _get_table_columns(target_conn, table_name, schema=alias)
                plan.columns = [column for column in plan.columns if column in source_columns]
                plan.pk_columns = [column for column in plan.pk_columns if column in source_columns]
                plan.timestamp_columns = [
                    column for column in plan.timestamp_columns if column in source_columns
                ]
                if not plan.pk_columns:
                    result.tables.append(
                        TableSyncResult(
                            table_name=table_name, skipped=True, reason="Pas de cle primaire."
                        )
                    )
                    continue
                result.tables.append(
                    _sync_table(
                        target_conn=target_conn,
                        alias=alias,
                        plan=plan,
                        conflict_strategy=conflict_strategy,
                        dry_run=dry_run,
                    )
                )
            if not dry_run:
                target_conn.commit()
                _execute(target_conn, "PRAGMA foreign_keys = ON")
                warnings.extend(_collect_foreign_key_warnings(target_conn))
        except Exception:
            if not dry_run:
                target_conn.rollback()
                _execute(target_conn, "PRAGMA foreign_keys = ON")
            raise
    finally:
        _execute(target_conn, f"DETACH DATABASE {alias}")
    return result


def _sync_table(
    *,
    target_conn: sqlite3.Connection,
    alias: str,
    plan: TablePlan,
    conflict_strategy: str,
    dry_run: bool,
) -> TableSyncResult:
    q_table = _quote_identifier(plan.table_name)
    src_rows = _fetch_count(target_conn, f"SELECT COUNT(*) FROM {alias}.{q_table}")
    src_alias, dst_alias = "src", "dst"
    join_sql = _build_join_condition(src_alias, dst_alias, plan.pk_columns)
    insert_count = _fetch_count(
        target_conn,
        f"SELECT COUNT(*) FROM {alias}.{q_table} {src_alias} "
        f"LEFT JOIN main.{q_table} {dst_alias} ON {join_sql} "
        f"WHERE {dst_alias}.{_quote_identifier(plan.pk_columns[0])} IS NULL",
    )
    if not plan.non_pk_columns:
        identical = max(src_rows - insert_count, 0)
        if not dry_run:
            cols = ", ".join(_quote_identifier(column) for column in plan.columns)
            pk_cols = ", ".join(_quote_identifier(column) for column in plan.pk_columns)
            _execute(
                target_conn,
                f"INSERT INTO main.{q_table} ({cols}) SELECT {cols} FROM {alias}.{q_table} WHERE 1=1 "
                f"ON CONFLICT ({pk_cols}) DO NOTHING",
            )
        return TableSyncResult(
            table_name=plan.table_name,
            source_rows=src_rows,
            inserted=insert_count,
            identical=identical,
        )
    diff_sql = _build_difference_condition(src_alias, dst_alias, plan.non_pk_columns)
    conflict_count = _fetch_count(
        target_conn,
        f"SELECT COUNT(*) FROM {alias}.{q_table} {src_alias} "
        f"JOIN main.{q_table} {dst_alias} ON {join_sql} WHERE {diff_sql}",
    )
    update_ok_sql = _build_update_eligibility_condition(
        strategy=conflict_strategy,
        source_prefix=src_alias,
        target_prefix=dst_alias,
        timestamp_columns=plan.timestamp_columns,
    )
    update_count = _fetch_count(
        target_conn,
        f"SELECT COUNT(*) FROM {alias}.{q_table} {src_alias} "
        f"JOIN main.{q_table} {dst_alias} ON {join_sql} "
        f"WHERE {diff_sql} AND ({update_ok_sql})",
    )
    if not dry_run:
        _execute(
            target_conn,
            _build_upsert_sql(alias=alias, plan=plan, conflict_strategy=conflict_strategy),
        )
    return TableSyncResult(
        table_name=plan.table_name,
        source_rows=src_rows,
        inserted=insert_count,
        updated=update_count,
        skipped_conflicts=max(conflict_count - update_count, 0),
        identical=max(src_rows - insert_count - conflict_count, 0),
    )


def _build_upsert_sql(*, alias: str, plan: TablePlan, conflict_strategy: str) -> str:
    q_table = _quote_identifier(plan.table_name)
    cols = ", ".join(_quote_identifier(column) for column in plan.columns)
    pk_cols = ", ".join(_quote_identifier(column) for column in plan.pk_columns)
    updates = ", ".join(
        f"{_quote_identifier(column)} = excluded.{_quote_identifier(column)}"
        for column in plan.non_pk_columns
    )
    diff_sql = _build_difference_condition("excluded", q_table, plan.non_pk_columns)
    update_ok_sql = _build_update_eligibility_condition(
        strategy=conflict_strategy,
        source_prefix="excluded",
        target_prefix=q_table,
        timestamp_columns=plan.timestamp_columns,
    )
    return (
        f"INSERT INTO main.{q_table} ({cols}) SELECT {cols} FROM {alias}.{q_table} WHERE 1=1 "
        f"ON CONFLICT ({pk_cols}) DO UPDATE SET {updates} "
        f"WHERE {diff_sql} AND ({update_ok_sql})"
    )


def _build_table_plan(conn: sqlite3.Connection, table_name: str, *, schema: str) -> TablePlan:
    info = _get_table_info(conn, table_name, schema=schema)
    columns = [row["name"] for row in info]
    pk_columns = [row["name"] for row in sorted(info, key=lambda item: item["pk"]) if row["pk"]]
    timestamps = [column for column in TIMESTAMP_CANDIDATE_COLUMNS if column in columns]
    return TablePlan(
        table_name=table_name, columns=columns, pk_columns=pk_columns, timestamp_columns=timestamps
    )


def _get_table_names(conn: sqlite3.Connection, *, schema: str) -> set[str]:
    rows = _fetch_rows(
        conn,
        f"SELECT name FROM {schema}.sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'",
    )
    return {row[0] for row in rows}


def _get_table_columns(conn: sqlite3.Connection, table_name: str, *, schema: str) -> set[str]:
    return {row["name"] for row in _get_table_info(conn, table_name, schema=schema)}


def _get_table_info(conn: sqlite3.Connection, table_name: str, *, schema: str) -> list[sqlite3.Row]:
    return list(_fetch_rows(conn, f"PRAGMA {schema}.table_info({_quote_literal(table_name)})"))


def _order_tables_by_dependencies(
    conn: sqlite3.Connection, table_names: Iterable[str], *, schema: str
) -> list[str]:
    table_set = set(table_names)
    deps = {table_name: set() for table_name in table_set}
    for table_name in table_set:
        rows = _fetch_rows(conn, f"PRAGMA {schema}.foreign_key_list({_quote_literal(table_name)})")
        deps[table_name] = {
            row["table"] for row in rows if row["table"] in table_set and row["table"] != table_name
        }
    ordered: list[str] = []
    seen: set[str] = set()

    def visit(table_name: str) -> None:
        if table_name in seen:
            return
        seen.add(table_name)
        for dep in sorted(deps[table_name]):
            visit(dep)
        ordered.append(table_name)

    for table_name in sorted(table_set):
        visit(table_name)
    return ordered


def _build_join_condition(source_prefix: str, target_prefix: str, pk_columns: Sequence[str]) -> str:
    return " AND ".join(
        f"{source_prefix}.{_quote_identifier(column)} = {target_prefix}.{_quote_identifier(column)}"
        for column in pk_columns
    )


def _build_difference_condition(
    source_prefix: str, target_prefix: str, columns: Sequence[str]
) -> str:
    if not columns:
        return "0"
    same_values = " AND ".join(
        f"{source_prefix}.{_quote_identifier(column)} IS {target_prefix}.{_quote_identifier(column)}"
        for column in columns
    )
    return f"NOT ({same_values})"


def _build_update_eligibility_condition(
    *,
    strategy: str,
    source_prefix: str,
    target_prefix: str,
    timestamp_columns: Sequence[str],
) -> str:
    if strategy == "source":
        return "1"
    if strategy == "target":
        return "0"
    if not timestamp_columns:
        return "1"
    src_ts = _build_timestamp_expression(source_prefix, timestamp_columns)
    dst_ts = _build_timestamp_expression(target_prefix, timestamp_columns)
    return (
        f"(({src_ts}) IS NOT NULL AND (({dst_ts}) IS NULL OR ({src_ts}) >= ({dst_ts}))) "
        f"OR (({src_ts}) IS NULL AND ({dst_ts}) IS NULL)"
    )


def _build_timestamp_expression(prefix: str, columns: Sequence[str]) -> str:
    expressions = [f"{prefix}.{_quote_identifier(column)}" for column in columns]
    if len(expressions) == 1:
        return expressions[0]
    return "COALESCE(" + ", ".join(expressions) + ")"


def _create_sqlite_backup(target_path: Path, backup_dir: str | Path | None) -> Path:
    directory = _normalize_path(backup_dir) if backup_dir else target_path.parent / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    backup_path = (
        directory / f"{target_path.stem}_backup_{datetime.now():%Y%m%d_%H%M%S}{target_path.suffix}"
    )
    with (
        closing(sqlite3.connect(target_path)) as source_conn,
        closing(sqlite3.connect(backup_path)) as backup_conn,
    ):
        source_conn.backup(backup_conn)
    return backup_path


def _collect_foreign_key_warnings(conn: sqlite3.Connection) -> list[str]:
    rows = _fetch_rows(conn, "PRAGMA foreign_key_check")
    warnings = [
        f"Contrainte FK sur table {row[0]!r}, ligne {row[1]!r}, reference {row[2]!r}."
        for row in rows[:20]
    ]
    if len(rows) > 20:
        warnings.append(f"{len(rows) - 20} autres anomalies FK non affichees.")
    return warnings


def _normalize_source_paths(source_paths: Sequence[str | Path], target: Path) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for item in source_paths:
        path = _normalize_path(item)
        if not path.exists():
            raise FileNotFoundError(f"Base source introuvable: {path}")
        if path == target:
            raise ValueError(f"La base source et la base cible sont identiques: {path}")
        if path not in seen:
            paths.append(path)
            seen.add(path)
    if not paths:
        raise ValueError("Aucune base source n'a ete fournie.")
    return paths


def _normalize_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _fetch_count(conn: sqlite3.Connection, sql: str) -> int:
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        row = cursor.fetchone()
    finally:
        cursor.close()
    return int(row[0])


def _fetch_rows(
    conn: sqlite3.Connection, sql: str, params: Sequence[object] = ()
) -> list[sqlite3.Row]:
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        return list(cursor.fetchall())
    finally:
        cursor.close()


def _execute(conn: sqlite3.Connection, sql: str, params: Sequence[object] = ()) -> None:
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
    finally:
        cursor.close()


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"

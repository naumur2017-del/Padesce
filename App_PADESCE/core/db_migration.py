from __future__ import annotations

from dataclasses import dataclass

from django.apps import apps
from django.core.management.color import no_style
from django.db import connections, transaction
from django.db.models import Model


@dataclass(slots=True)
class ModelCopyResult:
    model_label: str
    table_name: str
    source_count: int
    inserted: int


@dataclass(slots=True)
class CountMismatch:
    model_label: str
    table_name: str
    source_count: int
    target_count: int


@dataclass(slots=True)
class DatabaseCopyResult:
    source_alias: str
    target_alias: str
    model_results: list[ModelCopyResult] = field(default_factory=list)
    skipped_tables: list[str] = field(default_factory=list)
    flush_statements: int = 0
    sequence_statements: int = 0
    count_mismatches: list[CountMismatch] = field(default_factory=list)

    @property
    def inserted(self) -> int:
        return sum(item.inserted for item in self.model_results)


class DatabaseCopyIntegrityError(RuntimeError):
    def __init__(self, result: DatabaseCopyResult) -> None:
        self.result = result
        message = ", ".join(
            f"{item.table_name}: source={item.source_count}, cible={item.target_count}"
            for item in result.count_mismatches
        )
        super().__init__(f"Incoherences detectees apres copie: {message}")


def copy_database_contents(
    *,
    source_alias: str,
    target_alias: str,
    model_labels: list[str] | None = None,
    exclude_tables: list[str] | None = None,
    batch_size: int = 1000,
    flush_target: bool = True,
    verify_counts: bool = True,
) -> DatabaseCopyResult:
    if batch_size <= 0:
        raise ValueError("batch_size doit etre strictement positif.")

    result = DatabaseCopyResult(source_alias=source_alias, target_alias=target_alias)
    models = _get_copy_models(
        source_alias=source_alias,
        target_alias=target_alias,
        model_labels=model_labels or [],
        exclude_tables=exclude_tables or [],
        skipped_tables=result.skipped_tables,
    )
    ordered_models = _order_models_by_dependencies(models)
    table_names = [model._meta.db_table for model in ordered_models]

    with transaction.atomic(using=target_alias):
        if flush_target and table_names:
            result.flush_statements = _flush_target_tables(target_alias, table_names)

        for model in ordered_models:
            result.model_results.append(
                _copy_model_rows(
                    model=model,
                    source_alias=source_alias,
                    target_alias=target_alias,
                    batch_size=batch_size,
                )
            )

        result.sequence_statements = _reset_sequences(target_alias, ordered_models)

        if verify_counts:
            result.count_mismatches = _collect_count_mismatches(
                source_alias=source_alias,
                target_alias=target_alias,
                model_results=result.model_results,
            )
            if result.count_mismatches:
                raise DatabaseCopyIntegrityError(result)

        if table_names:
            connections[target_alias].check_constraints(table_names=table_names)

    return result


def _get_copy_models(
    *,
    source_alias: str,
    target_alias: str,
    model_labels: list[str],
    exclude_tables: list[str],
    skipped_tables: list[str],
) -> list[type[Model]]:
    source_tables = set(connections[source_alias].introspection.table_names())
    target_tables = set(connections[target_alias].introspection.table_names())
    requested_labels = {label.strip().lower() for label in model_labels if label.strip()}
    excluded_tables = {table.strip() for table in exclude_tables if table.strip()}
    selected_models: list[type[Model]] = []

    for model in apps.get_models(include_auto_created=True):
        opts = model._meta
        if not opts.managed or opts.proxy or opts.swapped:
            continue
        if opts.db_table in excluded_tables:
            skipped_tables.append(opts.db_table)
            continue
        if (
            requested_labels
            and opts.label_lower not in requested_labels
            and opts.db_table.lower() not in requested_labels
        ):
            continue
        if opts.db_table not in source_tables or opts.db_table not in target_tables:
            skipped_tables.append(opts.db_table)
            continue
        selected_models.append(model)
    return selected_models


def _order_models_by_dependencies(models: list[type[Model]]) -> list[type[Model]]:
    model_set = set(models)
    dependencies: dict[type[Model], set[type[Model]]] = {}

    for model in models:
        deps: set[type[Model]] = set()
        for field in model._meta.local_fields:
            remote_field = getattr(field, "remote_field", None)
            remote_model = getattr(remote_field, "model", None) if remote_field else None
            if not remote_model or isinstance(remote_model, str):
                continue
            remote_model = remote_model._meta.concrete_model
            if remote_model in model_set and remote_model is not model:
                deps.add(remote_model)
        dependencies[model] = deps

    ordered: list[type[Model]] = []
    visiting: set[type[Model]] = set()
    visited: set[type[Model]] = set()

    def visit(model: type[Model]) -> None:
        if model in visited:
            return
        if model in visiting:
            raise ValueError(f"Dependance circulaire detectee autour de {model._meta.label}.")
        visiting.add(model)
        for dependency in sorted(dependencies[model], key=lambda item: item._meta.db_table):
            visit(dependency)
        visiting.remove(model)
        visited.add(model)
        ordered.append(model)

    for model in sorted(models, key=lambda item: item._meta.db_table):
        visit(model)

    return ordered


def _flush_target_tables(target_alias: str, table_names: list[str]) -> int:
    connection = connections[target_alias]
    sql_list = connection.ops.sql_flush(
        no_style(),
        table_names,
        reset_sequences=False,
        allow_cascade=True,
    )
    if not sql_list:
        return 0
    with connection.cursor() as cursor:
        for sql in sql_list:
            cursor.execute(sql)
    return len(sql_list)


def _copy_model_rows(
    *,
    model: type[Model],
    source_alias: str,
    target_alias: str,
    batch_size: int,
) -> ModelCopyResult:
    manager = model._base_manager
    queryset = manager.using(source_alias).all()
    pk_field = model._meta.pk
    if pk_field is not None:
        queryset = queryset.order_by(pk_field.attname)
    else:
        queryset = queryset.order_by()

    source_count = queryset.count()
    concrete_fields = list(model._meta.concrete_fields)
    inserted = 0
    batch: list[Model] = []

    for source_object in queryset.iterator(chunk_size=batch_size):
        target_object = model()
        for field in concrete_fields:
            setattr(target_object, field.attname, getattr(source_object, field.attname))
        batch.append(target_object)
        if len(batch) >= batch_size:
            manager.using(target_alias).bulk_create(batch, batch_size=batch_size)
            inserted += len(batch)
            batch.clear()

    if batch:
        manager.using(target_alias).bulk_create(batch, batch_size=batch_size)
        inserted += len(batch)

    return ModelCopyResult(
        model_label=model._meta.label,
        table_name=model._meta.db_table,
        source_count=source_count,
        inserted=inserted,
    )


def _reset_sequences(target_alias: str, models: list[type[Model]]) -> int:
    connection = connections[target_alias]
    sql_list = connection.ops.sequence_reset_sql(no_style(), models)
    if not sql_list:
        return 0
    with connection.cursor() as cursor:
        for sql in sql_list:
            cursor.execute(sql)
    return len(sql_list)


def _collect_count_mismatches(
    *,
    source_alias: str,
    target_alias: str,
    model_results: list[ModelCopyResult],
) -> list[CountMismatch]:
    mismatches: list[CountMismatch] = []

    for item in model_results:
        model = apps.get_model(item.model_label)
        target_count = model._base_manager.using(target_alias).count()
        if item.source_count != target_count:
            mismatches.append(
                CountMismatch(
                    model_label=item.model_label,
                    table_name=item.table_name,
                    source_count=item.source_count,
                    target_count=target_count,
                )
            )

    return mismatches

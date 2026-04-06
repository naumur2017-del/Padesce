import json
import os
import time
import traceback
from pathlib import Path

AUTO_MIGRATE_LOCK_FILENAME = ".django-auto-migrate.lock"
AUTO_MIGRATE_DONE_FILENAME = ".django-auto-migrate.done"
AUTO_MIGRATE_ERROR_FILENAME = ".django-auto-migrate.error"
AUTO_MIGRATE_WAIT_SECONDS = 90
AUTO_MIGRATE_STALE_SECONDS = 15 * 60


def load_runtime_env(base_dir: Path) -> None:
    runtime_env = base_dir / ".runtime.env"
    if not runtime_env.exists():
        return

    for line in runtime_env.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().lstrip("\ufeff")
        value = value.strip()
        if not key or any(char.isspace() for char in key):
            continue
        os.environ.setdefault(key, value)


def _write_runtime_env(base_dir: Path, updates: dict[str, str]) -> None:
    runtime_env = base_dir / ".runtime.env"
    lines = runtime_env.read_text(encoding="utf-8-sig").splitlines() if runtime_env.exists() else []
    seen_keys: set[str] = set()
    output_lines: list[str] = []

    for original_line in lines:
        stripped = original_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in original_line:
            output_lines.append(original_line)
            continue
        key, _value = original_line.split("=", 1)
        key = key.strip().lstrip("\ufeff")
        if key in updates:
            output_lines.append(f"{key}={updates[key]}")
            seen_keys.add(key)
        else:
            output_lines.append(original_line)

    for key, value in updates.items():
        if key not in seen_keys:
            output_lines.append(f"{key}={value}")

    runtime_env.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")


def _ensure_utf8_postgres_database(base_dir: Path, config: dict) -> None:
    postgres = config.get("postgres") or {}
    database = str(postgres.get("database") or os.environ.get("POSTGRES_DB") or "postgres")
    user = str(postgres.get("user") or os.environ.get("POSTGRES_USER") or "hosting-db")
    password = str(postgres.get("password") or os.environ.get("POSTGRES_PASSWORD") or "")
    host = str(postgres.get("host") or os.environ.get("POSTGRES_HOST") or "localhost")
    port = int(postgres.get("port") or os.environ.get("POSTGRES_PORT") or 5432)

    try:
        import psycopg2
        from psycopg2 import sql
    except ImportError:
        return

    connection = psycopg2.connect(
        dbname=database,
        user=user,
        password=password,
        host=host,
        port=port,
    )
    connection.autocommit = True

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT datname, pg_encoding_to_char(encoding) FROM pg_database")
            database_encodings = {name: encoding.upper() for name, encoding in cursor.fetchall()}

            current_encoding = database_encodings.get(database, "")
            if current_encoding == "UTF8":
                return

            candidates = []
            for raw_name in (
                f"{database}_utf8",
                "call_naumur_utf8",
                "padesce_utf8",
                f"{user.replace('-', '_')[:40]}_utf8",
            ):
                candidate = raw_name[:63]
                if candidate and candidate not in candidates:
                    candidates.append(candidate)

            chosen_database = None
            for candidate in candidates:
                if database_encodings.get(candidate) == "UTF8":
                    chosen_database = candidate
                    break

            if chosen_database is None:
                last_error = None
                for candidate in candidates:
                    if candidate in database_encodings:
                        continue
                    try:
                        cursor.execute(
                            sql.SQL("CREATE DATABASE {} WITH ENCODING 'UTF8' TEMPLATE template0").format(
                                sql.Identifier(candidate)
                            )
                        )
                    except Exception as exc:  # pragma: no cover - remote-runtime fallback
                        last_error = exc
                        continue
                    chosen_database = candidate
                    break
                if chosen_database is None and last_error is not None:
                    raise last_error

            if not chosen_database:
                return

            postgres["database"] = chosen_database
            config["postgres"] = postgres
            os.environ["POSTGRES_DB"] = chosen_database
            _write_runtime_env(base_dir, {"POSTGRES_DB": chosen_database})
            (base_dir / ".postgres_migration.json").write_text(
                json.dumps(config, indent=2),
                encoding="utf-8",
            )
    finally:
        connection.close()


def maybe_run_postgres_migration(base_dir: Path) -> None:
    control_file = base_dir / ".postgres_migration.json"
    done_file = base_dir / ".postgres_migration.done"
    error_file = base_dir / ".postgres_migration.error"

    if not control_file.exists():
        return

    config = json.loads(control_file.read_text(encoding="utf-8-sig"))
    postgres = config.get("postgres") or {}
    sqlite_source = Path(config.get("sqlite_source") or (base_dir / "db.sqlite3"))
    if not sqlite_source.is_absolute():
        sqlite_source = (base_dir / sqlite_source).resolve(strict=False)

    if done_file.exists():
        try:
            if not sqlite_source.exists() or done_file.stat().st_mtime >= sqlite_source.stat().st_mtime:
                return
        except OSError:
            return

    os.environ["DB_ENGINE"] = "postgresql"
    os.environ["POSTGRES_DB"] = str(postgres.get("database") or "postgres")
    os.environ["POSTGRES_USER"] = str(postgres.get("user") or "postgres")
    os.environ["POSTGRES_PASSWORD"] = str(postgres.get("password") or "")
    os.environ["POSTGRES_HOST"] = str(postgres.get("host") or "localhost")
    os.environ["POSTGRES_PORT"] = str(postgres.get("port") or "5432")

    sslmode = str(postgres.get("sslmode") or "").strip()
    if sslmode:
        os.environ["POSTGRES_SSLMODE"] = sslmode
    else:
        os.environ.pop("POSTGRES_SSLMODE", None)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "App_PADESCE.settings")

    _ensure_utf8_postgres_database(base_dir, config)

    try:
        import django
        from django.core.management import call_command

        django.setup()
        call_command(
            "migrate_sqlite_to_postgres",
            source=str(sqlite_source),
            target="default",
            verbosity=1,
        )
    except Exception:
        error_file.write_text(traceback.format_exc(), encoding="utf-8")
        raise

    done_file.write_text(
        json.dumps(
            {
                "sqlite_source": str(sqlite_source),
                "database": os.environ["POSTGRES_DB"],
                "user": os.environ["POSTGRES_USER"],
                "host": os.environ["POSTGRES_HOST"],
                "port": os.environ["POSTGRES_PORT"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    error_file.unlink(missing_ok=True)


def _auto_migrate_enabled() -> bool:
    raw_value = str(os.environ.get("NAUMUR_AUTO_MIGRATE_ON_BOOT", "1") or "").strip().lower()
    return raw_value not in {"0", "false", "no", "off"}


def _runtime_marker_dir(base_dir: Path) -> Path:
    path = base_dir / "logs" / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _acquire_bootstrap_lock(lock_path: Path) -> bool:
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                age_seconds = time.time() - lock_path.stat().st_mtime
            except OSError:
                age_seconds = 0
            if age_seconds > AUTO_MIGRATE_STALE_SECONDS:
                lock_path.unlink(missing_ok=True)
                continue
            return False
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"pid": os.getpid(), "created_at": time.time()}))
            return True


def _wait_for_bootstrap_lock(lock_path: Path, timeout_seconds: int = AUTO_MIGRATE_WAIT_SECONDS) -> None:
    deadline = time.monotonic() + max(0, timeout_seconds)
    while lock_path.exists() and time.monotonic() < deadline:
        time.sleep(1)


def _has_pending_django_migrations() -> bool:
    import django
    from django.db import DEFAULT_DB_ALIAS, connections
    from django.db.migrations.executor import MigrationExecutor

    django.setup()
    connection = connections[DEFAULT_DB_ALIAS]
    executor = MigrationExecutor(connection)
    targets = executor.loader.graph.leaf_nodes()
    return bool(executor.migration_plan(targets))


def maybe_run_django_migrations(base_dir: Path) -> bool:
    if not _auto_migrate_enabled():
        return False

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "App_PADESCE.settings")

    marker_dir = _runtime_marker_dir(base_dir)
    lock_path = marker_dir / AUTO_MIGRATE_LOCK_FILENAME
    done_path = marker_dir / AUTO_MIGRATE_DONE_FILENAME
    error_path = marker_dir / AUTO_MIGRATE_ERROR_FILENAME

    if not _acquire_bootstrap_lock(lock_path):
        _wait_for_bootstrap_lock(lock_path)
        return False

    try:
        if not _has_pending_django_migrations():
            done_path.write_text(
                json.dumps({"pid": os.getpid(), "status": "up_to_date", "checked_at": time.time()}, indent=2),
                encoding="utf-8",
            )
            error_path.unlink(missing_ok=True)
            return False

        from django.core.management import call_command

        call_command("migrate", interactive=False, verbosity=0)
        done_path.write_text(
            json.dumps({"pid": os.getpid(), "status": "migrated", "completed_at": time.time()}, indent=2),
            encoding="utf-8",
        )
        error_path.unlink(missing_ok=True)
        return True
    except Exception:
        error_path.write_text(traceback.format_exc(), encoding="utf-8")
        return False
    finally:
        lock_path.unlink(missing_ok=True)


def bootstrap_runtime(base_dir: Path) -> None:
    load_runtime_env(base_dir)
    maybe_run_postgres_migration(base_dir)
    maybe_run_django_migrations(base_dir)

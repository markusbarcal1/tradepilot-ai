"""Explicit, offline SQLite -> PostgreSQL copy. Never called by application startup."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.config import Config
from sqlalchemy import Float, Integer, JSON, REAL, create_engine, inspect, select, text
from sqlalchemy.engine import make_url

from app.bootstrap import DEFAULT_DEV_USER_ID
from app.db import Base, resolve_database_url
from app import models  # noqa: F401


BACKEND = Path(__file__).resolve().parents[2]
TABLES = tuple(Base.metadata.sorted_tables)


class MigrationBlocked(Exception):
    """Safe operator-facing failure, without connection strings or row contents."""


def head_revision():
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    return ScriptDirectory.from_config(config).get_current_head()


def source_path(value):
    url = resolve_database_url(value) if "://" in value else make_url(
        "sqlite://").set(database=str(Path(value).resolve()))
    if url.get_backend_name() != "sqlite" or url.query or not url.database:
        raise MigrationBlocked("Source must be an existing SQLite file, without URL options.")
    path = Path(url.database).resolve()
    if not path.is_file():
        raise MigrationBlocked("Source SQLite file does not exist.")
    return path


@contextmanager
def readonly_source(path):
    # mode=ro prevents accidental file creation/writes, including during inspection.
    engine = create_engine("sqlite://", creator=lambda: sqlite3.connect(
        path.as_uri() + "?mode=ro", uri=True))
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA query_only=ON")
            connection.exec_driver_sql("BEGIN")
            yield connection
            connection.rollback()
    finally:
        engine.dispose()


def target_engine(value):
    if not value:
        raise MigrationBlocked("Provide --target-url or MIGRATION_TARGET_DATABASE_URL explicitly.")
    url = make_url(value)
    if url.drivername != "postgresql+psycopg" or not url.database:
        raise MigrationBlocked("Target must use postgresql+psycopg and an explicit database.")
    return create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 10})


def identity(engine):
    url = engine.url
    # Do not render URL query parameters: these can also contain credentials.
    return {"host": url.host, "port": url.port or 5432,
            "database": url.database, "user": url.username}


def revision(connection):
    if not inspect(connection).has_table("alembic_version"):
        return None
    rows = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
    return rows[0] if len(rows) == 1 else None


def schema_blockers(connection, label):
    blockers = []
    expected = {table.name for table in TABLES} | {"alembic_version"}
    if set(inspect(connection).get_table_names()) != expected:
        return [f"{label}: unexpected or missing tables."]

    def compare_types(context, _a, _b, actual, desired):
        if context.dialect.name == "sqlite" and isinstance(actual, REAL) and type(desired) is Float:
            return False
        return None

    context = MigrationContext.configure(connection, opts={"compare_type": compare_types})
    differences = compare_metadata(context, Base.metadata)
    # SQLite reflects INTEGER PRIMARY KEY as nullable. Ignore only that artifact.
    for difference in differences:
        group = difference if isinstance(difference, list) else [difference]
        for item in group:
            if (connection.dialect.name == "sqlite" and item[0] == "modify_nullable"
                    and item[2] in Base.metadata.tables
                    and Base.metadata.tables[item[2]].c[item[3]].primary_key
                    and item[-2:] == (True, False)):
                continue
            blockers.append(f"{label}: schema drift ({item[0]}).")
    if connection.dialect.name == "postgresql":
        if connection.scalar(text("SHOW session_replication_role")) != "origin":
            blockers.append(f"{label}: session must enforce normal constraints/triggers.")
        # RLS can hide pre-existing rows from COUNT/SELECT, violating empty-target safety.
        if connection.scalar(text(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relrowsecurity"
        )):
            blockers.append(f"{label}: row-level security must be disabled for this offline copy.")
        if connection.scalar(text(
            "SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace "
            "WHERE n.nspname='public' AND NOT c.convalidated"
        )):
            blockers.append(f"{label}: unvalidated constraints.")
        if connection.scalar(text(
            "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' "
            "AND (NOT t.tgisinternal OR t.tgenabled <> 'O')"
        )):
            blockers.append(f"{label}: custom or disabled triggers are unsupported.")
    return blockers


def snapshot(connection):
    return {table.name: [dict(row) for row in connection.execute(
        select(table).order_by(*table.primary_key.columns)).mappings()] for table in TABLES}


def integrity_blockers(data):
    blockers = []
    users = {row["user_id"] for row in data["app_users"]}
    accounts = {row["id"] for row in data["paper_accounts"]}
    if DEFAULT_DEV_USER_ID in users:
        blockers.append("Unexpected bootstrap user: complete reviewed legacy adoption first.")
    for table in TABLES:
        seen = set()
        for row in data[table.name]:
            key = tuple(row[column.name] for column in table.primary_key.columns)
            if key in seen:
                blockers.append(f"{table.name}: duplicate primary key.")
            seen.add(key)
            for column in table.columns:
                value = row[column.name]
                if value is None and not column.nullable:
                    blockers.append(f"{table.name}: null in required field.")
                if isinstance(column.type, Float) and (value is None or not math.isfinite(value)):
                    blockers.append(f"{table.name}: invalid financial value.")
                if isinstance(column.type, Integer) and (not isinstance(value, int)
                        or not -(2**31) <= value < 2**31 - 1):
                    blockers.append(f"{table.name}: ID exceeds PostgreSQL INTEGER range or leaves no sequence capacity.")
                if isinstance(column.type, JSON):
                    try:
                        json.dumps(value, allow_nan=False)
                    except (TypeError, ValueError):
                        blockers.append(f"{table.name}: invalid JSON value.")
            if table.name != "app_users" and "user_id" in row and row["user_id"] not in users:
                blockers.append(f"{table.name}: orphan user reference.")
            if "account_id" in row and row["account_id"] not in accounts:
                blockers.append(f"{table.name}: orphan account reference.")
    owners = [row["user_id"] for row in data["paper_accounts"]]
    if len(owners) != len(set(owners)):
        blockers.append("More than one paper account per user.")
    positions = [(row["account_id"], row["symbol"]) for row in data["paper_positions"]]
    if len(positions) != len(set(positions)):
        blockers.append("Duplicate position symbol within an account.")
    if any(not isinstance(row["scanner_preferences"], dict) for row in data["user_preferences"]):
        blockers.append("Scanner preferences must be JSON objects.")
    return sorted(set(blockers))


def summarize(data):
    result = {"counts": {name: len(rows) for name, rows in data.items()}, "per_user": []}
    for user in data["app_users"]:
        uid = user["user_id"]
        accounts = [row for row in data["paper_accounts"] if row["user_id"] == uid]
        account_ids = {row["id"] for row in accounts}
        positions = [row for row in data["paper_positions"] if row["account_id"] in account_ids]
        trades = [row["id"] for row in data["paper_trades"] if row["account_id"] in account_ids]
        watchlist = sorted(row["symbol"] for row in data["watchlist_items"] if row["user_id"] == uid)
        preference = next((row for row in data["user_preferences"] if row["user_id"] == uid), None)
        account = accounts[0] if len(accounts) == 1 else {}
        result["per_user"].append({
            "user_uuid": str(uid), "account_count": len(accounts),
            "account_id": account.get("id"), "cash_balance": account.get("cash_balance"),
            "starting_cash": account.get("starting_cash"), "position_count": len(positions),
            "position_symbols": sorted(row["symbol"] for row in positions),
            "trade_count": len(trades), "trade_id_range": [min(trades), max(trades)] if trades else None,
            "watchlist_count": len(watchlist), "watchlist_symbols": watchlist,
            "theme": preference["theme"] if preference else None,
            "scanner_preferences_present": preference is not None,
        })
    return result


def verify_data(source, target):
    """Compare every column, preserving timestamps/JSON/UUIDs and tolerating float roundoff."""
    blockers = integrity_blockers(target)
    for table in TABLES:
        before, after = source[table.name], target[table.name]
        if len(before) != len(after):
            blockers.append(f"{table.name}: count mismatch.")
            continue
        for left, right in zip(before, after):
            for column in table.columns:
                a, b = left[column.name], right[column.name]
                equal = (math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-8)
                         if isinstance(column.type, Float) and a is not None and b is not None
                         else a == b)
                if not equal:
                    blockers.append(f"{table.name}.{column.name}: value mismatch.")
    if blockers:
        raise MigrationBlocked("Verification failed: " + " ".join(sorted(set(blockers))))


def backup_source(connection, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    with tempfile.NamedTemporaryFile(prefix=f"sqlite-to-postgres-{stamp}-", suffix=".db",
                                     dir=directory, delete=False) as handle:
        path = Path(handle.name)
    destination = sqlite3.connect(path)
    try:
        connection.connection.driver_connection.backup(destination)
    finally:
        destination.close()
    return path


def sequence_details(connection):
    result = {}
    for name in ("paper_accounts", "paper_positions", "paper_trades"):
        sequence = connection.scalar(text("SELECT pg_get_serial_sequence(:table, 'id')"),
                                     {"table": f"public.{name}"})
        if sequence is None:
            raise MigrationBlocked(f"{name}: missing ID sequence.")
        # Resolve identifiers through the catalog and quote separately, never a URL/input.
        schema, seqname = connection.execute(text(
            "SELECT n.nspname, c.relname FROM pg_class c JOIN pg_namespace n "
            "ON n.oid = c.relnamespace WHERE c.oid = CAST(:sequence AS regclass)"
        ), {"sequence": sequence}).one()
        quote = connection.dialect.identifier_preparer.quote
        next_id = max(1, (connection.scalar(select(
            Base.metadata.tables[name].c.id).order_by(
            Base.metadata.tables[name].c.id.desc()).limit(1)) or 0) + 1)
        result[name] = (f"{quote(schema)}.{quote(seqname)}", next_id)
    return result


def synchronize_sequences(connection):
    result = {}
    for name, (sequence, next_id) in sequence_details(connection).items():
        # RESTART is transactional; setval is not. A failed copy restores sequence state too.
        connection.exec_driver_sql(f"ALTER SEQUENCE {sequence} RESTART WITH {next_id}")
        result[name] = next_id
    return result


def verify_sequences(connection):
    result = {}
    for name, (sequence, minimum) in sequence_details(connection).items():
        last, called = connection.exec_driver_sql(f"SELECT last_value, is_called FROM {sequence}").one()
        if last + int(called) < minimum:
            raise MigrationBlocked(f"{name}: sequence is behind migrated IDs.")
        result[name] = {"last_value": last, "is_called": called,
                        "next_id": last + int(called), "minimum_next_id": minimum}
    return result


def run_migration(source, target, *, mode="dry-run", backup_dir=None):
    if mode not in {"dry-run", "confirm", "verify-only"}:
        raise MigrationBlocked("Unknown migration mode.")
    report = {"source_type": "sqlite", "target_type": "postgresql",
              "dry_run": mode == "dry-run", "mode": mode, "source_revision": None,
              "target_revision": None, "target_empty": False, "migration_possible": False,
              "committed": False, "blockers": []}
    for label in ("users", "accounts", "positions", "trades", "watchlist", "preferences"):
        report[f"source_{label}"] = None
    engine = None
    commit_attempted = False
    try:
        path = source_path(source)
        engine = target_engine(target)
        report["target_identity"] = identity(engine)
        with readonly_source(path) as src, engine.connect() as dst:
            with dst.begin():
                if mode != "confirm":
                    dst.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                dst.exec_driver_sql("SET LOCAL search_path TO public, pg_catalog")
                dst.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
                if mode == "confirm":
                    # Hold all application tables against concurrent writers until commit.
                    names = ", ".join(f'public."{table.name}"' for table in TABLES)
                    dst.exec_driver_sql(f"LOCK TABLE {names}, public.alembic_version IN EXCLUSIVE MODE")
                report["source_revision"] = revision(src)
                report["target_revision"] = revision(dst)
                for label in ("source", "target"):
                    if report[f"{label}_revision"] != head_revision():
                        report["blockers"].append(f"{label}: must already be at Alembic head.")
                report["blockers"] += schema_blockers(src, "source")
                report["blockers"] += schema_blockers(dst, "target")
                if src.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
                    report["blockers"].append("source: SQLite foreign key integrity failure.")
                if src.exec_driver_sql("PRAGMA integrity_check").scalars().all() != ["ok"]:
                    report["blockers"].append("source: SQLite integrity failure.")
                if report["blockers"]:
                    return report
                # Ensure all three owned sequences are discoverable during preflight.
                sequence_details(dst)
                before, existing = snapshot(src), snapshot(dst)
                for label, name in (("users", "app_users"), ("accounts", "paper_accounts"),
                                    ("positions", "paper_positions"), ("trades", "paper_trades"),
                                    ("watchlist", "watchlist_items"), ("preferences", "user_preferences")):
                    report[f"source_{label}"] = len(before[name])
                report["target_empty"] = not any(existing.values())
                report["blockers"] += integrity_blockers(before)
                report["blockers"] += integrity_blockers(existing)
                if not report["blockers"]:
                    report["source"] = summarize(before)
                    report["target"] = summarize(existing)
                    report["integrity"] = {
                        "orphan_rows": 0, "account_uniqueness": "passed",
                        "position_uniqueness": "passed", "foreign_key_violations": 0,
                        "bootstrap_present": False,
                    }
                if mode != "verify-only" and not report["target_empty"]:
                    report["blockers"].append("Target application tables must be empty; merging is forbidden.")
                if report["blockers"]:
                    return report
                if mode == "verify-only":
                    verify_data(before, existing)
                    report["sequences"] = verify_sequences(dst)
                    report["verified"] = True
                    return report
                report["migration_possible"] = True
                if mode == "dry-run":
                    return report
                backup = backup_source(src, backup_dir or BACKEND / "backups")
                report["backup"] = str(backup)
                with readonly_source(backup) as copied:
                    verify_data(before, snapshot(copied))
                for table in TABLES:
                    if before[table.name]:
                        dst.execute(table.insert(), before[table.name])
                report["sequence_next_ids"] = synchronize_sequences(dst)
                report["sequences"] = verify_sequences(dst)
                after = snapshot(dst)
                verify_data(before, after)
                report["verified"] = True
                report["target"] = summarize(after)
                commit_attempted = True
            report["committed"] = True
    except MigrationBlocked as exc:
        report["blockers"].append(str(exc))
        report["migration_possible"] = False
    except Exception as exc:
        # SQLAlchemy errors may include URLs, passwords, SQL values, or emails.
        report["blockers"].append(f"Operation failed ({type(exc).__name__}); check connectivity, schema, and privileges. Verify target state before retrying.")
        report["migration_possible"] = False
        if commit_attempted and not report["committed"]:
            report["commit_outcome_unknown"] = True
    finally:
        if engine is not None:
            engine.dispose()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Existing SQLite file path or URL")
    parser.add_argument("--target-url", default=os.environ.get("MIGRATION_TARGET_DATABASE_URL"),
                        help="Prefer MIGRATION_TARGET_DATABASE_URL to avoid shell-history secrets")
    parser.add_argument("--backup-dir", type=Path)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--confirm", action="store_true")
    modes.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    mode = "confirm" if args.confirm else "verify-only" if args.verify_only else "dry-run"
    report = run_migration(args.source, args.target_url, mode=mode, backup_dir=args.backup_dir)
    print(json.dumps(report, indent=2, default=str, allow_nan=False))
    return 1 if report["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

import argparse
import hashlib
import re
import shutil
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker

from app.bootstrap import DEFAULT_DEV_USER_ID
from app.config import REPOSITORY_ROOT, settings
from app.db import create_database_engine, resolve_database_url, session_scope
from app.models.paper_trading import PaperAccount
from app.paper_trading import STARTING_CASH
from app.repositories.paper_trading import PaperTradingRepository
from app.models.user import AppUser
from app.repositories.users import UserRepository


BASELINE_REVISION = "20260828_01"
HEAD_REVISION = "20260902_03"
LEGACY_TABLES = {"paper_account", "paper_positions", "paper_trades"}
CURRENT_TABLES = {
    "app_users", "paper_accounts", "paper_positions", "paper_trades",
    "watchlist_items", "user_preferences", "alembic_version",
}
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class ProvisioningError(RuntimeError):
    def __init__(self, message: str, report: dict | None = None):
        super().__init__(message)
        self.report = report


@dataclass(frozen=True)
class DatabaseState:
    name: str
    revision: str | None
    tables: frozenset[str]


def sqlite_path(database_url: str) -> Path:
    url = resolve_database_url(database_url)
    if url.drivername != "sqlite" or not url.database or url.database == ":memory:":
        raise ProvisioningError("This Phase 6 operator command requires a file-backed SQLite database.")
    return Path(url.database)


def detect_database_state(database_path: Path) -> DatabaseState:
    if not database_path.is_file():
        raise ProvisioningError(f"Database does not exist: {database_path}")
    with closing(sqlite3.connect(database_path)) as connection:
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        revision = None
        if "alembic_version" in tables:
            row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
            revision = row[0] if row else None

    if tables == LEGACY_TABLES:
        return DatabaseState("legacy-unstamped", None, frozenset(tables))
    if tables == LEGACY_TABLES | {"alembic_version"} and revision == BASELINE_REVISION:
        return DatabaseState("baseline-stamped", revision, frozenset(tables))
    if tables == CURRENT_TABLES and revision == HEAD_REVISION:
        return DatabaseState("current", revision, frozenset(tables))
    return DatabaseState("unexpected", revision, frozenset(tables))


def snapshot_portfolio(database_path: Path, state: DatabaseState) -> dict:
    account_table = "paper_account" if state.name in {"legacy-unstamped", "baseline-stamped"} else "paper_accounts"
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        account_columns = "id, cash_balance, starting_cash, created_at, updated_at"
        accounts = [dict(row) for row in connection.execute(f"SELECT {account_columns} FROM {account_table} ORDER BY id")]
        positions = [dict(row) for row in connection.execute(
            "SELECT id, symbol, shares, avg_cost, created_at, updated_at FROM paper_positions ORDER BY id"
        )]
        trades = [dict(row) for row in connection.execute(
            "SELECT id, symbol, side, shares, price, total_value, realized_pnl, created_at FROM paper_trades ORDER BY id"
        )]
    return {"accounts": accounts, "positions": positions, "trades": trades}


def database_sha256(database_path: Path) -> str:
    digest = hashlib.sha256()
    with database_path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def create_backup(database_path: Path, backup_directory: Path | None = None) -> Path:
    directory = backup_directory or REPOSITORY_ROOT / "backend" / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    backup = directory / f"{database_path.stem}.pre_beta_{timestamp}{database_path.suffix}"
    with closing(sqlite3.connect(database_path)) as source, closing(sqlite3.connect(backup)) as target:
        source.backup(target)
    return backup


def alembic_config(database_path: Path) -> Config:
    config = Config(str(REPOSITORY_ROOT / "backend" / "alembic.ini"))
    config.attributes["database_url"] = f"sqlite:///{database_path.as_posix()}"
    return config


def migrate_to_head(database_path: Path, state: DatabaseState) -> DatabaseState:
    config = alembic_config(database_path)
    if state.name == "legacy-unstamped":
        command.stamp(config, BASELINE_REVISION)
    elif state.name not in {"baseline-stamped", "current"}:
        raise ProvisioningError("Refusing to migrate an unexpected or mixed schema.")
    if state.name != "current":
        command.upgrade(config, "head")
    migrated = detect_database_state(database_path)
    if migrated.name != "current":
        raise ProvisioningError("Database did not reach the expected current schema.")
    return migrated


def _normalize_identity(user_id: str, email: str) -> tuple[UUID, str]:
    try:
        parsed_id = UUID(user_id)
    except (ValueError, TypeError) as exc:
        raise ProvisioningError("--user-id must be a valid UUID.") from exc
    normalized_email = email.strip().lower()
    if not EMAIL_PATTERN.fullmatch(normalized_email):
        raise ProvisioningError("--email must be a valid email address.")
    return parsed_id, normalized_email


def _account_details(session, accounts: list[PaperAccount]) -> list[dict]:
    details = []
    for account in accounts:
        positions = session.execute(
            text("SELECT id, symbol FROM paper_positions WHERE account_id=:id ORDER BY id"),
            {"id": account.id},
        ).all()
        trade_ids = session.execute(
            text("SELECT id FROM paper_trades WHERE account_id=:id ORDER BY id"),
            {"id": account.id},
        ).scalars().all()
        details.append({
            "account_id": account.id,
            "owner_user_id": str(account.user_id),
            "cash_balance": account.cash_balance,
            "starting_cash": account.starting_cash,
            "position_count": len(positions),
            "position_ids": [row.id for row in positions],
            "position_symbols": [row.symbol for row in positions],
            "trade_count": len(trade_ids),
            "trade_id_range": [trade_ids[0], trade_ids[-1]] if trade_ids else None,
        })
    return details


def inspect_current(database_path: Path, target_id: UUID) -> dict:
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with session_scope(factory) as session:
            target = session.get(AppUser, target_id)
            bootstrap = session.get(AppUser, DEFAULT_DEV_USER_ID)
            bootstrap_accounts = list(session.scalars(select(PaperAccount).where(PaperAccount.user_id == DEFAULT_DEV_USER_ID)))
            target_accounts = list(session.scalars(select(PaperAccount).where(PaperAccount.user_id == target_id)))
            bootstrap_details = _account_details(session, bootstrap_accounts)
            target_details = _account_details(session, target_accounts)
            reported_accounts = target_details or bootstrap_details
            return {
                "target_exists": target is not None,
                "bootstrap_exists": bootstrap is not None,
                "bootstrap_account_count": len(bootstrap_accounts),
                "target_account_count": len(target_accounts),
                "bootstrap_accounts": bootstrap_details,
                "target_accounts": target_details,
                "reported_owner": "target" if target_details else "bootstrap" if bootstrap_details else None,
                "reported_accounts": reported_accounts,
                "positions": sum(item["position_count"] for item in reported_accounts),
                "trades": sum(item["trade_count"] for item in reported_accounts),
            }
    finally:
        engine.dispose()


def _validate_identity(session, user_id, email, display_name):
    users = UserRepository(session)
    target = users.get(user_id)
    email_owner = session.scalar(select(AppUser).where(AppUser.email == email))
    if email_owner is not None and email_owner.user_id != user_id:
        raise ProvisioningError("Email is already assigned to a different UUID; identity was not reassigned.")
    if target is not None:
        if target.email != email or (display_name is not None and target.display_name != display_name):
            raise ProvisioningError("UUID already exists with conflicting identity data.")
        if target.beta_status != "active":
            raise ProvisioningError("UUID exists but is not active; status was not silently changed.")
    return users, target, email_owner


def _provision_normal(session, user_id, email, display_name):
    users, target, email_owner = _validate_identity(session, user_id, email, display_name)
    if target is None:
        users.create(user_id, email=email, display_name=display_name, beta_status="active")
    accounts = list(session.scalars(select(PaperAccount).where(PaperAccount.user_id == user_id)))
    if len(accounts) > 1:
        raise ProvisioningError("Target UUID owns multiple paper accounts; provisioning did not modify them.")
    account_created = False
    if not accounts:
        accounts = [PaperTradingRepository(session).create_account(user_id, STARTING_CASH)]
        account_created = True
    return {
        "result": "already provisioned" if email_owner is not None and not account_created else "provisioned",
        "app_user_created": email_owner is None,
        "account_created": account_created,
        "account_id": accounts[0].id,
        "ownership_reassigned": False,
        "bootstrap_removed": False,
    }


def provision_current_database(database_path: Path, user_id: UUID, email: str, display_name: str | None, adopt_legacy: bool) -> dict:
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with session_scope(factory) as session:
            if not adopt_legacy:
                return _provision_normal(session, user_id, email, display_name)
            users, target, email_owner = _validate_identity(session, user_id, email, display_name)
            if target is None:
                target = users.create(user_id, email=email, display_name=display_name, beta_status="active")

            bootstrap_accounts = list(session.scalars(select(PaperAccount).where(PaperAccount.user_id == DEFAULT_DEV_USER_ID)))
            target_accounts = list(session.scalars(select(PaperAccount).where(PaperAccount.user_id == user_id)))
            bootstrap = users.get(DEFAULT_DEV_USER_ID)
            bootstrap_account_count = session.execute(
                text("SELECT COUNT(*) FROM paper_accounts WHERE lower(replace(user_id, '-', '')) = :user_id"),
                {"user_id": DEFAULT_DEV_USER_ID.hex},
            ).scalar_one()
            if not bootstrap_accounts and bootstrap is None and len(target_accounts) == 1:
                return {
                    "result": f"already provisioned and owns legacy account {target_accounts[0].id}; nothing to do",
                    "app_user_created": False,
                    "account_created": False,
                    "account_id": target_accounts[0].id,
                    "ownership_reassigned": False,
                    "bootstrap_removed": False,
                }
            if bootstrap_account_count != 1:
                raise ProvisioningError(f"Legacy adoption requires exactly one bootstrap account; found {bootstrap_account_count}.")
            if target_accounts:
                raise ProvisioningError("Target UUID already owns a paper account; portfolios were not merged.")
            account = bootstrap_accounts[0]
            account.user_id = user_id
            session.flush()
            if bootstrap is not None:
                session.delete(bootstrap)
            session.flush()
            violations = session.execute(text("PRAGMA foreign_key_check")).all()
            if violations:
                raise ProvisioningError(f"Foreign-key violations detected: {violations}")
            return {
                "result": f"provisioned and adopted legacy account {account.id}",
                "app_user_created": email_owner is None,
                "account_created": False,
                "account_id": account.id,
                "ownership_reassigned": True,
                "bootstrap_removed": bootstrap is not None,
            }
    finally:
        engine.dispose()


def cleanup_bootstrap(args) -> dict:
    """Explicit cleanup, with validation and deletion under one SQLite write lock."""
    if args.user_id or args.email or args.display_name or args.adopt_legacy_account:
        raise ProvisioningError("--cleanup-bootstrap cannot be combined with identity or adoption options.")
    if args.dry_run == args.confirm:
        raise ProvisioningError("Cleanup requires exactly one of --dry-run or --confirm.")
    path = sqlite_path(args.database_url)
    state = detect_database_state(path)
    if state.name != "current":
        raise ProvisioningError("Bootstrap cleanup requires the exact current schema; no migration is performed.")
    command.check(alembic_config(path))
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN" if args.dry_run else "BEGIN IMMEDIATE")
        try:
            identity = (DEFAULT_DEV_USER_ID.hex,)
            owner_filter = "lower(replace(user_id, '-', '')) = ?"
            users = connection.execute(f"SELECT user_id FROM app_users WHERE {owner_filter}", identity).fetchall()
            if len(users) != 1:
                raise ProvisioningError("Cleanup requires exactly one DEFAULT_DEV_USER_ID bootstrap identity.")
            accounts = connection.execute(
                f"SELECT id, starting_cash, cash_balance FROM paper_accounts WHERE {owner_filter}", identity
            ).fetchall()
            if len(accounts) != 1:
                raise ProvisioningError(f"Cleanup requires exactly one bootstrap account; found {len(accounts)}.")
            account_id, starting_cash, cash_balance = accounts[0]
            if starting_cash != 10000 or cash_balance != 10000:
                raise ProvisioningError("Bootstrap starting_cash and cash_balance must both equal 10000.")
            for table in ("paper_positions", "paper_trades"):
                if connection.execute(f"SELECT COUNT(*) FROM {table} WHERE account_id=?", (account_id,)).fetchone()[0]:
                    raise ProvisioningError(f"Bootstrap owns data in {table}; cleanup refused.")
            for table in ("watchlist_items", "user_preferences"):
                if connection.execute(f"SELECT COUNT(*) FROM {table} WHERE {owner_filter}", identity).fetchone()[0]:
                    raise ProvisioningError(f"Bootstrap owns data in {table}; cleanup refused.")
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise ProvisioningError("Foreign-key violations detected; cleanup refused.")
            report = {
                "database": str(path), "dry_run": args.dry_run,
                "bootstrap_user_id": str(DEFAULT_DEV_USER_ID), "account_id": account_id,
                "starting_cash": starting_cash, "cash_balance": cash_balance,
                "planned": ["delete unused bootstrap account and DEFAULT_DEV_USER_ID identity only"],
            }
            if args.dry_run:
                report["result"] = "safe cleanup planned; no changes made"
                connection.rollback()
                return report
            report["backup"] = str(create_backup(path, Path(args.backup_directory) if args.backup_directory else None))
            connection.execute("DELETE FROM paper_accounts WHERE id=?", (account_id,))
            connection.execute("DELETE FROM app_users WHERE user_id=?", users[0])
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise ProvisioningError("Foreign-key validation failed; cleanup rolled back.")
            connection.commit()
            report["result"] = "unused bootstrap account and identity removed"
            return report
        except Exception:
            connection.rollback()
            raise


def provision_postgres(args, user_id, email):
    """Normal onboarding only; schema creation and legacy operations stay external."""
    from app.cli.migrate_sqlite_to_postgres import identity, revision, schema_blockers

    if args.adopt_legacy_account or getattr(args, "cleanup_bootstrap", False):
        raise ProvisioningError("Legacy adoption and bootstrap cleanup are SQLite-only.")
    if user_id == DEFAULT_DEV_USER_ID:
        raise ProvisioningError("The bootstrap UUID cannot be provisioned on PostgreSQL.")
    if args.dry_run and args.confirm:
        raise ProvisioningError("Choose --dry-run or --confirm, not both.")
    engine = None
    try:
        engine = create_database_engine(args.database_url)
        with engine.begin() as connection:
            if args.dry_run:
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            connection.exec_driver_sql("SET LOCAL search_path TO public, pg_catalog")
            if revision(connection) != HEAD_REVISION:
                raise ProvisioningError("PostgreSQL must already be at Alembic head; run Alembic separately.")
            blockers = schema_blockers(connection, "target")
            if blockers:
                raise ProvisioningError(" ".join(blockers))
            factory = sessionmaker(bind=connection, expire_on_commit=False)
            with session_scope(factory) as session:
                if session.get(AppUser, DEFAULT_DEV_USER_ID) is not None:
                    raise ProvisioningError("Unexpected bootstrap identity; PostgreSQL onboarding blocked.")
                if args.dry_run:
                    # Validate conflicts without inserts or sequence consumption.
                    _validate_identity(session, user_id, email, args.display_name)
                    accounts = list(session.scalars(select(PaperAccount).where(PaperAccount.user_id == user_id)))
                    operation = {"result": "already provisioned" if accounts else "would provision",
                                 "accounts": _account_details(session, accounts)}
                else:
                    operation = _provision_normal(session, user_id, email, args.display_name)
            return {"database_type": "postgresql", "target_identity": identity(engine),
                    "revision": HEAD_REVISION, "dry_run": args.dry_run, **operation}
    except ProvisioningError:
        raise
    except Exception as exc:
        raise ProvisioningError(
            f"PostgreSQL provisioning failed ({type(exc).__name__}); inspect target and rerun safely."
        ) from None
    finally:
        if engine is not None:
            engine.dispose()


def run(args) -> dict:
    try:
        backend = resolve_database_url(args.database_url).get_backend_name()
    except Exception:
        raise ProvisioningError("Invalid database URL; check its format and encoded credentials.") from None
    if backend == "postgresql":
        if args.adopt_legacy_account or getattr(args, "cleanup_bootstrap", False):
            raise ProvisioningError("Legacy adoption and bootstrap cleanup are SQLite-only.")
        if not args.user_id or not args.email:
            raise ProvisioningError("Provisioning requires --user-id and --email.")
        return provision_postgres(args, *_normalize_identity(args.user_id, args.email))
    if getattr(args, "cleanup_bootstrap", False):
        return cleanup_bootstrap(args)
    if not args.user_id or not args.email:
        raise ProvisioningError("Provisioning requires --user-id and --email.")
    user_id, email = _normalize_identity(args.user_id, args.email)
    database_path = sqlite_path(args.database_url)
    state = detect_database_state(database_path)
    if state.name == "unexpected":
        raise ProvisioningError(f"Refusing unexpected/mixed schema: {sorted(state.tables)} (revision={state.revision})")
    before = snapshot_portfolio(database_path, state)
    report = {
        "database": str(database_path), "state": state.name, "revision": state.revision,
        "target_user_id": str(user_id), "target_email": email,
        "file_size": database_path.stat().st_size, "sha256": database_sha256(database_path),
        "accounts": len(before["accounts"]), "positions": len(before["positions"]), "trades": len(before["trades"]),
        "account_ids": [row["id"] for row in before["accounts"]],
        "cash_balances": [row["cash_balance"] for row in before["accounts"]],
        "starting_balances": [row["starting_cash"] for row in before["accounts"]],
        "position_ids": [row["id"] for row in before["positions"]],
        "position_symbols": [row["symbol"] for row in before["positions"]],
        "trade_ids": [row["id"] for row in before["trades"]],
        "snapshot_scope": "pre-operation",
        "portfolio_before": before,
        "planned": [], "dry_run": args.dry_run,
        "steps": {
            "backup_creation": "not started",
            "alembic_stamp": "not needed" if state.name != "legacy-unstamped" else "not started",
            "alembic_upgrade": "not needed" if state.name == "current" else "not started",
            "schema_verification": "not started",
            "app_user_provisioning": "not started",
            "account_creation": "not applicable" if args.adopt_legacy_account else "not started",
            "account_ownership_reassignment": "not started" if args.adopt_legacy_account else "not applicable",
            "bootstrap_cleanup": "not started" if args.adopt_legacy_account else "not applicable",
            "foreign_key_validation": "not started",
            "portfolio_data_verification": "not started",
            "alembic_metadata_check": "not started",
        },
    }
    if state.name != "current":
        report["planned"].extend([f"stamp {BASELINE_REVISION}" if state.name == "legacy-unstamped" else "baseline already stamped", f"upgrade {HEAD_REVISION}"])
    if args.adopt_legacy_account:
        report["planned"].append("provision active app_user and atomically reassign the bootstrap account")
        report["adoption_possible"] = len(before["accounts"]) == 1
    else:
        report["planned"].append("provision active app_user and create fresh $10,000 paper account (retain existing target account on rerun; no adoption)")
    if args.dry_run:
        report["steps"] = {key: "planned" if value == "not started" else value for key, value in report["steps"].items()}
        if state.name == "current":
            report["before"] = inspect_current(database_path, user_id)
            if args.adopt_legacy_account and report["before"]["target_account_count"] == 1 and report["before"]["bootstrap_account_count"] == 0:
                report["result"] = "adoption already complete; target owns one account and nothing will be changed"
        return report
    if args.adopt_legacy_account and not args.confirm:
        raise ProvisioningError("Real legacy adoption requires --confirm (or use --dry-run).")

    try:
        backup = create_backup(database_path, Path(args.backup_directory) if args.backup_directory else None)
        report["backup"] = str(backup)
        report["steps"]["backup_creation"] = "committed"

        config = alembic_config(database_path)
        if state.name == "legacy-unstamped":
            command.stamp(config, BASELINE_REVISION)
            report["steps"]["alembic_stamp"] = f"committed ({BASELINE_REVISION})"
        if state.name != "current":
            command.upgrade(config, "head")
            report["steps"]["alembic_upgrade"] = f"committed ({HEAD_REVISION})"
        current = detect_database_state(database_path)
        if current.name != "current":
            raise ProvisioningError("Database did not reach the expected current schema.")
        report["steps"]["schema_verification"] = f"passed ({HEAD_REVISION})"
        report["revision"] = HEAD_REVISION

        operation = provision_current_database(
            database_path, user_id, email, args.display_name, args.adopt_legacy_account
        )
        report["result"] = operation["result"]
        report["steps"]["app_user_provisioning"] = "committed" if operation["app_user_created"] else "already complete"
        if args.adopt_legacy_account:
            report["steps"]["account_ownership_reassignment"] = "committed" if operation["ownership_reassigned"] else "already complete"
            report["steps"]["bootstrap_cleanup"] = "committed" if operation["bootstrap_removed"] else "already complete"
        else:
            report["steps"]["account_creation"] = "committed" if operation["account_created"] else "already complete"

        after = snapshot_portfolio(database_path, current)
        if args.adopt_legacy_account and before != after:
            raise ProvisioningError("Portfolio equivalence check failed; inspect current state before considering the named backup.")
        report["portfolio_equivalent"] = before == after if args.adopt_legacy_account else None
        report["steps"]["portfolio_data_verification"] = "passed"

        with closing(sqlite3.connect(database_path)) as connection:
            violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise ProvisioningError(f"Post-operation foreign-key violations: {violations}")
        report["foreign_key_violations"] = 0
        report["steps"]["foreign_key_validation"] = "passed"

        report["after"] = inspect_current(database_path, user_id)
        command.check(config)
        report["steps"]["alembic_metadata_check"] = "passed"
        report["post_sha256"] = database_sha256(database_path)
        return report
    except Exception as exc:
        if isinstance(exc, ProvisioningError) and exc.report is not None:
            raise
        report["failure"] = str(exc)
        try:
            if detect_database_state(database_path).name == "current":
                report["current_at_failure"] = inspect_current(database_path, user_id)
        except Exception:
            report["current_at_failure"] = "inspection unavailable"
        report["recovery"] = "Inspect the reported committed steps and current database state, then rerun; do not restore the backup blindly."
        raise ProvisioningError(str(exc), report=report) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Provision an invite-only TradePilot beta user.")
    parser.add_argument("--user-id", help="UUID copied from Supabase Dashboard Authentication > Users")
    parser.add_argument("--email")
    parser.add_argument("--display-name")
    parser.add_argument("--database-url", default=settings.database_url)
    parser.add_argument("--backup-directory")
    parser.add_argument("--adopt-legacy-account", action="store_true")
    parser.add_argument("--cleanup-bootstrap", action="store_true", help="Remove only the unused compatibility bootstrap identity/account")
    parser.add_argument("--confirm", action="store_true", help="Required for a real legacy ownership transfer or bootstrap cleanup")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    try:
        report = run(parser.parse_args())
    except ProvisioningError as exc:
        if exc.report:
            print("Provisioning stopped after the following durable-step status:")
            for key, value in exc.report.items():
                print(f"{key}: {value}")
        parser.exit(2, f"Provisioning aborted: {exc}\n")
    print("Supabase existence is operator-verified; no Auth Admin secret is used.")
    for key, value in report.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

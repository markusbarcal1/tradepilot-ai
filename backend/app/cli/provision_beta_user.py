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
from app.models.user import AppUser
from app.repositories.users import UserRepository


BASELINE_REVISION = "20260828_01"
HEAD_REVISION = "20260829_02"
LEGACY_TABLES = {"paper_account", "paper_positions", "paper_trades"}
CURRENT_TABLES = {
    "app_users", "paper_accounts", "paper_positions", "paper_trades",
    "watchlist_items", "user_preferences", "alembic_version",
}
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class ProvisioningError(RuntimeError):
    pass


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


def inspect_current(database_path: Path, target_id: UUID) -> dict:
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with session_scope(factory) as session:
            target = session.get(AppUser, target_id)
            bootstrap = session.get(AppUser, DEFAULT_DEV_USER_ID)
            bootstrap_accounts = list(session.scalars(select(PaperAccount).where(PaperAccount.user_id == DEFAULT_DEV_USER_ID)))
            target_accounts = list(session.scalars(select(PaperAccount).where(PaperAccount.user_id == target_id)))
            legacy = bootstrap_accounts[0] if len(bootstrap_accounts) == 1 else None
            counts = {"positions": 0, "trades": 0}
            if legacy:
                counts["positions"] = session.execute(text("SELECT COUNT(*) FROM paper_positions WHERE account_id=:id"), {"id": legacy.id}).scalar_one()
                counts["trades"] = session.execute(text("SELECT COUNT(*) FROM paper_trades WHERE account_id=:id"), {"id": legacy.id}).scalar_one()
            return {
                "target_exists": target is not None,
                "bootstrap_exists": bootstrap is not None,
                "bootstrap_account_count": len(bootstrap_accounts),
                "target_account_count": len(target_accounts),
                "legacy_account_id": legacy.id if legacy else None,
                **counts,
            }
    finally:
        engine.dispose()


def provision_current_database(database_path: Path, user_id: UUID, email: str, display_name: str | None, adopt_legacy: bool) -> str:
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with session_scope(factory) as session:
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
            else:
                target = users.create(user_id, email=email, display_name=display_name, beta_status="active")

            if not adopt_legacy:
                return "already provisioned" if email_owner is not None else "provisioned"

            bootstrap_accounts = list(session.scalars(select(PaperAccount).where(PaperAccount.user_id == DEFAULT_DEV_USER_ID)))
            target_accounts = list(session.scalars(select(PaperAccount).where(PaperAccount.user_id == user_id)))
            bootstrap = users.get(DEFAULT_DEV_USER_ID)
            bootstrap_account_count = session.execute(
                text("SELECT COUNT(*) FROM paper_accounts WHERE lower(replace(user_id, '-', '')) = :user_id"),
                {"user_id": DEFAULT_DEV_USER_ID.hex},
            ).scalar_one()
            if not bootstrap_accounts and bootstrap is None and len(target_accounts) == 1:
                return f"already provisioned and owns legacy account {target_accounts[0].id}"
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
            return f"provisioned and adopted legacy account {account.id}"
    finally:
        engine.dispose()


def run(args) -> dict:
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
        "planned": [], "dry_run": args.dry_run,
    }
    if state.name != "current":
        report["planned"].extend([f"stamp {BASELINE_REVISION}" if state.name == "legacy-unstamped" else "baseline already stamped", f"upgrade {HEAD_REVISION}"])
    if args.adopt_legacy_account:
        report["planned"].append("provision active app_user and atomically reassign the bootstrap account")
        report["adoption_possible"] = len(before["accounts"]) == 1
    else:
        report["planned"].append("provision active app_user without creating or adopting an account")
    if args.dry_run:
        if state.name == "current":
            report.update(inspect_current(database_path, user_id))
        return report
    if args.adopt_legacy_account and not args.confirm:
        raise ProvisioningError("Real legacy adoption requires --confirm (or use --dry-run).")

    backup = create_backup(database_path, Path(args.backup_directory) if args.backup_directory else None)
    report["backup"] = str(backup)
    current = migrate_to_head(database_path, state)
    result = provision_current_database(database_path, user_id, email, args.display_name, args.adopt_legacy_account)
    after = snapshot_portfolio(database_path, current)
    if before != after:
        raise ProvisioningError(f"Portfolio equivalence check failed. Restore from backup: {backup}")
    config = alembic_config(database_path)
    command.check(config)
    with closing(sqlite3.connect(database_path)) as connection:
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise ProvisioningError(f"Post-operation foreign-key violations: {violations}")
    report.update({"result": result, "revision": HEAD_REVISION, "portfolio_equivalent": True, "foreign_key_violations": 0, "post_sha256": database_sha256(database_path)})
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Provision an invite-only TradePilot beta user.")
    parser.add_argument("--user-id", required=True, help="UUID copied from Supabase Dashboard Authentication > Users")
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name")
    parser.add_argument("--database-url", default=settings.database_url)
    parser.add_argument("--backup-directory")
    parser.add_argument("--adopt-legacy-account", action="store_true")
    parser.add_argument("--confirm", action="store_true", help="Required for a real legacy ownership transfer")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    try:
        report = run(parser.parse_args())
    except ProvisioningError as exc:
        parser.exit(2, f"Provisioning aborted: {exc}\n")
    print("Supabase existence is operator-verified; no Auth Admin secret is used.")
    for key, value in report.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

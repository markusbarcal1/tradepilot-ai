"""Opt-in PostgreSQL tests use random databases, never the configured application DB."""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from unittest.mock import patch
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, delete, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.auth import CurrentUser
from app.bootstrap import DEFAULT_DEV_USER_ID
from app.cli import migrate_sqlite_to_postgres as migration
from app.db import create_database_engine, session_scope
from app.models.paper_trading import PaperAccount, PaperPosition, PaperTrade
from app.models.user import AppUser, UserPreference, WatchlistItem
from app.paper_trading import (PaperTradeRequest, buy, sell, read_account,
                               read_positions, read_trades, init_paper_trading_db)
from app.repositories import (PaperTradingRepository, PreferencesRepository,
                              UserRepository, WatchlistRepository)


A = UUID("10000000-0000-4000-8000-000000000001")
B = UUID("20000000-0000-4000-8000-000000000002")


def alembic_config(url):
    config = Config(str(migration.BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(migration.BACKEND / "migrations"))
    config.attributes["database_url"] = str(url)
    return config


@contextmanager
def disposable_postgres():
    value = os.environ.get("TRADEPILOT_TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set TRADEPILOT_TEST_DATABASE_URL for disposable PostgreSQL tests")
    url = make_url(value)
    if (url.drivername != "postgresql+psycopg" or url.database != "tradepilot_test"
            or url.host not in {"127.0.0.1", "localhost", "::1"}):
        pytest.fail("Test URL must point to loopback PostgreSQL database tradepilot_test")
    admin = create_engine(url, isolation_level="AUTOCOMMIT", hide_parameters=True)
    name = "tp_phase7_test_" + uuid4().hex
    created = False
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
        created = True
        yield url.set(database=name).render_as_string(hide_password=False)
    finally:
        if created:
            with admin.connect() as connection:
                connection.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.dispose()


@pytest.fixture
def pg_url():
    with disposable_postgres() as url:
        yield url


@pytest.fixture(params=["sqlite", "postgresql"])
def database(request, tmp_path):
    @contextmanager
    def sqlite_url():
        yield f"sqlite:///{(tmp_path / 'source.db').as_posix()}"

    with (sqlite_url() if request.param == "sqlite" else disposable_postgres()) as url:
        config = alembic_config(url)
        command.upgrade(config, "head")
        command.check(config)
        engine = create_database_engine(url)
        try:
            with engine.begin() as connection:
                # Existing SQLite migration deliberately retains compatibility bootstrap.
                if request.param == "sqlite":
                    connection.execute(delete(AppUser).where(AppUser.user_id == DEFAULT_DEV_USER_ID))
                assert connection.scalar(select(AppUser.user_id)) is None
            yield engine
        finally:
            engine.dispose()


def seed(engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_scope(factory) as session:
        for uid in (A, B):
            UserRepository(session).create(uid, email=f"{uid}@example.test")
            account = PaperTradingRepository(session).create_account(uid, 10000)
            PaperTradingRepository(session).create_position(account.id, "AAPL", 1.25, 100.15)
            PaperTradingRepository(session).create_trade(
                account_id=account.id, symbol="AAPL", side="SELL", shares=.25,
                price=110.25, total_value=27.5625, realized_pnl=2.525)
            WatchlistRepository(session).add(uid, "AAPL")
            PreferencesRepository(session).upsert(uid, {"limit": 10 if uid == A else 20,
                                                         "nested": {"enabled": True}})
        PreferencesRepository(session).upsert_theme(A, "dark")
    return factory


def test_migrations_types_isolation_and_ordering(database):
    factory = seed(database)
    with session_scope(factory) as session:
        paper = PaperTradingRepository(session)
        a, b = paper.get_account_for_user(A), paper.get_account_for_user(B)
        assert isinstance(a.user_id, UUID)
        assert a.id != b.id
        assert paper.ensure_account_for_user(A, 99).id == a.id
        paper.update_account_balance(a, 9876.54)
        paper.update_position(paper.get_position(a.id, "AAPL"), shares=2)
        second = paper.create_trade(account_id=a.id, symbol="MSFT", side="BUY", shares=1,
                                    price=1, total_value=1, realized_pnl=0)
        for trade in paper.list_trades_for_account(a.id):
            trade.created_at = "2026-01-01 00:00:00"
        WatchlistRepository(session).add(A, "MSFT")
        WatchlistRepository(session).add(A, "MSFT")  # Repository is idempotent.
        PreferencesRepository(session).upsert_theme(B, "light")
    with session_scope(factory) as session:
        paper = PaperTradingRepository(session)
        assert paper.get_account_for_user(B).cash_balance == 10000
        assert paper.get_account_for_user(A).cash_balance == 9876.54
        assert paper.list_positions_for_account(a.id)[0].shares == 2
        assert paper.list_positions_for_account(b.id)[0].shares == 1.25
        assert [t.id for t in paper.list_trades_for_account(a.id)][0] == second.id
        assert len(paper.list_trades_for_account(b.id)) == 1
        assert paper.get_trade(b.id, second.id) is None
        assert WatchlistRepository(session).list_symbols(A) == ["AAPL", "MSFT"]
        assert WatchlistRepository(session).list_symbols(B) == ["AAPL"]
        assert PreferencesRepository(session).get(A)["limit"] == 10
        assert PreferencesRepository(session).get(B)["limit"] == 20
        assert PreferencesRepository(session).get_theme(A) == "dark"
        assert PreferencesRepository(session).get_theme(B) == "light"
        assert isinstance(paper.get_account_for_user(A).updated_at, str)
    if database.dialect.name == "postgresql":
        assert str(inspect(database).get_columns("app_users")[0]["type"]) == "UUID"
        with database.connect() as connection:
            assert connection.scalar(text("SHOW TIME ZONE")) == "UTC"


@pytest.mark.parametrize("violation", ["account", "position", "watchlist", "account_fk",
                                       "position_fk", "trade_fk", "watchlist_fk", "preference_fk"])
def test_constraints_and_rollback(database, violation):
    factory = seed(database)
    with session_scope(factory) as session:
        account_id = PaperTradingRepository(session).get_account_for_user(A).id
    invalid_user = uuid4()
    rows = {
        "account": PaperAccount(user_id=A, cash_balance=1, starting_cash=1),
        "position": PaperPosition(account_id=account_id, symbol="AAPL", shares=1, avg_cost=1),
        "watchlist": WatchlistItem(user_id=A, symbol="AAPL"),
        "account_fk": PaperAccount(user_id=invalid_user, cash_balance=1, starting_cash=1),
        "position_fk": PaperPosition(account_id=999999, symbol="X", shares=1, avg_cost=1),
        "trade_fk": PaperTrade(account_id=999999, symbol="X", side="BUY", shares=1, price=1, total_value=1),
        "watchlist_fk": WatchlistItem(user_id=invalid_user, symbol="X"),
        "preference_fk": UserPreference(user_id=invalid_user),
    }
    with pytest.raises(IntegrityError), session_scope(factory) as session:
        PaperTradingRepository(session).update_account_balance(session.get(PaperAccount, account_id), 7)
        session.add(rows[violation])
    with session_scope(factory) as session:
        assert session.get(PaperAccount, account_id).cash_balance == 10000


@pytest.mark.parametrize("delete_user", [False, True])
def test_delete_cascades_are_owner_scoped(database, delete_user):
    factory = seed(database)
    with session_scope(factory) as session:
        account = PaperTradingRepository(session).get_account_for_user(A)
        session.execute(delete(AppUser).where(AppUser.user_id == A) if delete_user else
                        delete(PaperAccount).where(PaperAccount.id == account.id))
    with session_scope(factory) as session:
        assert PaperTradingRepository(session).get_account_for_user(A) is None
        assert not PaperTradingRepository(session).list_positions_for_account(account.id)
        assert not PaperTradingRepository(session).list_trades_for_account(account.id)
        assert (session.get(AppUser, A) is None) == delete_user
        assert (session.get(UserPreference, A) is None) == delete_user
        assert bool(WatchlistRepository(session).list_symbols(A)) != delete_user
        assert PaperTradingRepository(session).get_account_for_user(B) is not None
        assert WatchlistRepository(session).list_symbols(B) == ["AAPL"]


def test_buy_sell_success_and_failure_are_atomic(database):
    factory = seed(database)
    user = CurrentUser(user_id=A)
    with patch("app.paper_trading.session_scope", side_effect=lambda: session_scope(factory)):
        buy(PaperTradeRequest(symbol="MSFT", shares=2, price=100), user)
        sell(PaperTradeRequest(symbol="MSFT", shares=1, price=120), user)
        assert read_account(user)["cash_balance"] == 9920
        for operation in (buy, sell):
            before = (read_account(user), read_positions(user), read_trades(user))
            with patch.object(PaperTradingRepository, "create_trade", side_effect=RuntimeError("injected")):
                with pytest.raises(RuntimeError):
                    operation(PaperTradeRequest(symbol="MSFT", shares=1, price=100), user)
            assert (read_account(user), read_positions(user), read_trades(user)) == before


@pytest.fixture
def populated_source(tmp_path):
    path = tmp_path / "populated.db"
    url = f"sqlite:///{path.as_posix()}"
    command.upgrade(alembic_config(url), "head")
    engine = create_database_engine(url)
    with engine.begin() as connection:
        connection.execute(delete(AppUser).where(AppUser.user_id == DEFAULT_DEV_USER_ID))
    seed(engine)
    # Nontrivial explicit IDs prove copying and sequence correction, including gaps.
    with engine.begin() as connection:
        connection.execute(PaperTrade.__table__.update().values(id=PaperTrade.id + 100))
        connection.execute(PaperPosition.__table__.update().values(id=PaperPosition.id + 200))
        connection.execute(PaperTrade.__table__.update().values(created_at="2026-07-01T12:34:56.123456+00:00"))
    engine.dispose()
    yield path


def prepare_target(url):
    command.upgrade(alembic_config(url), "head")
    command.check(alembic_config(url))


def test_copy_dry_run_verify_backup_sequences_and_nonempty_refusal(pg_url, populated_source, tmp_path):
    prepare_target(pg_url)
    original = hashlib.sha256(populated_source.read_bytes()).hexdigest()
    backup_dir = tmp_path / "backups"
    report = migration.run_migration(str(populated_source), pg_url, backup_dir=backup_dir)
    assert report["migration_possible"], report
    assert report["dry_run"] and report["target_empty"]
    assert report["source_users"] == report["source_accounts"] == 2
    assert not backup_dir.exists()
    assert not report["committed"]
    copied = migration.run_migration(str(populated_source), pg_url, mode="confirm", backup_dir=backup_dir)
    assert copied["committed"] and copied["verified"], copied
    assert copied["target"] == copied["source"]
    assert Path(copied["backup"]).is_file()
    assert hashlib.sha256(populated_source.read_bytes()).hexdigest() == original
    verified = migration.run_migration(str(populated_source), pg_url, mode="verify-only")
    assert verified["verified"]
    assert (verified["source_type"], verified["target_type"]) == ("sqlite", "postgresql")
    assert verified["integrity"]["foreign_key_violations"] == 0
    assert verified["integrity"]["bootstrap_present"] is False
    assert all(s["next_id"] >= s["minimum_next_id"] for s in verified["sequences"].values())
    repeated = migration.run_migration(str(populated_source), pg_url, mode="confirm", backup_dir=backup_dir)
    assert not repeated["committed"] and not repeated["migration_possible"]
    assert len(list(backup_dir.iterdir())) == 1
    engine = create_database_engine(pg_url)
    try:
        factory = sessionmaker(bind=engine)
        with session_scope(factory) as session:
            uid = uuid4()
            UserRepository(session).create(uid)
            paper = PaperTradingRepository(session)
            account = paper.create_account(uid, 10000)
            position = paper.create_position(account.id, "NEW", 1, 1)
            trade = paper.create_trade(account_id=account.id, symbol="NEW", side="BUY",
                                       shares=1, price=1, total_value=1, realized_pnl=0)
            assert account.id == copied["sequence_next_ids"]["paper_accounts"]
            assert position.id > 200
            assert trade.id > 100
        command.check(alembic_config(pg_url))
    finally:
        engine.dispose()


@pytest.mark.parametrize("failure", ["verification", "sequence", "backup", "insert"])
def test_failed_copy_rolls_back_target_and_sequences(pg_url, populated_source, tmp_path, failure):
    prepare_target(pg_url)
    engine = create_database_engine(pg_url)
    try:
        with engine.connect() as connection:
            sequence = connection.scalar(text("SELECT pg_get_serial_sequence('paper_accounts', 'id')"))
            initial = connection.exec_driver_sql(f"SELECT last_value, is_called FROM {sequence}").one()
        actual_verify = migration.verify_data
        calls = 0

        def fail_final_verification(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise migration.MigrationBlocked("Injected verification failure")
            return actual_verify(*args)

        if failure == "insert":
            # A target-side constraint passes metadata shape comparison but rejects inserts.
            with engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE paper_trades ADD CONSTRAINT reject_copy CHECK (shares < 0)")
        method = {"verification": "verify_data", "sequence": "synchronize_sequences",
                  "backup": "backup_source", "insert": "identity"}[failure]
        effect = fail_final_verification if failure == "verification" else (
            migration.identity if failure == "insert" else migration.MigrationBlocked("Injected failure"))
        with patch.object(migration, method, side_effect=effect):
            report = migration.run_migration(str(populated_source), pg_url, mode="confirm", backup_dir=tmp_path / "backups")
        assert not report["committed"] and report["blockers"], report
        with engine.connect() as connection:
            assert not any(migration.snapshot(connection).values())
            assert connection.exec_driver_sql(f"SELECT last_value, is_called FROM {sequence}").one() == initial
    finally:
        engine.dispose()


@pytest.mark.parametrize("problem", ["source_revision", "target_revision", "source_drift", "target_drift", "orphan", "bootstrap"])
def test_dry_run_reports_blockers_without_writes(pg_url, populated_source, tmp_path, problem):
    prepare_target(pg_url)
    if problem.startswith("target"):
        engine = create_database_engine(pg_url)
        with engine.begin() as connection:
            connection.exec_driver_sql("UPDATE alembic_version SET version_num='old'" if problem == "target_revision"
                                       else "ALTER TABLE app_users ADD COLUMN unexpected TEXT")
        engine.dispose()
    else:
        with sqlite3.connect(populated_source) as connection:
            if problem == "source_revision":
                connection.execute("UPDATE alembic_version SET version_num='old'")
            elif problem == "source_drift":
                connection.execute("ALTER TABLE app_users ADD COLUMN unexpected TEXT")
            elif problem == "orphan":
                connection.execute("UPDATE paper_positions SET account_id=999999 WHERE id=(SELECT MIN(id) FROM paper_positions)")
            else:
                connection.execute("INSERT INTO app_users(user_id) VALUES (?)", (DEFAULT_DEV_USER_ID.hex,))
    original = populated_source.read_bytes()
    report = migration.run_migration(str(populated_source), pg_url, backup_dir=tmp_path / "backups")
    assert report["blockers"] and not report["migration_possible"]
    assert populated_source.read_bytes() == original
    assert not (tmp_path / "backups").exists()


def test_postgres_startup_never_creates_schema(pg_url):
    engine = create_database_engine(pg_url)
    try:
        with pytest.raises(RuntimeError, match="Alembic"):
            init_paper_trading_db(engine)
        assert inspect(engine).get_table_names() == []
    finally:
        engine.dispose()


def test_source_readonly_and_missing_source_never_created(tmp_path, populated_source):
    with migration.readonly_source(populated_source) as connection:
        with pytest.raises(Exception):
            connection.exec_driver_sql("DELETE FROM app_users")
    missing = tmp_path / "missing.db"
    report = migration.run_migration(str(missing), "postgresql+psycopg://test:secret@localhost/test")
    assert report["blockers"] and not missing.exists()
    assert "secret" not in json.dumps(report)


def test_full_row_verification_detects_changes_and_tolerates_float_roundoff(populated_source):
    import copy
    with migration.readonly_source(populated_source) as connection:
        before = migration.snapshot(connection)
    after = copy.deepcopy(before)
    after["paper_accounts"][0]["cash_balance"] += 1e-9
    migration.verify_data(before, after)
    for table, column, value in (("paper_positions", "avg_cost", 123),
                                 ("paper_trades", "created_at", "wrong"),
                                 ("user_preferences", "scanner_preferences", {"changed": True})):
        changed = copy.deepcopy(before)
        changed[table][0][column] = value
        with pytest.raises(migration.MigrationBlocked):
            migration.verify_data(before, changed)


def test_postgres_populated_baseline_upgrade_preserves_rows(pg_url):
    config = alembic_config(pg_url)
    command.upgrade(config, "20260828_01")
    engine = create_database_engine(pg_url)
    try:
        with engine.begin() as connection:
            account_id = connection.scalar(text(
                "INSERT INTO paper_account(cash_balance, starting_cash) VALUES (4321.25, 10000) RETURNING id"))
            position_id = connection.scalar(text(
                "INSERT INTO paper_positions(symbol, shares, avg_cost) VALUES ('AAPL', 1.25, 101.15) RETURNING id"))
            trade_id = connection.scalar(text(
                "INSERT INTO paper_trades(symbol, side, shares, price, total_value) "
                "VALUES ('AAPL', 'BUY', 1.25, 101.15, 126.4375) RETURNING id"))
        command.upgrade(config, "head")
        command.check(config)
        with engine.connect() as connection:
            assert connection.scalar(select(PaperAccount.user_id)) == DEFAULT_DEV_USER_ID
            assert connection.scalar(select(PaperAccount.cash_balance)) == 4321.25
            assert connection.execute(select(PaperPosition.id, PaperPosition.account_id)).one() == (position_id, account_id)
            assert connection.execute(select(PaperTrade.id, PaperTrade.account_id)).one() == (trade_id, account_id)
        with session_scope(sessionmaker(bind=engine)) as session:
            UserRepository(session).create(A)
            assert PaperTradingRepository(session).create_account(A, 10000).id > account_id
    finally:
        engine.dispose()


def test_verify_only_detects_sequence_regression(pg_url, populated_source, tmp_path):
    prepare_target(pg_url)
    report = migration.run_migration(str(populated_source), pg_url, mode="confirm", backup_dir=tmp_path / "backups")
    assert report["committed"], report
    engine = create_database_engine(pg_url)
    try:
        with engine.begin() as connection:
            sequence, _minimum = migration.sequence_details(connection)["paper_trades"]
            connection.exec_driver_sql(f"ALTER SEQUENCE {sequence} RESTART WITH 1")
        report = migration.run_migration(str(populated_source), pg_url, mode="verify-only")
        assert "sequence is behind" in " ".join(report["blockers"])
    finally:
        engine.dispose()


def test_empty_source_copy_restarts_empty_sequences_at_one(pg_url, populated_source, tmp_path):
    with sqlite3.connect(populated_source) as connection:
        for table in reversed(migration.TABLES):
            connection.execute(f'DELETE FROM "{table.name}"')
    prepare_target(pg_url)
    report = migration.run_migration(str(populated_source), pg_url, mode="confirm", backup_dir=tmp_path / "backups")
    assert report["committed"], report
    assert set(report["sequence_next_ids"].values()) == {1}


def test_target_rls_is_blocked_even_for_owner(pg_url, populated_source):
    prepare_target(pg_url)
    engine = create_database_engine(pg_url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE app_users ENABLE ROW LEVEL SECURITY")
        report = migration.run_migration(str(populated_source), pg_url)
        assert "row-level security" in " ".join(report["blockers"])
    finally:
        engine.dispose()


def test_wal_source_backup_includes_committed_wal_rows(pg_url, populated_source, tmp_path):
    prepare_target(pg_url)
    # Hold a connection open so the new committed row stays in WAL during copy.
    connection = sqlite3.connect(populated_source)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA wal_autocheckpoint=0")
        connection.execute("INSERT INTO watchlist_items(user_id, symbol) VALUES (?, 'WAL')", (A.hex,))
        connection.commit()
        assert Path(str(populated_source) + "-wal").stat().st_size > 0
        report = migration.run_migration(str(populated_source), pg_url, mode="confirm", backup_dir=tmp_path / "backups")
        assert report["committed"] and report["source_watchlist"] == 3, report
        with migration.readonly_source(Path(report["backup"])) as backup:
            assert len(migration.snapshot(backup)["watchlist_items"]) == 3
    finally:
        connection.close()


def test_cli_requires_mode_and_redacts_invalid_targets(populated_source, capsys):
    with pytest.raises(SystemExit) as result:
        migration.main(["--source", str(populated_source)])
    assert result.value.code == 2
    assert migration.main(["--source", str(populated_source), "--dry-run", "--target-url",
                           "sqlite:///do-not-create-secret.db"]) == 1
    assert "do-not-create-secret" not in capsys.readouterr().out


def test_production_sqlite_startup_requires_alembic(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    try:
        with patch("app.paper_trading.settings.environment", "production"):
            with pytest.raises(RuntimeError, match="Alembic"):
                init_paper_trading_db(engine)
        assert not inspect(engine).get_table_names()
    finally:
        engine.dispose()

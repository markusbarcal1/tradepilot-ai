import argparse
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from contextlib import closing
from pathlib import Path
from uuid import UUID

from alembic import command
from sqlalchemy.orm import sessionmaker

from app.bootstrap import DEFAULT_DEV_USER_ID
from app.cli.provision_beta_user import (
    HEAD_REVISION,
    ProvisioningError,
    alembic_config,
    detect_database_state,
    provision_current_database,
    run,
    snapshot_portfolio,
)
from app.db import create_database_engine, session_scope
from app.repositories.paper_trading import PaperTradingRepository
from app.repositories.users import UserRepository
from app.paper_trading import init_paper_trading_db


TARGET_ID = UUID("11111111-2222-4333-8444-555555555555")
OTHER_ID = UUID("99999999-8888-4777-8666-555555555555")


class BetaProvisioningTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_current(self, name="current.db"):
        path = self.directory / name
        command.upgrade(alembic_config(path), "head")
        return path

    def make_unstamped_legacy(self):
        path = self.directory / "legacy.db"
        command.upgrade(alembic_config(path), "20260828_01")
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("INSERT INTO paper_account (id, cash_balance, starting_cash, created_at, updated_at) VALUES (7, 4321.25, 10000, '2025-01-01', '2025-02-01')")
            connection.executemany("INSERT INTO paper_positions (id, symbol, shares, avg_cost, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)", [
                (11, "ABCL", 2.5, 10.25, "2025-01-02", "2025-02-02"),
                (12, "ABTC", 3, 20, "2025-01-03", "2025-02-03"),
                (13, "EXE", 4, 30, "2025-01-04", "2025-02-04"),
                (14, "OMEX", 5, 40, "2025-01-05", "2025-02-05"),
            ])
            connection.executemany("INSERT INTO paper_trades (id, symbol, side, shares, price, total_value, realized_pnl, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
                (21, "ABCL", "BUY", 2.5, 10.25, 25.625, 0, "2025-01-02"),
                (22, "OMEX", "SELL", 1, 45, 45, 5, "2025-02-05"),
            ])
            connection.execute("DROP TABLE alembic_version")
            connection.commit()
        return path

    def args(self, path, **overrides):
        values = dict(
            user_id=str(TARGET_ID), email="beta@example.test", display_name="Beta User",
            database_url=f"sqlite:///{path.as_posix()}", backup_directory=str(self.directory / "backups"),
            adopt_legacy_account=False, confirm=False, dry_run=False,
        )
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_new_user_and_idempotent_rerun(self):
        path = self.make_current()
        first = run(self.args(path))
        second = run(self.args(path))
        self.assertEqual(first["result"], "provisioned")
        self.assertEqual(second["result"], "already provisioned")
        with closing(sqlite3.connect(path)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM app_users WHERE email='beta@example.test' AND beta_status='active'").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM paper_accounts WHERE user_id=?", (TARGET_ID.hex,)).fetchone()[0], 1)
            account = connection.execute("SELECT cash_balance, starting_cash FROM paper_accounts WHERE user_id=?", (TARGET_ID.hex,)).fetchone()
            self.assertEqual(account, (10000.0, 10000.0))
            account_id = connection.execute("SELECT id FROM paper_accounts WHERE user_id=?", (TARGET_ID.hex,)).fetchone()[0]
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM paper_positions WHERE account_id=?", (account_id,)).fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM paper_trades WHERE account_id=?", (account_id,)).fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM watchlist_items WHERE user_id=?", (TARGET_ID.hex,)).fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM user_preferences WHERE user_id=?", (TARGET_ID.hex,)).fetchone()[0], 0)

    def cleanup_args(self, path, **overrides):
        return self.args(path, user_id=None, email=None, display_name=None,
                         cleanup_bootstrap=True, **overrides)

    def test_cleanup_dry_run_and_confirm_preserve_real_portfolio(self):
        path = self.make_unstamped_legacy()
        run(self.args(path, adopt_legacy_account=True, confirm=True))
        engine = create_database_engine(f"sqlite:///{path.as_posix()}")
        try:
            with session_scope(sessionmaker(bind=engine)) as session:
                UserRepository(session).create(DEFAULT_DEV_USER_ID)
                PaperTradingRepository(session).create_account(DEFAULT_DEV_USER_ID, 10000)
        finally:
            engine.dispose()
        with closing(sqlite3.connect(path)) as connection:
            before = {table: connection.execute(f"SELECT * FROM {table}").fetchall()
                      for table in ("app_users", "paper_accounts", "paper_positions", "paper_trades")}
        original = path.read_bytes()
        report = run(self.cleanup_args(path, dry_run=True))
        self.assertIn("safe cleanup planned", report["result"])
        self.assertEqual(path.read_bytes(), original)
        report = run(self.cleanup_args(path, confirm=True))
        self.assertTrue(Path(report["backup"]).is_file())
        with closing(sqlite3.connect(path)) as connection:
            self.assertEqual(connection.execute("SELECT * FROM app_users").fetchall(),
                             [row for row in before["app_users"] if row[0] != DEFAULT_DEV_USER_ID.hex])
            self.assertEqual(connection.execute("SELECT * FROM paper_accounts").fetchall(),
                             [row for row in before["paper_accounts"] if row[0] != report["account_id"]])
            for table in ("paper_positions", "paper_trades"):
                self.assertEqual(connection.execute(f"SELECT * FROM {table}").fetchall(), before[table])
        engine = create_database_engine(f"sqlite:///{path.as_posix()}")
        try:
            original = path.read_bytes()
            init_paper_trading_db(engine, sessionmaker(bind=engine))
            self.assertEqual(path.read_bytes(), original)
        finally:
            engine.dispose()

    def test_cleanup_refuses_owned_data_or_modified_balances(self):
        mutations = [
            ("INSERT INTO paper_positions (account_id,symbol,shares,avg_cost) SELECT id,'AAPL',1,10 FROM paper_accounts", "paper_positions"),
            ("INSERT INTO paper_trades (account_id,symbol,side,shares,price,total_value) SELECT id,'AAPL','BUY',1,10,10 FROM paper_accounts", "paper_trades"),
            ("UPDATE paper_accounts SET cash_balance=9999", "cash_balance"),
            ("UPDATE paper_accounts SET starting_cash=9999", "starting_cash"),
            ("INSERT INTO watchlist_items (user_id,symbol) SELECT user_id,'AAPL' FROM app_users", "watchlist_items"),
            ("INSERT INTO user_preferences (user_id) SELECT user_id FROM app_users", "user_preferences"),
            ("DELETE FROM paper_accounts", "exactly one bootstrap account"),
            ("CREATE TABLE other_owned_data (user_id TEXT)", "exact current schema"),
        ]
        for index, (sql, reason) in enumerate(mutations):
            with self.subTest(reason=reason):
                path = self.make_current(f"refuse_{index}.db")
                with closing(sqlite3.connect(path)) as connection:
                    connection.execute(sql)
                    connection.commit()
                before = path.read_bytes()
                for mode in ({"dry_run": True}, {"confirm": True}):
                    with self.assertRaisesRegex(ProvisioningError, reason):
                        run(self.cleanup_args(path, **mode))
                    self.assertEqual(path.read_bytes(), before)

    def test_cleanup_requires_explicit_mode(self):
        path = self.make_current()
        for mode in ({}, {"dry_run": True, "confirm": True}):
            with self.assertRaisesRegex(ProvisioningError, "exactly one of"):
                run(self.cleanup_args(path, **mode))

    def test_fresh_user_dry_run_reports_account_creation(self):
        path = self.make_current()
        before = path.read_bytes()
        report = run(self.args(path, dry_run=True))
        self.assertIn("create fresh $10,000 paper account", report["planned"][0])
        self.assertEqual(report["steps"]["account_creation"], "planned")
        self.assertEqual(path.read_bytes(), before)

    def test_startup_empty_and_repeat_and_existing_schema(self):
        path = self.directory / "empty.db"
        engine = create_database_engine(f"sqlite:///{path.as_posix()}")
        try:
            factory = sessionmaker(bind=engine)
            init_paper_trading_db(engine, factory)
            before = path.read_bytes()
            init_paper_trading_db(engine, factory)
            self.assertEqual(path.read_bytes(), before)
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute("SELECT user_id FROM app_users").fetchall(), [(DEFAULT_DEV_USER_ID.hex,)])
                self.assertEqual(connection.execute("SELECT starting_cash,cash_balance FROM paper_accounts").fetchall(), [(10000,10000)])
                connection.execute("DELETE FROM paper_accounts")
                connection.execute("DELETE FROM app_users")
                connection.commit()
            before = path.read_bytes()
            init_paper_trading_db(engine, factory)
            self.assertEqual(path.read_bytes(), before)
        finally:
            engine.dispose()

    def test_startup_rejects_phase_1b(self):
        path = self.make_unstamped_legacy()
        engine = create_database_engine(f"sqlite:///{path.as_posix()}")
        try:
            with self.assertRaisesRegex(RuntimeError, "Phase 1B"):
                init_paper_trading_db(engine, sessionmaker(bind=engine))
        finally:
            engine.dispose()

    def test_invalid_uuid_and_email_collision_are_rejected(self):
        path = self.make_current()
        with self.assertRaisesRegex(ProvisioningError, "valid UUID"):
            run(self.args(path, user_id="not-a-uuid", dry_run=True))
        run(self.args(path))
        with self.assertRaisesRegex(ProvisioningError, "different UUID"):
            run(self.args(path, user_id=str(OTHER_ID)))

    def test_conflicting_identity_for_same_uuid_is_rejected(self):
        path = self.make_current()
        run(self.args(path))
        with self.assertRaisesRegex(ProvisioningError, "conflicting identity"):
            run(self.args(path, email="changed@example.test"))

    def test_dry_run_does_not_mutate_unstamped_legacy_database(self):
        path = self.make_unstamped_legacy()
        before = path.read_bytes()
        report = run(self.args(path, adopt_legacy_account=True, dry_run=True))
        self.assertEqual(report["state"], "legacy-unstamped")
        self.assertEqual(report["positions"], 4)
        self.assertEqual(path.read_bytes(), before)

    def test_unstamped_legacy_to_head_adoption_preserves_every_portfolio_field(self):
        path = self.make_unstamped_legacy()
        state = detect_database_state(path)
        before = snapshot_portfolio(path, state)
        report = run(self.args(path, adopt_legacy_account=True, confirm=True))
        after_state = detect_database_state(path)
        after = snapshot_portfolio(path, after_state)
        self.assertEqual(after_state.revision, HEAD_REVISION)
        self.assertEqual(after, before)
        self.assertTrue(Path(report["backup"]).is_file())
        self.assertTrue(report["portfolio_equivalent"])
        with closing(sqlite3.connect(path)) as connection:
            owner = connection.execute("SELECT user_id FROM paper_accounts WHERE id=7").fetchone()[0]
            self.assertEqual(owner, TARGET_ID.hex)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM app_users WHERE user_id=? AND beta_status='active'", (TARGET_ID.hex,)).fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM app_users WHERE user_id=?", (DEFAULT_DEV_USER_ID.hex,)).fetchone()[0], 0)
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        rerun = run(self.args(path, adopt_legacy_account=True, confirm=True))
        self.assertIn("already provisioned and owns legacy account", rerun["result"])
        self.assertEqual(rerun["after"]["positions"], 4)
        self.assertEqual(rerun["after"]["trades"], 2)
        self.assertEqual(rerun["after"]["reported_owner"], "target")

        dry_run = run(self.args(path, adopt_legacy_account=True, dry_run=True))
        self.assertIn("adoption already complete", dry_run["result"])
        self.assertEqual(dry_run["before"]["positions"], 4)
        self.assertEqual(dry_run["before"]["trades"], 2)
        self.assertEqual(dry_run["before"]["target_accounts"][0]["position_symbols"], ["ABCL", "ABTC", "EXE", "OMEX"])
        self.assertEqual(dry_run["before"]["target_accounts"][0]["trade_id_range"], [21, 22])

    def test_new_users_are_isolated_and_each_get_exactly_one_empty_account(self):
        path = self.make_current()
        run(self.args(path))
        run(self.args(path, user_id=str(OTHER_ID), email="other@example.test", display_name="Other"))
        with closing(sqlite3.connect(path)) as connection:
            target_account = connection.execute("SELECT id FROM paper_accounts WHERE user_id=?", (TARGET_ID.hex,)).fetchone()[0]
            other_account = connection.execute("SELECT id FROM paper_accounts WHERE user_id=?", (OTHER_ID.hex,)).fetchone()[0]
            self.assertNotEqual(target_account, other_account)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM paper_accounts WHERE user_id IN (?, ?)", (TARGET_ID.hex, OTHER_ID.hex)).fetchone()[0], 2)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM paper_positions WHERE account_id IN (?, ?)", (target_account, other_account)).fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM paper_trades WHERE account_id IN (?, ?)", (target_account, other_account)).fetchone()[0], 0)

    def test_failure_after_migration_reports_committed_state_and_rerun_recovers(self):
        path = self.make_unstamped_legacy()
        with patch("app.cli.provision_beta_user.provision_current_database", side_effect=RuntimeError("simulated stop before adoption")):
            with self.assertRaises(ProvisioningError) as caught:
                run(self.args(path, adopt_legacy_account=True, confirm=True))
        report = caught.exception.report
        self.assertEqual(detect_database_state(path).revision, HEAD_REVISION)
        self.assertEqual(report["steps"]["backup_creation"], "committed")
        self.assertIn("committed", report["steps"]["alembic_stamp"])
        self.assertIn("committed", report["steps"]["alembic_upgrade"])
        self.assertEqual(report["steps"]["account_ownership_reassignment"], "not started")
        recovered = run(self.args(path, adopt_legacy_account=True, confirm=True))
        self.assertIn("adopted legacy account", recovered["result"])
        self.assertEqual(recovered["after"]["positions"], 4)
        self.assertEqual(recovered["after"]["trades"], 2)

    def test_adoption_rejects_target_with_different_account(self):
        path = self.make_current()
        engine = create_database_engine(f"sqlite:///{path.as_posix()}")
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        with session_scope(factory) as session:
            UserRepository(session).create(TARGET_ID, email="beta@example.test", display_name="Beta User")
            PaperTradingRepository(session).create_account(TARGET_ID, 10000)
        with self.assertRaisesRegex(ProvisioningError, "already owns"):
            provision_current_database(path, TARGET_ID, "beta@example.test", "Beta User", True)
        engine.dispose()

    def test_adoption_rejects_missing_or_multiple_bootstrap_accounts(self):
        missing = self.make_current("missing.db")
        with closing(sqlite3.connect(missing)) as connection:
            connection.execute("DELETE FROM paper_accounts WHERE user_id=?", (DEFAULT_DEV_USER_ID.hex,))
            connection.commit()
        with self.assertRaisesRegex(ProvisioningError, "exactly one"):
            provision_current_database(missing, TARGET_ID, "beta@example.test", "Beta User", True)

        multiple = self.make_current("multiple.db")
        with closing(sqlite3.connect(multiple)) as connection:
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("ALTER TABLE paper_accounts RENAME TO paper_accounts_old")
            connection.execute("CREATE TABLE paper_accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id CHAR(32) NOT NULL, cash_balance FLOAT NOT NULL, starting_cash FLOAT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL)")
            connection.execute("INSERT INTO paper_accounts (id, user_id, cash_balance, starting_cash, created_at, updated_at) SELECT id, user_id, cash_balance, starting_cash, created_at, updated_at FROM paper_accounts_old")
            connection.execute("INSERT INTO paper_accounts (user_id, cash_balance, starting_cash) SELECT user_id, 1, 1 FROM paper_accounts_old LIMIT 1")
            connection.commit()
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM paper_accounts").fetchone()[0], 2)
        with self.assertRaisesRegex(ProvisioningError, "exactly one"):
            provision_current_database(multiple, TARGET_ID, "beta@example.test", "Beta User", True)


if __name__ == "__main__":
    unittest.main()

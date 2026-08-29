import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from alembic import command
from alembic.config import Config


BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG = BACKEND_ROOT / "alembic.ini"
LEGACY_USER_ID = "00000000000040008000000000000001"


class MigrationTests(unittest.TestCase):
    def alembic_config(self, database_path):
        config = Config(str(ALEMBIC_CONFIG))
        config.attributes["database_url"] = f"sqlite:///{database_path.as_posix()}"
        return config

    def test_upgrade_head_builds_empty_database_without_metadata_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "empty.db"
            config = self.alembic_config(database_path)
            command.upgrade(config, "head")

            with closing(sqlite3.connect(database_path)) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
            self.assertTrue(
                {
                    "app_users", "paper_accounts", "paper_positions", "paper_trades",
                    "watchlist_items", "user_preferences", "alembic_version",
                }
                <= tables
            )
            command.check(config)

    def test_populated_baseline_upgrade_preserves_existing_application_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "existing.db"
            config = self.alembic_config(database_path)
            command.upgrade(config, "20260828_01")
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    "INSERT INTO paper_account (id, cash_balance, starting_cash) "
                    "VALUES (7, 4321.25, 10000)"
                )
                connection.executemany(
                    "INSERT INTO paper_positions "
                    "(id, symbol, shares, avg_cost, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        (11, "AAPL", 2, 100, "2026-01-01 00:00:00", "2026-01-02 00:00:00"),
                        (12, "MSFT", 3, 200, "2026-01-03 00:00:00", "2026-01-04 00:00:00"),
                    ],
                )
                connection.executemany(
                    "INSERT INTO paper_trades "
                    "(id, symbol, side, shares, price, total_value, realized_pnl, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (21, "AAPL", "BUY", 2, 100, 200, 0, "2026-01-01 00:00:00"),
                        (22, "MSFT", "SELL", 1, 210, 210, 10, "2026-01-05 00:00:00"),
                    ],
                )
                connection.commit()
                before = {
                    "account": connection.execute("SELECT * FROM paper_account ORDER BY id").fetchall(),
                    "positions": connection.execute("SELECT * FROM paper_positions ORDER BY id").fetchall(),
                    "trades": connection.execute("SELECT * FROM paper_trades ORDER BY id").fetchall(),
                }

            command.upgrade(config, "head")
            with closing(sqlite3.connect(database_path)) as connection:
                account = connection.execute(
                    "SELECT id, cash_balance, starting_cash, created_at, updated_at, user_id "
                    "FROM paper_accounts ORDER BY id"
                ).fetchall()
                positions = connection.execute(
                    "SELECT id, symbol, shares, avg_cost, created_at, updated_at, account_id "
                    "FROM paper_positions ORDER BY id"
                ).fetchall()
                trades = connection.execute(
                    "SELECT id, symbol, side, shares, price, total_value, realized_pnl, "
                    "created_at, account_id FROM paper_trades ORDER BY id"
                ).fetchall()
                revision = connection.execute(
                    "SELECT version_num FROM alembic_version"
                ).fetchone()[0]

            self.assertEqual(account[0][:-1], before["account"][0])
            self.assertEqual(account[0][-1], LEGACY_USER_ID)
            self.assertEqual([row[:-1] for row in positions], before["positions"])
            self.assertEqual([row[-1] for row in positions], [7, 7])
            self.assertEqual([row[:-1] for row in trades], before["trades"])
            self.assertEqual([row[-1] for row in trades], [7, 7])
            self.assertEqual(revision, "20260829_02")


if __name__ == "__main__":
    unittest.main()

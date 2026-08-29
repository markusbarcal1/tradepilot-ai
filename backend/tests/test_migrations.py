import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from alembic import command
from alembic.config import Config


BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG = BACKEND_ROOT / "alembic.ini"
EXISTING_DATABASE = BACKEND_ROOT / "app" / "paper_trading.db"


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
                {"paper_account", "paper_positions", "paper_trades", "alembic_version"}
                <= tables
            )
            command.check(config)

    def test_stamp_baseline_preserves_existing_application_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "existing.db"
            shutil.copy2(EXISTING_DATABASE, database_path)

            with closing(sqlite3.connect(database_path)) as connection:
                before = self.application_snapshot(connection)
            command.stamp(self.alembic_config(database_path), "20260828_01")
            with closing(sqlite3.connect(database_path)) as connection:
                after = self.application_snapshot(connection)
                revision = connection.execute(
                    "SELECT version_num FROM alembic_version"
                ).fetchone()[0]

            self.assertEqual(after, before)
            self.assertEqual(revision, "20260828_01")

    @staticmethod
    def application_snapshot(connection):
        return {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
            for table in ("paper_account", "paper_positions", "paper_trades")
        }


if __name__ == "__main__":
    unittest.main()

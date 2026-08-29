import tempfile
import unittest
from pathlib import Path
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db import create_database_engine, create_schema, session_scope
from app.models.paper_trading import PaperAccount, PaperPosition
from app.models.user import WatchlistItem
from app.repositories.paper_trading import PaperTradingRepository
from app.repositories.preferences import PreferencesRepository
from app.repositories.users import UserRepository
from app.repositories.watchlist import WatchlistRepository


USER_A = UUID("10000000-0000-4000-8000-000000000001")
USER_B = UUID("20000000-0000-4000-8000-000000000002")


class MultiUserPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "multi-user.db"
        self.engine = create_database_engine(f"sqlite:///{database_path}")
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        create_schema(self.engine)
        with session_scope(self.factory) as session:
            users = UserRepository(session)
            users.create(USER_A, email="a@example.test")
            users.create(USER_B, email="b@example.test")

    def tearDown(self):
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_all_repositories_isolate_two_users_with_same_symbol(self):
        with session_scope(self.factory) as session:
            paper = PaperTradingRepository(session)
            account_a = paper.create_account(USER_A, 9000)
            account_b = paper.create_account(USER_B, 8000)
            paper.create_position(account_a.id, "AAPL", 1, 100)
            paper.create_position(account_b.id, "AAPL", 2, 200)
            paper.create_trade(account_id=account_a.id, symbol="AAPL", side="BUY", shares=1, price=100, total_value=100, realized_pnl=0)
            paper.create_trade(account_id=account_b.id, symbol="AAPL", side="BUY", shares=2, price=200, total_value=400, realized_pnl=0)
            watchlist = WatchlistRepository(session)
            watchlist.add(USER_A, "AAPL")
            watchlist.add(USER_B, "AAPL")
            preferences = PreferencesRepository(session)
            preferences.upsert(USER_A, {"universe": "sp500"})
            preferences.upsert(USER_B, {"universe": "nasdaq"})

        with session_scope(self.factory) as session:
            paper = PaperTradingRepository(session)
            account_a = paper.get_account_for_user(USER_A)
            account_b = paper.get_account_for_user(USER_B)
            self.assertEqual(account_a.cash_balance, 9000)
            self.assertEqual(account_b.cash_balance, 8000)
            self.assertEqual([p.shares for p in paper.list_positions_for_account(account_a.id)], [1])
            self.assertEqual([p.shares for p in paper.list_positions_for_account(account_b.id)], [2])
            self.assertEqual([t.total_value for t in paper.list_trades_for_account(account_a.id)], [100])
            self.assertEqual([t.total_value for t in paper.list_trades_for_account(account_b.id)], [400])
            self.assertEqual(WatchlistRepository(session).list_symbols(USER_A), ["AAPL"])
            self.assertEqual(WatchlistRepository(session).list_symbols(USER_B), ["AAPL"])
            self.assertEqual(PreferencesRepository(session).get(USER_A), {"universe": "sp500"})
            self.assertEqual(PreferencesRepository(session).get(USER_B), {"universe": "nasdaq"})

    def test_one_account_per_user_is_enforced(self):
        with self.assertRaises(IntegrityError):
            with session_scope(self.factory) as session:
                session.add_all([
                    PaperAccount(user_id=USER_A, cash_balance=1, starting_cash=1),
                    PaperAccount(user_id=USER_A, cash_balance=2, starting_cash=2),
                ])

    def test_duplicate_position_and_watchlist_are_scoped_to_owner(self):
        with session_scope(self.factory) as session:
            paper = PaperTradingRepository(session)
            account_a = paper.create_account(USER_A, 1000)
            account_b = paper.create_account(USER_B, 1000)
            paper.create_position(account_a.id, "AAPL", 1, 10)
            paper.create_position(account_b.id, "AAPL", 1, 10)
            WatchlistRepository(session).add(USER_A, "AAPL")
            WatchlistRepository(session).add(USER_B, "AAPL")

        with self.assertRaises(IntegrityError):
            with session_scope(self.factory) as session:
                account = PaperTradingRepository(session).get_account_for_user(USER_A)
                session.add(PaperPosition(account_id=account.id, symbol="AAPL", shares=2, avg_cost=20))
        with self.assertRaises(IntegrityError):
            with session_scope(self.factory) as session:
                session.add(WatchlistItem(user_id=USER_A, symbol="AAPL"))

    def test_sqlite_foreign_keys_reject_invalid_owners(self):
        with self.engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql("PRAGMA foreign_keys").scalar(), 1)
        with self.assertRaises(IntegrityError):
            with session_scope(self.factory) as session:
                session.add(PaperPosition(account_id=9999, symbol="AAPL", shares=1, avg_cost=1))
        with self.assertRaises(IntegrityError):
            with session_scope(self.factory) as session:
                session.add(WatchlistItem(user_id=UUID("30000000-0000-4000-8000-000000000003"), symbol="AAPL"))

    def test_missing_preferences_are_empty_and_upsert_is_user_scoped(self):
        with session_scope(self.factory) as session:
            preferences = PreferencesRepository(session)
            self.assertEqual(preferences.get(USER_A), {})
            preferences.upsert(USER_A, {"limit": 10})
            preferences.upsert(USER_A, {"limit": 20})
            self.assertEqual(preferences.get(USER_A), {"limit": 20})
            self.assertEqual(preferences.get(USER_B), {})


if __name__ == "__main__":
    unittest.main()

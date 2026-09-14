import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker

from app.auth import CurrentUser
from app.config import REPOSITORY_ROOT
from app.bootstrap import DEFAULT_DEV_USER_ID
from app.db import create_database_engine, resolve_database_url, session_scope
from app.models.paper_trading import PaperAccount
from app.paper_trading import (
    PaperTradeRequest,
    buy,
    init_paper_trading_db,
    read_account,
    read_portfolio,
    read_positions,
    read_trades,
    sell,
)
from app.repositories.paper_trading import PaperTradingRepository


class PaperPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "paper.db"
        self.engine = create_database_engine(f"sqlite:///{self.database_path}")
        self.factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False
        )
        init_paper_trading_db(self.engine, self.factory)
        self.scope_patch = patch(
            "app.paper_trading.session_scope",
            side_effect=lambda: session_scope(self.factory),
        )
        self.scope_patch.start()
        self.current_user = CurrentUser(user_id=DEFAULT_DEV_USER_ID)

    def tearDown(self):
        self.scope_patch.stop()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_empty_database_initializes_expected_schema_and_account(self):
        self.assertEqual(
            set(inspect(self.engine).get_table_names()),
            {
                "app_users", "paper_accounts", "paper_positions", "paper_trades",
                "user_preferences", "watchlist_items",
            },
        )
        account = read_account(self.current_user)
        self.assertEqual(account["cash_balance"], 10_000.0)
        self.assertEqual(account["starting_cash"], 10_000.0)

    def test_relative_sqlite_url_is_stable_from_any_working_directory(self):
        resolved = resolve_database_url("sqlite:///backend/app/paper_trading.db")
        self.assertEqual(
            Path(resolved.database),
            REPOSITORY_ROOT / "backend" / "app" / "paper_trading.db",
        )

    def test_bootstrap_account_is_owned_by_development_user(self):
        with session_scope(self.factory) as session:
            account = PaperTradingRepository(session).get_account_for_user(
                DEFAULT_DEV_USER_ID
            )
            self.assertIsNotNone(account)
            self.assertEqual(account.user_id, DEFAULT_DEV_USER_ID)

    def test_buy_creates_and_averages_position_and_inserts_trades(self):
        first = buy(PaperTradeRequest(symbol=" aapl ", shares=10, price=100), self.current_user)
        second = buy(PaperTradeRequest(symbol="AAPL", shares=10, price=120), self.current_user)

        self.assertEqual(first["message"], "Paper buy executed")
        self.assertEqual(second["position"]["shares"], 20)
        self.assertEqual(second["position"]["avg_cost"], 110)
        self.assertEqual(second["account"]["cash_balance"], 7_800)
        self.assertEqual(len(read_positions(self.current_user)), 1)
        self.assertEqual(
            [trade["side"] for trade in read_trades(self.current_user)],
            ["BUY", "BUY"],
        )

    def test_sell_updates_then_closes_position_and_preserves_realized_pnl(self):
        buy(PaperTradeRequest(symbol="AAPL", shares=10, price=100), self.current_user)
        partial = sell(PaperTradeRequest(symbol="AAPL", shares=4, price=125), self.current_user)
        closed = sell(PaperTradeRequest(symbol="AAPL", shares=6, price=90), self.current_user)

        self.assertEqual(partial["position"]["shares"], 6)
        self.assertEqual(partial["trade"]["realized_pnl"], 100)
        self.assertIsNone(closed["position"])
        self.assertEqual(closed["trade"]["realized_pnl"], -60)
        self.assertEqual(read_positions(self.current_user), [])
        self.assertEqual(read_account(self.current_user)["cash_balance"], 10_040)

    def test_trade_history_preserves_timestamp_then_id_descending_order(self):
        with session_scope(self.factory) as session:
            repository = PaperTradingRepository(session)
            account = repository.get_account_for_user(DEFAULT_DEV_USER_ID)
            first = repository.create_trade(
                account_id=account.id, symbol="AAPL", side="BUY", shares=1, price=10,
                total_value=10, realized_pnl=0,
            )
            second = repository.create_trade(
                account_id=account.id, symbol="MSFT", side="BUY", shares=1, price=20,
                total_value=20, realized_pnl=0,
            )
            first.created_at = "2026-01-01 00:00:00"
            second.created_at = "2026-01-01 00:00:00"

        self.assertEqual(
            [trade["symbol"] for trade in read_trades(self.current_user)],
            ["MSFT", "AAPL"],
        )

    def test_portfolio_response_contract_is_preserved(self):
        buy(PaperTradeRequest(symbol="AAPL", shares=10, price=100), self.current_user)
        with patch(
            "app.paper_trading.get_position_market_prices",
            return_value=(125.0, 120.0),
        ):
            portfolio = read_portfolio(self.current_user)

        self.assertEqual(portfolio["cash"], 9_000)
        self.assertEqual(portfolio["account_equity"], 10_250)
        self.assertEqual(portfolio["total_pl"], 250)
        self.assertEqual(portfolio["positions_count"], 1)
        self.assertEqual(portfolio["positions"][0]["symbol"], "AAPL")

    def test_buy_rolls_back_every_change_when_trade_insert_fails(self):
        with patch.object(
            PaperTradingRepository,
            "create_trade",
            side_effect=RuntimeError("forced failure"),
        ):
            with self.assertRaises(RuntimeError):
                buy(
                    PaperTradeRequest(symbol="AAPL", shares=10, price=100),
                    self.current_user,
                )

        self.assertEqual(read_account(self.current_user)["cash_balance"], 10_000)
        self.assertEqual(read_positions(self.current_user), [])
        self.assertEqual(read_trades(self.current_user), [])

    def test_model_matches_existing_float_and_text_contract(self):
        columns = PaperAccount.__table__.columns
        self.assertEqual(str(columns.cash_balance.type), "FLOAT")
        self.assertEqual(str(columns.created_at.type), "TEXT")


if __name__ == "__main__":
    unittest.main()

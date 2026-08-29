import asyncio
import json
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWK
from jwt.exceptions import PyJWKClientError
from sqlalchemy.orm import sessionmaker

from app.auth import SupabaseJWTVerifier, get_auth_session
from app.bootstrap import DEFAULT_DEV_USER_ID
from app.db import create_database_engine, create_schema, session_scope
from app.main import app
from app.repositories.paper_trading import PaperTradingRepository
from app.repositories.preferences import PreferencesRepository
from app.repositories.users import UserRepository
from app.repositories.watchlist import WatchlistRepository


ISSUER = "https://project.supabase.co/auth/v1"
AUDIENCE = "authenticated"
USER_A = UUID("10000000-0000-4000-8000-000000000001")
USER_B = UUID("20000000-0000-4000-8000-000000000002")
USER_C = UUID("30000000-0000-4000-8000-000000000003")
DISABLED_USER = UUID("40000000-0000-4000-8000-000000000004")
UNKNOWN_USER = UUID("50000000-0000-4000-8000-000000000005")


class StaticJwksClient:
    def __init__(self, key):
        self.key = key

    def get_signing_key_from_jwt(self, token):
        if jwt.get_unverified_header(token).get("kid") != "api-test-key":
            raise PyJWKClientError("Unknown signing key")
        return PyJWK.from_dict(self.key)


async def call_asgi(method, path, *, token=None, json_body=None, query=""):
    body = b"" if json_body is None else json.dumps(json_body).encode("utf-8")
    headers = [(b"content-type", b"application/json")]
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode("ascii")))
    messages = []
    received = False

    async def receive():
        nonlocal received
        if not received:
            received = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": query.encode("ascii"),
            "root_path": "",
            "headers": headers,
            "client": ("test", 1234),
            "server": ("test", 80),
        },
        receive,
        send,
    )
    start = next(item for item in messages if item["type"] == "http.response.start")
    response_body = b"".join(
        item.get("body", b"")
        for item in messages
        if item["type"] == "http.response.body"
    )
    return start["status"], dict(start["headers"]), (
        json.loads(response_body) if response_body else None
    )


class AuthenticatedApiIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(
            cls.private_key.public_key(), as_dict=True
        )
        public_jwk.update({"kid": "api-test-key", "alg": "RS256", "use": "sig"})
        cls.verifier = SupabaseJWTVerifier(
            ISSUER,
            AUDIENCE,
            "https://unused.test/jwks.json",
            jwks_client=StaticJwksClient(public_jwk),
        )

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "authenticated-api.db"
        self.engine = create_database_engine(f"sqlite:///{database_path}")
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        create_schema(self.engine)
        with session_scope(self.factory) as session:
            users = UserRepository(session)
            users.create(DEFAULT_DEV_USER_ID, email="bootstrap@example.test")
            users.create(USER_A, email="a@example.test")
            users.create(USER_B, email="b@example.test")
            users.create(USER_C, email="c@example.test")
            users.create(DISABLED_USER, email="disabled@example.test", beta_status="disabled")
            paper = PaperTradingRepository(session)
            bootstrap = paper.create_account(DEFAULT_DEV_USER_ID, 1111)
            account_a = paper.create_account(USER_A, 5000)
            account_b = paper.create_account(USER_B, 7000)
            paper.create_position(bootstrap.id, "BOOT", 1, 1)
            paper.create_position(account_a.id, "AAPL", 10, 100)
            paper.create_position(account_b.id, "AAPL", 20, 200)
            paper.create_trade(account_id=account_a.id, symbol="AAPL", side="BUY", shares=10, price=100, total_value=1000, realized_pnl=0)
            paper.create_trade(account_id=account_b.id, symbol="AAPL", side="BUY", shares=20, price=200, total_value=4000, realized_pnl=0)
            watchlist = WatchlistRepository(session)
            for symbol in ("AAPL", "MSFT"):
                watchlist.add(USER_A, symbol)
            for symbol in ("AAPL", "NVDA"):
                watchlist.add(USER_B, symbol)
            preferences = PreferencesRepository(session)
            preferences.upsert(USER_A, {"universe": "sp500"})
            preferences.upsert(USER_B, {"universe": "nasdaq"})

        def auth_session_override():
            session = self.factory()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_auth_session] = auth_session_override
        self.stack = ExitStack()
        self.stack.enter_context(
            patch("app.auth.get_token_verifier", return_value=self.verifier)
        )
        self.stack.enter_context(
            patch("app.paper_trading.session_scope", side_effect=lambda: session_scope(self.factory))
        )
        self.stack.enter_context(
            patch("app.user_data.session_scope", side_effect=lambda: session_scope(self.factory))
        )

    def tearDown(self):
        self.stack.close()
        app.dependency_overrides.clear()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def token(self, user_id):
        now = datetime.now(timezone.utc)
        return jwt.encode(
            {"iss": ISSUER, "aud": AUDIENCE, "sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=5)},
            self.private_key,
            algorithm="RS256",
            headers={"kid": "api-test-key"},
        )

    def request(self, method, path, *, user_id=None, json_body=None, query=""):
        token = self.token(user_id) if user_id is not None else None
        return asyncio.run(call_asgi(method, path, token=token, json_body=json_body, query=query))

    def test_health_is_public_and_auth_me_is_authenticated(self):
        self.assertEqual(self.request("GET", "/health")[0:3:2], (200, {"status": "ok"}))
        status, _, payload = self.request("GET", "/auth/me", user_id=USER_A)
        self.assertEqual(status, 200)
        self.assertEqual(payload["user_id"], str(USER_A))

    def test_anonymous_product_routes_return_401_before_work_executes(self):
        routes = [
            ("GET", "/paper/account", None), ("GET", "/paper/positions", None),
            ("GET", "/paper/trades", None), ("GET", "/paper/portfolio", None),
            ("POST", "/paper/buy", {"symbol": "AAPL", "shares": 1, "price": 1}),
            ("POST", "/paper/sell", {"symbol": "AAPL", "shares": 1, "price": 1}),
            ("GET", "/watchlist", None), ("GET", "/preferences/scanner", None),
            ("GET", "/scan", None), ("GET", "/scan/stream", None),
            ("GET", "/analyze/AAPL", None), ("GET", "/financial-analysis/AAPL", None),
            ("GET", "/valuation-analysis/AAPL", None), ("GET", "/validate/AAPL", None),
            ("POST", "/analyze/batch", {"symbols": ["AAPL"]}),
        ]
        with patch("app.main.analyze_ticker") as analyzer, patch("app.main.scan_market") as scanner:
            for method, path, body in routes:
                with self.subTest(path=path):
                    status, headers, _ = self.request(method, path, json_body=body)
                    self.assertEqual(status, 401)
                    self.assertEqual(headers[b"www-authenticate"], b"Bearer")
            analyzer.assert_not_called()
            scanner.assert_not_called()

    def test_unknown_and_disabled_users_are_forbidden_before_scan(self):
        with patch("app.main.scan_market") as scanner:
            for user_id in (UNKNOWN_USER, DISABLED_USER):
                with self.subTest(user_id=user_id):
                    self.assertEqual(self.request("GET", "/scan", user_id=user_id)[0], 403)
            scanner.assert_not_called()

    def test_active_user_reaches_shared_route_and_query_token_is_not_accepted(self):
        with patch("app.main.get_price_history") as price_history:
            self.assertEqual(
                self.request("GET", "/validate/AAPL", user_id=USER_A)[0], 200
            )
            price_history.assert_called_once()
        self.assertEqual(
            self.request(
                "GET", "/scan/stream", query="access_token=not-accepted"
            )[0],
            401,
        )

    def test_paper_reads_use_authenticated_account_not_bootstrap_or_other_user(self):
        status, _, account = self.request("GET", "/paper/account", user_id=USER_A)
        self.assertEqual((status, account["cash_balance"]), (200, 5000))
        _, _, positions = self.request("GET", "/paper/positions", user_id=USER_A)
        self.assertEqual([(row["symbol"], row["shares"]) for row in positions], [("AAPL", 10)])
        _, _, trades = self.request("GET", "/paper/trades", user_id=USER_A)
        self.assertEqual([(row["symbol"], row["total_value"]) for row in trades], [("AAPL", 1000)])
        with patch("app.paper_trading.get_position_market_prices", return_value=(125.0, 120.0)):
            _, _, portfolio = self.request("GET", "/paper/portfolio", user_id=USER_A)
        self.assertEqual(portfolio["cash_balance"], 5000)
        self.assertEqual(portfolio["positions"][0]["shares"], 10)

    def test_cross_user_sell_and_buy_mutate_only_authenticated_account(self):
        self.request("POST", "/paper/sell", user_id=USER_A, json_body={"symbol": "aapl", "shares": 2, "price": 150})
        with session_scope(self.factory) as session:
            paper = PaperTradingRepository(session)
            account_a = paper.get_account_for_user(USER_A)
            account_b = paper.get_account_for_user(USER_B)
            self.assertEqual((account_a.cash_balance, paper.get_position(account_a.id, "AAPL").shares), (5300, 8))
            self.assertEqual((account_b.cash_balance, paper.get_position(account_b.id, "AAPL").shares), (7000, 20))

        self.request("POST", "/paper/buy", user_id=USER_B, json_body={"symbol": "aapl", "shares": 1, "price": 100})
        with session_scope(self.factory) as session:
            paper = PaperTradingRepository(session)
            account_a = paper.get_account_for_user(USER_A)
            account_b = paper.get_account_for_user(USER_B)
            self.assertEqual((account_a.cash_balance, paper.get_position(account_a.id, "AAPL").shares), (5300, 8))
            self.assertEqual((account_b.cash_balance, paper.get_position(account_b.id, "AAPL").shares), (6900, 21))

    def test_missing_account_is_created_once_for_active_user(self):
        first = self.request("GET", "/paper/account", user_id=USER_C)[2]
        second = self.request("GET", "/paper/account", user_id=USER_C)[2]
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["cash_balance"], 10000)

    def test_watchlist_reads_and_deletes_are_user_scoped_and_add_is_idempotent(self):
        self.assertEqual(self.request("GET", "/watchlist", user_id=USER_A)[2], {"symbols": ["AAPL", "MSFT"]})
        self.request("DELETE", "/watchlist/aapl", user_id=USER_A)
        self.request("POST", "/watchlist", user_id=USER_B, json_body={"symbol": " aapl "})
        self.assertEqual(self.request("GET", "/watchlist", user_id=USER_A)[2], {"symbols": ["MSFT"]})
        self.assertEqual(self.request("GET", "/watchlist", user_id=USER_B)[2], {"symbols": ["AAPL", "NVDA"]})

    def test_preferences_are_user_scoped_and_payload_is_bounded(self):
        self.assertEqual(self.request("GET", "/preferences/scanner", user_id=USER_A)[2], {"universe": "sp500"})
        self.request("PUT", "/preferences/scanner", user_id=USER_A, json_body={"universe": "dow", "limit": 5})
        self.assertEqual(self.request("GET", "/preferences/scanner", user_id=USER_A)[2], {"universe": "dow", "limit": 5})
        self.assertEqual(self.request("GET", "/preferences/scanner", user_id=USER_B)[2], {"universe": "nasdaq"})
        self.assertEqual(self.request("GET", "/preferences/scanner", user_id=USER_C)[2], {})
        self.assertEqual(self.request("PUT", "/preferences/scanner", user_id=USER_A, json_body={"value": "x" * 17000})[0], 413)
        self.assertEqual(
            self.request(
                "PUT", "/preferences/scanner", user_id=USER_A, json_body=[]
            )[0],
            422,
        )


if __name__ == "__main__":
    unittest.main()

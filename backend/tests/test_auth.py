import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jwt import PyJWK
from jwt.exceptions import PyJWKClientError
from sqlalchemy.orm import sessionmaker

from app.auth import (
    CurrentUser,
    SupabaseJWTVerifier,
    get_current_user,
    get_token_verifier,
)
from app.db import create_database_engine, create_schema, session_scope
from app.main import auth_me
from app.repositories.users import UserRepository


ISSUER = "https://project.supabase.co/auth/v1"
AUDIENCE = "authenticated"
ACTIVE_USER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
DISABLED_USER_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
UNKNOWN_USER_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


class StaticJwksClient:
    def __init__(self, keys):
        self.keys = keys

    def get_signing_key_from_jwt(self, token):
        kid = jwt.get_unverified_header(token).get("kid")
        if kid not in self.keys:
            raise PyJWKClientError("Unknown signing key")
        return PyJWK.from_dict(self.keys[kid])


class AuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(
            cls.private_key.public_key(), as_dict=True
        )
        public_jwk.update({"kid": "test-key", "alg": "RS256", "use": "sig"})
        cls.verifier = SupabaseJWTVerifier(
            ISSUER,
            AUDIENCE,
            "https://unused.test/jwks.json",
            jwks_client=StaticJwksClient({"test-key": public_jwk}),
        )

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "auth.db"
        self.engine = create_database_engine(f"sqlite:///{database_path}")
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        create_schema(self.engine)
        with session_scope(self.factory) as session:
            users = UserRepository(session)
            users.create(ACTIVE_USER_ID, email="active@example.test")
            users.create(
                DISABLED_USER_ID,
                email="disabled@example.test",
                beta_status="disabled",
            )

    def tearDown(self):
        self.engine.dispose()
        self.temp_dir.cleanup()

    def token(self, subject=ACTIVE_USER_ID, **overrides):
        now = datetime.now(timezone.utc)
        claims = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": str(subject),
            "email": "jwt@example.test",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        }
        claims.update(overrides)
        return jwt.encode(
            claims,
            self.private_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

    @staticmethod
    def credentials(token):
        return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    def assert_auth_error(self, token):
        with self.assertRaises(HTTPException) as raised:
            self.verifier.verify(token)
        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(raised.exception.headers, {"WWW-Authenticate": "Bearer"})

    def test_valid_token_is_cryptographically_verified(self):
        claims = self.verifier.verify(self.token())
        self.assertEqual(claims["sub"], str(ACTIVE_USER_ID))

    def test_invalid_signature_is_rejected(self):
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = jwt.encode(
            jwt.decode(self.token(), options={"verify_signature": False}),
            other_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )
        self.assert_auth_error(token)

    def test_malformed_and_expired_tokens_are_rejected(self):
        self.assert_auth_error("not-a-jwt")
        self.assert_auth_error(
            self.token(exp=datetime.now(timezone.utc) - timedelta(seconds=1))
        )

    def test_wrong_issuer_and_audience_are_rejected(self):
        self.assert_auth_error(self.token(iss="https://wrong.test/auth/v1"))
        self.assert_auth_error(self.token(aud="wrong"))

    def test_missing_or_invalid_subject_is_rejected(self):
        claims = jwt.decode(self.token(), options={"verify_signature": False})
        del claims["sub"]
        missing = jwt.encode(
            claims, self.private_key, algorithm="RS256", headers={"kid": "test-key"}
        )
        self.assert_auth_error(missing)

        with session_scope(self.factory) as session, patch(
            "app.auth.get_token_verifier", return_value=self.verifier
        ):
            with self.assertRaises(HTTPException) as raised:
                get_current_user(
                    self.credentials(self.token(subject="not-a-uuid")), session
                )
        self.assertEqual(raised.exception.status_code, 401)

    def test_unknown_kid_and_disallowed_algorithm_are_rejected(self):
        unknown_kid = jwt.encode(
            jwt.decode(self.token(), options={"verify_signature": False}),
            self.private_key,
            algorithm="RS256",
            headers={"kid": "unknown-key"},
        )
        self.assert_auth_error(unknown_kid)
        hs_token = jwt.encode(
            jwt.decode(self.token(), options={"verify_signature": False}),
            "test-secret-not-used-by-the-server",
            algorithm="HS256",
            headers={"kid": "test-key"},
        )
        self.assert_auth_error(hs_token)

    def test_missing_token_returns_401(self):
        with session_scope(self.factory) as session:
            with self.assertRaises(HTTPException) as raised:
                get_current_user(None, session)
        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(raised.exception.headers, {"WWW-Authenticate": "Bearer"})

    def test_unknown_and_disabled_users_return_403(self):
        for user_id in (UNKNOWN_USER_ID, DISABLED_USER_ID):
            with (
                self.subTest(user_id=user_id),
                session_scope(self.factory) as session,
                patch("app.auth.get_token_verifier", return_value=self.verifier),
            ):
                with self.assertRaises(HTTPException) as raised:
                    get_current_user(self.credentials(self.token(user_id)), session)
                self.assertEqual(raised.exception.status_code, 403)

    def test_active_user_returns_current_user_and_auth_me_payload(self):
        with session_scope(self.factory) as session, patch(
            "app.auth.get_token_verifier", return_value=self.verifier
        ):
            current_user = get_current_user(
                self.credentials(self.token(ACTIVE_USER_ID)), session
            )
        self.assertEqual(
            current_user,
            CurrentUser(user_id=ACTIVE_USER_ID, email="jwt@example.test"),
        )
        self.assertEqual(
            auth_me(current_user),
            {"user_id": str(ACTIVE_USER_ID), "email": "jwt@example.test"},
        )

    def test_unconfigured_auth_returns_sanitized_503(self):
        get_token_verifier.cache_clear()
        with patch("app.auth.settings", SimpleNamespace(auth_configured=False)):
            with self.assertRaises(HTTPException) as raised:
                get_token_verifier()
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.detail, "Authentication is not configured")
        get_token_verifier.cache_clear()


if __name__ == "__main__":
    unittest.main()

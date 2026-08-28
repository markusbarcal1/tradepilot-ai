import os
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.config import DEFAULT_CORS_ORIGINS, Settings


CONFIG_KEYS = {
    "ENVIRONMENT",
    "DATABASE_URL",
    "CORS_ORIGINS",
    "SCANNER_MAX_WORKERS",
    "LOG_LEVEL",
    "SUPABASE_AUTH_ISSUER",
    "SUPABASE_AUTH_AUDIENCE",
    "SUPABASE_JWKS_URL",
}


class SettingsTests(unittest.TestCase):
    def build_settings(self, **environment):
        clean_environment = {
            key: value for key, value in os.environ.items() if key not in CONFIG_KEYS
        }
        clean_environment.update(environment)
        with patch.dict(os.environ, clean_environment, clear=True):
            return Settings(_env_file=None)

    def test_development_defaults_do_not_require_auth_configuration(self):
        configured = self.build_settings()

        self.assertEqual(configured.environment, "development")
        self.assertEqual(configured.database_url, "sqlite:///backend/app/paper_trading.db")
        self.assertEqual(configured.cors_origins, DEFAULT_CORS_ORIGINS)
        self.assertEqual(configured.scanner_max_workers, 8)
        self.assertEqual(configured.log_level, "INFO")
        self.assertIsNone(configured.supabase_auth_issuer)
        self.assertIsNone(configured.supabase_auth_audience)
        self.assertIsNone(configured.supabase_jwks_url)

    def test_environment_overrides_defaults(self):
        configured = self.build_settings(
            ENVIRONMENT="test",
            DATABASE_URL="postgresql://localhost/tradepilot",
            SCANNER_MAX_WORKERS="4",
            LOG_LEVEL="debug",
            SUPABASE_AUTH_ISSUER="https://example.supabase.co/auth/v1",
        )

        self.assertEqual(configured.environment, "test")
        self.assertEqual(configured.database_url, "postgresql://localhost/tradepilot")
        self.assertEqual(configured.scanner_max_workers, 4)
        self.assertEqual(configured.log_level, "DEBUG")
        self.assertEqual(
            configured.supabase_auth_issuer,
            "https://example.supabase.co/auth/v1",
        )

    def test_invalid_environment_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.build_settings(ENVIRONMENT="staging")

    def test_invalid_scanner_worker_values_are_rejected(self):
        for value in ("0", "-1", "17"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.build_settings(SCANNER_MAX_WORKERS=value)

    def test_cors_origins_accept_comma_separated_values(self):
        configured = self.build_settings(
            CORS_ORIGINS="https://app.example.com, https://admin.example.com/"
        )

        self.assertEqual(
            configured.cors_origins,
            ["https://app.example.com", "https://admin.example.com"],
        )

    def test_cors_origins_accept_json_array(self):
        configured = self.build_settings(
            CORS_ORIGINS='["https://app.example.com", "https://admin.example.com"]'
        )

        self.assertEqual(
            configured.cors_origins,
            ["https://app.example.com", "https://admin.example.com"],
        )

    def test_cors_wildcard_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.build_settings(CORS_ORIGINS="*")


if __name__ == "__main__":
    unittest.main()

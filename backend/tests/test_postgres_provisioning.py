"""Provisioning uses only random loopback databases from the guarded test fixture."""
from unittest.mock import patch

import pytest
from alembic import command

from app.bootstrap import DEFAULT_DEV_USER_ID
from app.cli import provision_beta_user as provisioning
from app.cli.migrate_sqlite_to_postgres import snapshot
from app.db import create_database_engine
from tests import test_authenticated_api_isolation as api_tests
from tests.test_postgres_migration import pg_url, alembic_config, disposable_postgres, A, B


def args(url, uid=A, email="a@example.test", *flags):
    return provisioning.build_parser().parse_args([
        "--database-url", url, "--user-id", str(uid), "--email", email, *flags])


def data(url):
    engine = create_database_engine(url)
    try:
        with engine.connect() as connection:
            return snapshot(connection)
    finally:
        engine.dispose()


def test_normal_users_idempotency_dry_run_and_independence(pg_url):
    command.upgrade(alembic_config(pg_url), "head")
    before = data(pg_url)
    assert provisioning.run(args(pg_url, A, "a@example.test", "--dry-run"))["result"] == "would provision"
    assert data(pg_url) == before
    first = provisioning.run(args(pg_url))
    second = provisioning.run(args(pg_url, B, "b@example.test"))
    assert first["account_id"] != second["account_id"]
    before = data(pg_url)
    assert provisioning.run(args(pg_url))["result"] == "already provisioned"
    assert data(pg_url) == before
    assert len(before["app_users"]) == len(before["paper_accounts"]) == 2
    assert DEFAULT_DEV_USER_ID not in {u["user_id"] for u in before["app_users"]}
    assert not before["paper_positions"] and not before["paper_trades"]
    assert all(a["starting_cash"] == a["cash_balance"] == 10000 for a in before["paper_accounts"])


@pytest.mark.parametrize("uid,email", [(B, "a@example.test"), (A, "changed@example.test")])
@pytest.mark.parametrize("mode", [(), ("--dry-run",)])
def test_identity_conflicts_leave_rows_unchanged(pg_url, uid, email, mode):
    command.upgrade(alembic_config(pg_url), "head")
    provisioning.run(args(pg_url))
    before = data(pg_url)
    with pytest.raises(provisioning.ProvisioningError):
        provisioning.run(args(pg_url, uid, email, *mode))
    assert data(pg_url) == before


def test_account_failure_rolls_back_user_and_redacts_error(pg_url):
    command.upgrade(alembic_config(pg_url), "head")
    before = data(pg_url)
    with patch.object(provisioning.PaperTradingRepository, "create_account",
                      side_effect=RuntimeError("secret-password")):
        with pytest.raises(provisioning.ProvisioningError) as error:
            provisioning.run(args(pg_url))
    assert "secret-password" not in str(error.value)
    assert data(pg_url) == before


@pytest.mark.parametrize("flag", ["--adopt-legacy-account", "--cleanup-bootstrap"])
def test_legacy_operations_rejected_without_connecting(flag):
    with patch.object(provisioning, "create_database_engine") as engine:
        with pytest.raises(provisioning.ProvisioningError, match="SQLite-only"):
            provisioning.run(args("postgresql+psycopg://unused/db", A, "a@example.test", flag))
        engine.assert_not_called()


def test_bootstrap_and_unmigrated_database_rejected(pg_url):
    with pytest.raises(provisioning.ProvisioningError, match="bootstrap UUID"):
        provisioning.run(args(pg_url, DEFAULT_DEV_USER_ID))
    with pytest.raises(provisioning.ProvisioningError, match="Alembic head"):
        provisioning.run(args(pg_url))
    command.upgrade(alembic_config(pg_url), "head")
    assert not data(pg_url)["app_users"]


# Exercise the existing HTTP/JWT boundary tests against Alembic-created PostgreSQL.
# Tokens and JWKS are synthetic; these do not certify live Supabase sessions.
class TestPostgresAuthenticatedApiIsolation(api_tests.AuthenticatedApiIsolationTests):
    def setUp(self):
        self.pg_context = disposable_postgres()
        url = self.pg_context.__enter__()
        self.addCleanup(self.pg_context.__exit__, None, None, None)
        command.upgrade(alembic_config(url), "head")
        with patch.object(api_tests, "create_database_engine", side_effect=lambda _: create_database_engine(url)), \
                patch.object(api_tests, "create_schema"):
            super().setUp()

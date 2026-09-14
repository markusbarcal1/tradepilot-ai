# Phase 7B implementation and validation

Validated 2026-09-11. Scope was narrowed by the operator to code/configuration and
disposable local validation: no approved managed rehearsal target exists. Real
snapshot, managed rehearsal, cutover and live Supabase acceptance remain unexecuted.

## Changes

| File | Result |
| --- | --- |
| `backend/app/config.py` | Bounded PostgreSQL pool settings: 5 connections, overflow 2, timeout 30s, recycle 1800s |
| `backend/app/db.py` | PostgreSQL pre-ping, conservative pool settings, 10s connect timeout, hidden SQL parameters; existing UTC hook retained |
| `.env.example` | Server-only migration URL, TLS/CA and pool configuration guidance |
| `backend/app/cli/provision_beta_user.py` | Shared normal provisioning and identity validation; PostgreSQL schema preflight, atomic user/account transaction, read-only dry-run, safe error messages, bootstrap/legacy rejection |
| `backend/app/cli/migrate_sqlite_to_postgres.py` | Source/target types, explicit integrity report, actual next-sequence positions in confirm and verify-only |
| `backend/tests/test_config.py` | Invalid pool setting rejection |
| `backend/tests/test_postgres_migration.py` | Verification report assertions alongside existing migration/sequence tests |
| `backend/tests/test_postgres_provisioning.py` | PostgreSQL provisioning, identity conflicts, idempotency, rollback, bootstrap refusal, and inherited authenticated API isolation tests |
| `docs/phase7b-cutover.md` | Exact PowerShell rehearsal/cutover commands, provider prerequisites, live acceptance, rollback checkpoints |
| `docs/private-beta-setup.md` | Current onboarding guidance and runbook link |
| `docs/phase7b-validation.md` | This record |

No Alembic migration was necessary; head remains `20260902_03`. SQLite normal and
legacy behavior is preserved. PostgreSQL normal onboarding does not migrate schemas
or call bootstrap creation. It requires exact current schema and rejects identity
conflicts, bootstrap UUID/presence, adoption and cleanup. Concurrent duplicate
provision attempts are protected by database constraints; an operator can safely
rerun after inspecting an error. Sequence gaps on rolled-back provisioning are
normal PostgreSQL behavior; no duplicate account/user rows remain.

## Executed validation

The initial focused run passed **69 tests and 8 subtests** covering SQLite beta
provisioning, PostgreSQL provisioning, migration dry-run/copy/verify-only, sequence
continuation/regression, rollback injection, and read-only source preservation.

The full backend suite includes all SQLite cases, PostgreSQL integration and
provisioning, and 10 authenticated HTTP/API isolation cases against PostgreSQL.
These HTTP cases use real signature verification with synthetic JWT/JWKS fixtures;
they cover auth/me, owned account/positions/trades/portfolio, watchlists, scanner
preferences, theme, cross-user mutations and anonymous/disabled access. They do
not use or certify real Supabase sessions. Synthetic test data includes a bootstrap
row to prove routes ignore it; this is separate from the provisioning tests, which
verify normal PostgreSQL onboarding never creates it.

Final full-suite result: **250 passed, 168 subtests passed, no skips, 2 warnings in 55.97s**.
The warnings are existing FastAPI `on_event` deprecations.

Command from `backend`:

```powershell
$env:TRADEPILOT_TEST_DATABASE_URL='postgresql+psycopg://tradepilot_test@127.0.0.1:55439/tradepilot_test'
& '.\venv\Scripts\python.exe' -m pytest -q
```

Only a fresh local PostgreSQL **17.11** temporary cluster was used, bound to
127.0.0.1:55439. Tests enforce a loopback `tradepilot_test` admin database and use
random disposable child databases. No managed database or production credentials
were created or used. Docker/Compose launch was not tested; existing portable
PostgreSQL binaries were used. The temporary cluster was stopped after validation.

The full suite rehearses populated synthetic SQLite copies into disposable
PostgreSQL, checks every copied column/relationship, backs up sources, confirms
source hashes, and tests rollback including transactional sequence RESTART.
No real two-user dataset counts were queried or certified in this phase.

`git diff --check`: passed.

## Real database safety

The real SQLite database was not opened through application/SQLite connections,
backed up, migrated, or written by this work. Only its file hash was read. SHA-256
before and after matched:

```text
308A5326E33497310D44068FB0B5063F46732A046841DA640A2CF5C063F301AD
```

The real `.env`/DATABASE_URL was not edited, Supabase Auth users were not changed,
no services were deployed, and no Git commit was made. No frontend files changed.
FastAPI remains the application data boundary and authenticated UUID ownership is
unchanged. Existing startup does not perform PostgreSQL create_all/migrations or
bootstrap creation. Alembic remains the schema authority.

## Remaining operator work

- Select and approve an empty managed rehearsal database and separate final target.
- Verify provider TLS, network access, role grants, pool budget, backup/PITR and restore.
- Stop writers and create a fresh read-only-source SQLite backup using the runbook.
- Review actual two-user counts/ownership and rehearse dry-run, confirm and verify-only.
- Complete real Supabase A/B application acceptance and record cross-user isolation.
- Review/commit changes, then authorize final migration and URL switch separately.

The [exact runbook](phase7b-cutover.md) includes all commands and rollback cases.
After PostgreSQL-only writes, freeze and reconcile; never blindly revert to SQLite.

Recommended commit: `feat(beta): prepare managed PostgreSQL cutover`.

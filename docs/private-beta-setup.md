# TradePilot AI private-beta setup

TradePilot uses Supabase Auth for identity and FastAPI plus `app_users` as the
application allowlist. The normal backend needs only JWT verification settings;
it does not need a Supabase secret or service-role key.

## Configure Supabase Auth

In the hosted Supabase Dashboard:

1. Open **Authentication > Settings** and turn **Allow new users to sign up**
   off. Existing and administratively invited users can still sign in.
2. On the same general configuration page, turn **Allow anonymous sign-ins**
   off.
3. Open **Authentication > Sign In / Providers > Email** and leave the Email
   provider enabled. Configure email confirmation according to the invitation
   flow; do not add a public signup path to TradePilot.
4. Open **Authentication > URL Configuration**. For local development set the
   Site URL to `http://localhost:5173` and allow both
   `http://localhost:5173/**` and `http://127.0.0.1:5173/**` as Redirect URLs.
   Before deployment, replace the Site URL with the real HTTPS origin and add
   exact production redirect paths. Do not invent a production domain.

Dashboard labels can evolve. The authoritative Supabase references are:

- https://supabase.com/docs/guides/auth/general-configuration
- https://supabase.com/docs/guides/auth/users#inviting-users
- https://supabase.com/docs/guides/auth/redirect-urls
- https://supabase.com/docs/guides/auth/passwords

## Environment

Create ignored local environment files; never commit real values. The backend
loads its environment from the repository-root `.env` file
(`tradepilot-ai/.env`), while the frontend environment remains
`tradepilot-ai/frontend/.env`.

Frontend:

```text
VITE_SUPABASE_URL=https://PROJECT_REF.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
```

Backend:

```text
SUPABASE_AUTH_ISSUER=https://PROJECT_REF.supabase.co/auth/v1
SUPABASE_AUTH_AUDIENCE=authenticated
SUPABASE_JWKS_URL=https://PROJECT_REF.supabase.co/auth/v1/.well-known/jwks.json
```

Confirm these URLs against the project's current Auth/JWT settings. TradePilot
does not use an Auth Admin secret and cannot independently confirm that an
operator-supplied UUID exists in Supabase.

## Provision a normal beta tester

1. Approve the tester.
2. In **Authentication > Users**, choose **Add user > Send invitation**.
3. Copy the created user's UUID directly from that page.
4. From `backend`, run a dry run and then provision the allowlist row:

```powershell
& '.\venv\Scripts\python.exe' -m app.cli.provision_beta_user `
  --user-id '<SUPABASE-UUID>' --email '<EMAIL>' --dry-run
& '.\venv\Scripts\python.exe' -m app.cli.provision_beta_user `
  --user-id '<SUPABASE-UUID>' --email '<EMAIL>'
```

5. Provisioning creates one active `app_users` row and exactly one fresh
   $10,000 paper account with no positions or trades. It does not copy another
   user's watchlist or preferences. Re-running the command is a safe no-op for
   both records.
6. The user completes the invitation, signs in, and `/auth/me` authorizes the
   active `app_users` row.

The Dashboard's manual **Create new user** option with an operator-chosen
password is acceptable for the operator's first account. Invitations are
preferred for outside testers.

## Adopt the historical account for the first user

Do this before the first user accesses any paper endpoint. Otherwise normal
runtime behavior can create a new empty account for that UUID.

1. Stop Uvicorn and any reloaders using the SQLite file.
2. Create the Auth user in the Supabase Dashboard and copy its UUID.
3. Run the non-mutating inspection:

```powershell
& '.\venv\Scripts\python.exe' -m app.cli.provision_beta_user `
  --user-id '<SUPABASE-UUID>' --email '<EMAIL>' `
  --adopt-legacy-account --dry-run
```

4. Review the detected state, file hash, account/position/trade counts, legacy
   account ID, and planned operations.
5. Run the guarded operation:

```powershell
& '.\venv\Scripts\python.exe' -m app.cli.provision_beta_user `
  --user-id '<SUPABASE-UUID>' --email '<EMAIL>' `
  --adopt-legacy-account --confirm
```

For the verified unstamped legacy schema, the command creates a timestamped
backup under ignored `backend/backups/`, stamps `20260828_01`, upgrades to head
`20260902_03`, creates the active user, and changes the existing
`paper_accounts.user_id` from the bootstrap UUID to the supplied UUID. It does
not copy the account, positions, or trades. Provisioning plus reassignment and
bootstrap-row cleanup are one transaction; Alembic is a preceding, separate
boundary because SQLite DDL cannot be treated as part of that ownership
transaction.

The report labels its pre-operation snapshot separately from the current
target/bootstrap ownership inspection. After a completed adoption, a repeat
dry run says `adoption already complete`, reports one target-owned account and
zero bootstrap-owned accounts, and counts positions/trades through the target
account. Repeating `--confirm` reports `nothing to do` and does not reassign or
duplicate anything.

Each durable boundary is reported independently: backup, stamp, upgrade,
schema verification, user provisioning, account creation or reassignment,
bootstrap cleanup, foreign-key validation, portfolio verification, and
Alembic metadata check. If the command stops after migration but before the
ownership transaction, leave the database in place, inspect the printed step
statuses and current ownership, and rerun the same command. The rerun detects
the current revision and safely continues. Never restore a backup blindly:
first verify the current Alembic revision, ownership, account ID, positions,
trades, and foreign-key status, because earlier durable steps may already have
succeeded.

SQLite schema inspection can spell model `Float` columns as `REAL` and can
report `INTEGER PRIMARY KEY` columns as nullable even though primary-key
semantics make them non-null. Alembic comparison normalizes only those two
SQLite reflection artifacts. Other type, nullability, column, constraint, and
table differences remain visible to `alembic check`.

The command aborts on mixed schema, identity collision, missing or multiple
bootstrap accounts, an existing target account, or foreign-key violations. A
successful adoption removes the now-unreferenced bootstrap database row; source
constants remain for migrations and tests.

## Invitation compatibility

The frontend detects a valid Supabase invitation session and presents only the
minimal initial-password form. It calls the authenticated Supabase `updateUser`
operation, then performs the normal `/auth/me` beta-allowlist check. It cannot
create a user and exposes no public signup, general password-reset, or
browser-side admin flow. Verify the hosted invitation template and redirect
behavior before inviting an outside tester.

## First-user certification checklist

1. Configure invite-only Auth and URL settings.
2. Create the first Auth user and copy the UUID.
3. Configure ignored frontend/backend environment files.
4. Stop backend reloaders.
5. Run adoption dry-run, then guarded adoption.
6. Confirm revision `20260902_03`, zero FK violations, unchanged account ID,
   balance, starting cash, four positions, and 31 trades.
7. Start FastAPI and React; sign in and confirm `/auth/me` returns 200.
8. Confirm the historical dashboard, watchlist, preferences, analysis, and
   authenticated scanner stream.
9. Refresh to confirm session restoration; log out to confirm state clearing;
   sign in again to confirm the same account returns.

The application never migrates or provisions users automatically at startup.
# Explicit cleanup of an unused bootstrap account

Startup creates the compatibility bootstrap user/account only when a local SQLite database
has no tables. Empty PostgreSQL databases require Alembic. Existing databases are left unchanged, including any stale bootstrap
account. Startup performs no migration or cleanup.

To remove a stale bootstrap account, stop the backend and review this dry run from
`backend` (the explicit URL selects the repository's local database):

```powershell
& '.\venv\Scripts\python.exe' -m app.cli.provision_beta_user --database-url 'sqlite:///backend/app/paper_trading.db' --cleanup-bootstrap --dry-run
```

After reviewing the reported UUID, account ID, and balances, run:

```powershell
& '.\venv\Scripts\python.exe' -m app.cli.provision_beta_user --database-url 'sqlite:///backend/app/paper_trading.db' --cleanup-bootstrap --confirm
```

This mode accepts no target identity or adoption options and performs no migration.
It requires the current schema, exactly one `DEFAULT_DEV_USER_ID` identity and
account, starting cash and cash balance both exactly $10,000, and no positions,
trades, watchlist items, or preference row. Unknown tables/schema drift and foreign
key violations also block cleanup. Confirmation creates a timestamped backup and
validates/deletes within one transaction protected by a SQLite write lock. Any
failed eligibility check aborts without deleting data. The dry run makes no changes
and creates no backup. Keep the backend stopped until the startup fix is deployed.

Normal user provisioning creates an active app user and exactly one fresh $10,000
paper account, with no positions or trades. Reruns retain the target's existing
account. This does not adopt or clean up the bootstrap account.

## Phase 7A: PostgreSQL compatibility and migration rehearsal

This phase supplies a migration path, not a production cutover. FastAPI remains
the only application-data boundary. React receives no database URL or credentials.
Supabase Auth is separate: the copy command does **not** migrate or modify Auth
users. Application user UUIDs must remain the corresponding Supabase UUIDs.

### Database configuration

Install backend dependencies from `backend`:

```powershell
& '.\venv\Scripts\python.exe' -m pip install -r requirements.txt
```

Supported `DATABASE_URL` forms:

```text
sqlite:///backend/app/paper_trading.db
sqlite:///C:/absolute/path/to/disposable.db
postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE
postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE?sslmode=verify-full
```

Relative SQLite URLs resolve from the repository root, including when running
from `backend`. PostgreSQL uses psycopg 3 (`psycopg[binary]>=3.2,<4`). Percent-encode
reserved characters in usernames/passwords. Use the provider's required TLS and
CA settings for a managed database. Keep secrets in ignored configuration or a
secret manager; do not place passwords in committed files or CLI arguments.
Application PostgreSQL connections set their session timezone to UTC.

Alembic is the schema authority for PostgreSQL. Startup does not run migrations
or create PostgreSQL tables; empty production SQLite databases also require
Alembic. Both backends use head **`20260902_03`**.
For a new, disposable SQLite development database, from `backend`:

```powershell
$env:DATABASE_URL='sqlite:///backend/backups/phase7-empty-development.db'
& '.\venv\Scripts\python.exe' -m alembic upgrade head
& '.\venv\Scripts\python.exe' -m alembic check
Remove-Item Env:DATABASE_URL
```

Ensure the parent directory exists first. Do not use the real SQLite file for
rehearsals, test setup, or schema drift experiments. The historical SQLite
migration still creates its compatibility bootstrap identity/account. Reviewed
legacy adoption or cleanup must be complete before that database can be copied.

### Local PostgreSQL and tests

From the repository root:

```powershell
docker compose -f compose.postgres-test.yml up -d --wait
```

This starts PostgreSQL 17 on **127.0.0.1:55432**, with database `tradepilot_test`,
user `tradepilot_test`, and the disposable password `local-test-only`. Override
`TRADEPILOT_TEST_PG_USER`, `TRADEPILOT_TEST_PG_PASSWORD`, and
`TRADEPILOT_TEST_PG_PORT` in the shell if needed, and match the URL below. The
service uses tmpfs; stopping/removing the container loses its disposable data.
It is not a production Compose configuration.

From `backend`, migrate the explicitly selected local test database:

```powershell
$env:DATABASE_URL='postgresql+psycopg://tradepilot_test:local-test-only@127.0.0.1:55432/tradepilot_test'
& '.\venv\Scripts\python.exe' -m alembic upgrade head
& '.\venv\Scripts\python.exe' -m alembic check
Remove-Item Env:DATABASE_URL
```

A fresh PostgreSQL upgrade leaves all six application tables empty. For tests:

```powershell
# Default suite: SQLite; PostgreSQL cases skip unless explicitly opted in.
& '.\venv\Scripts\python.exe' -m pytest -q

$env:TRADEPILOT_TEST_DATABASE_URL='postgresql+psycopg://tradepilot_test:local-test-only@127.0.0.1:55432/tradepilot_test'
& '.\venv\Scripts\python.exe' -m pytest tests/test_postgres_migration.py -q
Remove-Item Env:TRADEPILOT_TEST_DATABASE_URL
```

Install pytest separately in a development environment if unavailable. Test
connections deliberately use `TRADEPILOT_TEST_DATABASE_URL`, never the backend's
`DATABASE_URL`. The test harness requires a loopback host and control database
named `tradepilot_test`. Its user needs CREATEDB privileges. Every PostgreSQL test
creates and finally drops only its own random `tp_phase7_test_<uuid>` database;
it never clears or migrates the control database. Each schema is created by the
full Alembic chain, followed by `alembic check`. SQLite remains the unit-test default.

Coverage includes repository isolation, native/Python UUIDs, nullable theme and
JSON preservation, constraints/FKs/cascades, timestamp/ID trade ordering, rollback,
buy/sell atomicity, populated SQLite copies, backup equivalence, repeat refusal,
verification failure rollback, and sequence continuation. Failure tests use
intentionally corrupted disposable SQLite files only.

From the repository root, stop the disposable service after use:

```powershell
docker compose -f compose.postgres-test.yml down
```

### Copy CLI: inspect, confirm, verify

The source must be an existing SQLite file at head; the target must already be
a PostgreSQL database at the same head. The utility creates neither database nor
schema. It supports the application's six tables in PostgreSQL's `public` schema.
Unexpected tables/schema drift, nonempty targets, orphan rows, duplicate ownership,
nonfinite financial values, bootstrap identities, RLS, unvalidated constraints,
and custom/disabled triggers block the operation. It never merges portfolios or
silently removes a bootstrap account. Perform any necessary SQLite legacy
adoption/cleanup separately through the existing reviewed operator workflow.

Stop application writes throughout the final dry run, copy, and acceptance window.
A read-only SQLite transaction pins a consistent source snapshot. During confirmed
copy, PostgreSQL table locks prevent concurrent target writers; lock contention
fails after five seconds. Dry-run/verify-only use read-only target transactions.
Dry-run creates no backup, inserts, sequence changes, or source changes.

Set `MIGRATION_TARGET_DATABASE_URL` through your secret manager or ignored operator
environment. This variable is intentionally separate from `DATABASE_URL`; there
is no automatic production-target fallback. For a **local rehearsal only**:

```powershell
$env:MIGRATION_TARGET_DATABASE_URL='postgresql+psycopg://tradepilot_test:local-test-only@127.0.0.1:55432/tradepilot_test'
& '.\venv\Scripts\python.exe' -m app.cli.migrate_sqlite_to_postgres `
  --source 'C:/path/to/stopped-writes-sqlite-copy.db' --dry-run
```

Illustrative report excerpt (fixture counts, not the current real portfolio):

```json
{
  "dry_run": true,
  "source_revision": "20260902_03",
  "target_revision": "20260902_03",
  "source_users": 2,
  "source_accounts": 2,
  "source_positions": 2,
  "source_trades": 2,
  "source_watchlist": 2,
  "source_preferences": 2,
  "target_empty": true,
  "migration_possible": true,
  "committed": false,
  "blockers": []
}
```

The full report includes counts for all tables and per-user UUID, account count/ID,
balance, starting cash, position count/symbols, trade count/ID range, watchlist
count/symbols, theme, and preference-row presence. A presence flag can be true for
an empty `{}` preference object. Users without an account remain accountless;
the copy does not invent accounts. Reports contain portfolio information: retain
them as private operator artifacts. Connection identity includes host/port/database/
username and excludes passwords and URL query parameters.

After reviewing a successful dry run, the eventual authorized copy command is:

```powershell
& '.\venv\Scripts\python.exe' -m app.cli.migrate_sqlite_to_postgres `
  --source 'C:/path/to/stopped-writes-sqlite-copy.db' --confirm
```

`--confirm` revalidates eligibility, creates a unique SQLite backup under ignored
`backend/backups/` (override with `--backup-dir`), and verifies the backup against
the pinned source snapshot before any inserts. All six tables are copied in FK
order, preserving every column, ID, user UUID, timestamp, and JSON value. Explicit
integer IDs are followed by transactional `ALTER SEQUENCE ... RESTART WITH max+1`
for accounts, positions, and trades (or 1 for an empty table). Sequence names are
resolved from PostgreSQL catalogs, including the renamed account table's sequence.

Verification compares **all rows and columns**, not only summaries. Financial
floats use relative tolerance `1e-12` and absolute tolerance `1e-8`; UUIDs, strings,
timestamps, JSON, IDs, and other fields compare exactly. It checks relationships,
unique ownership, absence of bootstrap data, and sequence readiness. Verification
or insert failure rolls back all target row and sequence changes. The backup is
retained for diagnosis; the source is never altered. Success requires `committed:
true` and `verified: true`. Exit status is zero for success and nonzero for blockers.
Never assume success solely because a backup file exists.
If the connection fails during COMMIT, the report sets `commit_outcome_unknown`:
the server may have committed even though the client did not receive confirmation.
Keep writes stopped and use `--verify-only` to establish the actual target state
before deciding whether to retry.

Before starting writes, rerun verification independently:

```powershell
& '.\venv\Scripts\python.exe' -m app.cli.migrate_sqlite_to_postgres `
  --source 'C:/path/to/stopped-writes-sqlite-copy.db' --verify-only
Remove-Item Env:MIGRATION_TARGET_DATABASE_URL
```

`--verify-only` permits a populated target, makes no changes, checks complete data
equivalence and sequence readiness, and does not create another backup. Once new
PostgreSQL writes occur, equality to the frozen source is no longer expected.
Repeating `--confirm` against a populated target always aborts; retries are safe
only after a failed transaction left it empty. No destructive reset mode exists.

### Compatibility findings and operator limits

No model/API type conversion was required: SQLAlchemy `Uuid(as_uuid=True)` stores
SQLite hex strings and PostgreSQL native UUIDs while returning Python UUIDs.
`Float` remains double precision on PostgreSQL to preserve existing arithmetic;
this phase does not convert money to Decimal. `JSON` preserves scanner objects,
and theme remains nullable `Text`. All user/account FKs cascade on deletion;
one account per user and one symbol per account remain database constraints.
Watchlist composite PKs permit the same symbol for separate users. Existing
account/symbol and account/timestamp indexes remain intact. Trade ordering remains
`created_at DESC, id DESC`.

Timestamps remain text to preserve the API and historical values. PostgreSQL
generated strings can include fractional seconds and `+00`; application parsing
accepts these, and connections use UTC. No historical timestamps are rewritten.
The inherited text ordering assumes consistent chronological timestamp formatting;
manually mixed formats/timezone offsets deserve review before a real cutover.

The baseline and theme migrations were unchanged. The ownership migration
`20260829_02` has a narrowly scoped PostgreSQL correction: in-place ALTER instead
of forced table recreation, reflection of PostgreSQL's named symbol constraint,
and no compatibility seed on a fresh PostgreSQL database. Its SQLite path is
preserved. A forward migration cannot repair an earlier migration that fails
before reaching it, which is why this historical correction is necessary.
No new head revision or provisioning head constant change is needed.

The existing `provision_beta_user` legacy/adoption tool remains SQLite-only;
post-cutover onboarding tooling is a separate remaining operator task. This phase
does not change trading concurrency semantics (for example, simultaneous requests
against one account), deploy infrastructure, configure a managed provider, or
certify live Supabase authentication. The CLI holds complete snapshots in memory;
size the rehearsal for the real data volume before scheduling downtime. The
managed migration role needs table read/insert/lock and owned-sequence ALTER
privileges; validate these and TLS/network configuration during rehearsal.

### Eventual production cutover and rollback

Do not execute a production cutover as part of Phase 7A. The later operator sequence is:

1. Stop all writes, backend instances, and reloaders.
2. Back up SQLite with a consistent SQLite backup (include committed WAL contents).
3. Provision an empty managed PostgreSQL database separately.
4. Select it explicitly and run `alembic upgrade head`, then `alembic check`.
5. Run migration `--dry-run`; review revision, counts, ownership, and blockers.
6. Run the separately authorized `--confirm` copy.
7. Inspect the committed report and run `--verify-only` before any new writes.
8. Point only the backend's `DATABASE_URL` at PostgreSQL.
9. Start the backend.
10. Run authenticated two-user acceptance tests: account/position/trade isolation,
    watchlist, scanner preferences, theme, and an approved disposable buy/sell.
11. Retain the unchanged SQLite source, backup, and verification reports.

If copy/verification fails, keep writes stopped, inspect the blockers, and retry
only against an eligible empty target. Before PostgreSQL accepts new writes,
rollback is stopping the backend, restoring its prior SQLite `DATABASE_URL`, and
restarting against the preserved source. After any PostgreSQL writes, switching
back would lose those writes: stop writes and reconcile/export them through a
separately reviewed recovery procedure. This utility provides no reverse migration
and never deletes target data to force a retry.

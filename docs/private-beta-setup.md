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

Startup creates the compatibility bootstrap user/account only when the database
has no tables. Existing databases are left unchanged, including any stale bootstrap
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

# Phase 7B managed PostgreSQL operator runbook

Status: code/configuration preparation is complete; local validation is recorded separately. **Managed rehearsal, real
snapshot, live Supabase acceptance, and cutover are unexecuted.** No approved managed
target exists as of 2026-09-11. Do not execute these steps until the corresponding
operator checkpoint is approved. Do not deploy publicly in this phase.

## Managed target preparation

Use a dedicated empty application database with the `public` schema, separate from
Supabase Auth's database and from the final cutover target. The current migration
utility supports `public`, not an arbitrary rehearsal schema. Request a direct or
session-mode PostgreSQL endpoint; transaction-mode poolers have not been certified.
Record provider, host, port, database, region, PostgreSQL version, connection limit,
TLS CA requirements, backup retention/PITR policy, and restore-test evidence.
Confirm private networking/firewall access from the intended backend host. Use a
migration role able to create/alter tables and sequences and a server-only runtime
role with application table DML and sequence usage privileges. Neither role needs
Supabase service-role credentials. Check actual grants with the provider; do not
apply guessed provider-specific grants.

Use `postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE`. Percent-encode username
and password components once, never the entire URL. A password `a@b:c/d%` becomes
`a%40b%3Ac%2Fd%25`. Prefer building the URL with SQLAlchemy `URL.create` in a trusted
secret-management process and `render_as_string(hide_password=False)` only when
assigning it to the environment, never when logging it. Do not paste secrets into
commands, reports, Git, frontend settings, or chat. Enter an already encoded URL
without echo/history in a new backend-only PowerShell window:

```powershell
$secureTarget = Read-Host 'Encoded rehearsal PostgreSQL URL including TLS options' -AsSecureString
$env:MIGRATION_TARGET_DATABASE_URL = [System.Net.NetworkCredential]::new('', $secureTarget).Password
Remove-Variable secureTarget
```

Set `sslmode=verify-full` and the provider CA via `sslrootcert` in the URL (encode
query values too). `require` encrypts but does not consistently establish hostname
verification; prefer `verify-full`. Validate the provider certificate and hostname
in rehearsal. See [PostgreSQL TLS documentation](https://www.postgresql.org/docs/17/libpq-ssl.html).
Keep `DATABASE_URL` unchanged until the cutover checkpoint. Migration CLI reads
`MIGRATION_TARGET_DATABASE_URL` from the process environment, not automatically
from `.env`.

PostgreSQL runtime pools use pre-ping, 1800-second recycling, pool size 5, overflow
2, 30-second checkout timeout, and a 10-second connection timeout. The four pool
settings are centralized as `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`,
`DATABASE_POOL_TIMEOUT`, and `DATABASE_POOL_RECYCLE`. Budget seven connections per
worker plus operator connections. SQLite configuration is unchanged. Connections
use UTC, and existing text timestamps are copied unchanged. Sessions commit on
success and roll back on failure. Pre-ping handles stale connections on checkout;
it cannot repair an interrupted transaction. Do not blindly retry a paper trade
with an uncertain commit result. See [SQLAlchemy connection guidance](https://docs.sqlalchemy.org/en/20/faq/connections.html).

## Rehearsal: checkpoint 1 â€” stop writers and take a fresh snapshot

Operator must first stop FastAPI (Ctrl+C in its console or stop its known service),
background jobs, and every other SQLite writer. Inspect known backend processes;
a matching hash alone does not prove that no process can write. Do not kill unrelated
Python processes. Leave writers stopped until the snapshot and hashes are checked.

From the repository root, after operator confirmation:

```powershell
Set-Location 'C:\Users\Ragem\tradepilot-ai'
$python = (Resolve-Path '.\backend\venv\Scripts\python.exe').Path
$env:SQLITE_SOURCE = (Resolve-Path '.\backend\app\paper_trading.db').Path
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$rehearsalDir = Join-Path (Get-Location) "backend/backups/rehearsal-$stamp"
New-Item -ItemType Directory -Path $rehearsalDir -ErrorAction Stop | Out-Null
$env:SQLITE_SNAPSHOT = Join-Path $rehearsalDir 'source.db'
$sourceHash = (Get-FileHash $env:SQLITE_SOURCE -Algorithm SHA256).Hash
$sourceHash | Set-Content (Join-Path $rehearsalDir 'source-before.sha256')
@"
import os, sqlite3
from pathlib import Path
from contextlib import closing
source = Path(os.environ['SQLITE_SOURCE'])
target = Path(os.environ['SQLITE_SNAPSHOT'])
if target.exists():
    raise SystemExit('Snapshot already exists; refusing overwrite')
with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as src:
    src.execute('PRAGMA query_only=ON')
    with closing(sqlite3.connect(target)) as dst:
        src.backup(dst)
with closing(sqlite3.connect(target.as_uri() + '?mode=ro', uri=True)) as check:
    assert check.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
    assert check.execute('PRAGMA foreign_key_check').fetchall() == []
print('Snapshot opens and integrity checks passed')
"@ | & $python -
if ($LASTEXITCODE -ne 0) { throw 'Snapshot failed' }
if ((Get-FileHash $env:SQLITE_SOURCE).Hash -ne $sourceHash) { throw 'Source changed; stop and investigate' }
$snapshotHash = (Get-FileHash $env:SQLITE_SNAPSHOT).Hash
$snapshotHash | Set-Content (Join-Path $rehearsalDir 'snapshot.sha256')
```

SQLite backup includes committed WAL content; a raw file copy/hash alone may omit
WAL transactions. Preserve any original sidecars with the archive; never delete
or checkpoint them using these instructions. The snapshot hash need not equal
the source hash. Never run Alembic or provisioning against this immutable snapshot.

## Rehearsal: checkpoint 2 â€” prepare and inspect the empty target

Confirm the non-secret target identity is the approved rehearsal database. Use a
fresh database; never truncate an existing database to make this procedure pass.
The following commands scope Alembic to the migration target and restore the prior
process environment even if it fails. They do not edit `.env`.

```powershell
Set-Location 'C:\Users\Ragem\tradepilot-ai\backend'
$previousDatabaseUrl = $env:DATABASE_URL
try {
    if (-not $env:MIGRATION_TARGET_DATABASE_URL) { throw 'Missing explicit migration target' }
    $env:DATABASE_URL = $env:MIGRATION_TARGET_DATABASE_URL
    @"
from sqlalchemy import inspect
from app.db import engine
try:
    with engine.connect() as connection:
        assert not inspect(connection).get_table_names(schema='public'), 'Target public schema must be empty'
    print('Target public schema is empty')
finally:
    engine.dispose()
"@ | & $python -
    if ($LASTEXITCODE -ne 0) { throw 'Empty target check failed' }
    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Alembic failed' }
    & $python -m alembic check
    if ($LASTEXITCODE -ne 0) { throw 'Schema drift detected' }
} finally { $env:DATABASE_URL = $previousDatabaseUrl }
& $python -m app.cli.migrate_sqlite_to_postgres --source $env:SQLITE_SNAPSHOT --dry-run |
    Tee-Object -FilePath (Join-Path $rehearsalDir 'dry-run.json')
if ($LASTEXITCODE -ne 0) { throw 'Dry-run blocked' }
```

**STOP for operator review.** Require both revisions `20260902_03`, expected target
identity, `target_empty: true`, `migration_possible: true`, no blockers, and review
all source users/accounts. Expect two users and two accounts only if still current.
Verify original portfolio ownership, second user's $10,000 starting/current cash
and zero positions/trades unless subsequent real activity explains differences.
Review watchlist, theme and scanner preferences per UUID, no bootstrap, uniqueness
and foreign keys. Do not hardcode the two-user expectation into migration logic.

After explicit review approval, against the same rehearsal target only:

```powershell
& $python -m app.cli.migrate_sqlite_to_postgres --source $env:SQLITE_SNAPSHOT --confirm |
    Tee-Object -FilePath (Join-Path $rehearsalDir 'confirm.json')
if ($LASTEXITCODE -ne 0) { throw 'Copy failed; inspect target before retry' }
& $python -m app.cli.migrate_sqlite_to_postgres --source $env:SQLITE_SNAPSHOT --verify-only |
    Tee-Object -FilePath (Join-Path $rehearsalDir 'verify.json')
if ($LASTEXITCODE -ne 0) { throw 'Verification failed' }
if ((Get-FileHash $env:SQLITE_SNAPSHOT).Hash -ne $snapshotHash) { throw 'Snapshot changed' }
```

Require `committed: true` in confirm and `verified: true` with no blockers in
verify-only. Compare every per-user report, total counts, integrity and actual
sequence positions. `committed: false` in verify-only is normal: it does not copy.
Reports contain personal portfolio data; archive privately outside Git. Target
writes and sequence RESTART roll back together on copy failure. A lost commit
acknowledgment requires independent verification, not automatic retry.

## Rehearsal: checkpoint 3 â€” authenticated application acceptance

In a separate backend console, retain existing Supabase issuer/audience/JWKS
settings. Temporarily set the process `DATABASE_URL` to the approved rehearsal
URL, then start FastAPI locally. Do not persist the change to `.env`.

```powershell
Set-Location 'C:\Users\Ragem\tradepilot-ai\backend'
$previousDatabaseUrl = $env:DATABASE_URL
try {
    $env:DATABASE_URL = $env:MIGRATION_TARGET_DATABASE_URL
    & '.\venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8001
} finally { $env:DATABASE_URL = $previousDatabaseUrl }
```

Run `Invoke-RestMethod 'http://127.0.0.1:8001/health'`. For each real beta user's
existing Supabase session, enter an access token securely (never save it in reports)
and exercise actual API responses:

```powershell
$secureToken = Read-Host 'Existing beta user access token' -AsSecureString
$headers = @{ Authorization = 'Bearer ' + [System.Net.NetworkCredential]::new('', $secureToken).Password }
Remove-Variable secureToken
$base = 'http://127.0.0.1:8001'
foreach ($route in @('/auth/me','/paper/account','/paper/positions','/paper/trades',
                      '/paper/portfolio','/watchlist','/preferences/theme','/preferences/scanner')) {
    $response = Invoke-RestMethod "$base$route" -Headers $headers
    # Review privately: expected UUID, account and owned data; do not print headers.
    Write-Output $route
    $response | ConvertTo-Json -Depth 12
}
Remove-Variable headers
```

Use separate browser profiles for A and B if checking the UI; point the local
frontend at port 8001 by setting `$env:VITE_API_BASE_URL='http://127.0.0.1:8001'` in its console before `npm run dev` (remove the variable afterward). Record
both users' baseline responses. Ensure A's portfolio matches its migrated account
and B has its own account. On rehearsal only, add a symbol absent from A's watchlist
through `POST /watchlist` (`{"symbol":"MSFT"}`); verify B's list is byte-for-byte
unchanged, then remove only that newly added symbol with `DELETE /watchlist/MSFT`.
Change B's theme with `PUT /preferences/theme` (`{"theme":"light"}` or `dark`),
verify A is unchanged, and restore B's original theme. Verify scanner preferences
remain independently owned. Submit a controlled rehearsal paper buy for A through
`POST /paper/buy` (`{"symbol":"MSFT","shares":1,"price":1}`); verify only A's
cash, positions and trades change, and all B responses remain unchanged. Repeat
with B if desired. This leaves test trades in the rehearsal database: retire it;
do not promote it or expect source/target equality after these acceptance writes.
Do not perform this synthetic trade on the final production dataset.

## Normal PostgreSQL beta onboarding

Supabase identity existence is operator-verified. No Auth users are created or
changed by this CLI. Use the backend-only PostgreSQL `DATABASE_URL`, already at
Alembic head:

```powershell
& '.\venv\Scripts\python.exe' -m app.cli.provision_beta_user --user-id '<SUPABASE-UUID>' --email '<EMAIL>' --dry-run
# Review identity and target, then:
& '.\venv\Scripts\python.exe' -m app.cli.provision_beta_user --user-id '<SUPABASE-UUID>' --email '<EMAIL>' --confirm
```

Normal provisioning also retains its existing immediate-execution mode without
`--confirm`. It creates one active user and one fresh $10,000 account, no trades or
positions; reruns preserve existing accounts and balances. Identity conflicts abort.
Dry-run performs no writes or sequence allocations. Legacy adoption and cleanup
are rejected on PostgreSQL. Schema changes are always a separate Alembic operation.

## Final real cutover â€” separately authorized, never automatic

1. Complete managed rehearsal and both real-user acceptance records first. Verify
   provider backups/restore, TLS, privileges and connection budget. Select a new
   empty final managed database; do not reuse acceptance-mutated rehearsal data.
2. Ensure Phase 7B changes have been reviewed and committed by the operator.
   Run `git status --porcelain` (must be empty) and `git rev-parse HEAD`; record SHA.
3. Stop FastAPI and all writers. Confirm no jobs/services can reopen SQLite.
4. Repeat checkpoint 1 with a fresh timestamp: record source SHA-256, make a fresh
   backup/snapshot, open it read-only, verify integrity, and record snapshot hash.
5. Securely set `MIGRATION_TARGET_DATABASE_URL` to the final approved target.
   Repeat checkpoint 2's empty-target check, Alembic upgrade/check and dry-run
   against the fresh snapshot. Do not change the active application URL.
6. **STOP: operator reviews target identity, source/target revisions, counts,
   ownership, balances, integrity and backup evidence.**
7. Only after approval, run the exact `--confirm` and `--verify-only` commands above
   with this fresh snapshot and final target. Require successful reports and
   unchanged source/snapshot hashes. Compare source and target per-user reports.
8. **STOP: operator authorizes configuration switch.** Set backend `DATABASE_URL`
   in the server secret/environment configuration to the verified PostgreSQL
   runtime URL. Preserve the prior SQLite value securely. Do not modify frontend
   credentials or introduce any database connection in the browser.
9. Start the backend using its existing local launch command. Check `/health`
   (liveness only), then authenticated `/auth/me` and database-backed account routes.
10. Log in separately as A and B; validate every acceptance read above. Confirm
    ownership, portfolio/watchlist/preferences and independent accounts. Any write
    check requires tracking the resulting PostgreSQL-only writes. Prefer reversible
    watchlist/theme checks; keep synthetic paper trades confined to rehearsal.
11. Leave original SQLite untouched and archived, retain its sidecars and the fresh
    readable backup, and prevent any old SQLite-configured process from restarting.
12. Record final migration reports, Git SHA, hashes, target identity, time, operator,
    acceptance results and whether any PostgreSQL-only writes occurred. Do not
    deploy publicly as part of this procedure.

## Rollback

- Before URL switch: retain SQLite; fix/recreate a separately approved empty target
  and retry from a fresh reviewed snapshot. Never clear a target automatically.
- After migration but before backend start: keep configuration on SQLite; if already
  edited, restore the saved SQLite URL before starting anything.
- After brief PostgreSQL runtime with **no meaningful new writes**: stop backend,
  verify that no PostgreSQL-only changes need preserving, restore SQLite URL and
  investigate. Reads may create missing accounts; check actual data, not just elapsed
  time or assumptions about user activity.
- **After any PostgreSQL-only writes: DO NOT blindly switch back to SQLite. Data
  would diverge. Freeze writes, preserve both datasets and reconcile intentionally
  with separately reviewed recovery steps.** No reverse migration is provided.

## Production safeguards and validation scope

Startup does not migrate schemas or call create_all for PostgreSQL; empty targets
require Alembic. Existing databases do not create bootstrap identities. Authenticated
UUID remains ownership authority through FastAPI dependencies and repositories.
Application data remains behind FastAPI, with server-only database credentials.
No frontend, Supabase Auth, deployment or automatic commit changes are included.

See [Phase 7B validation](phase7b-validation.md) for executed tests and remaining
blockers. Automated PostgreSQL tests accept only loopback `tradepilot_test` and
create random disposable databases; never set their URL to a managed target.

# Phase 7A implementation and validation

Validated on 2026-09-10. No production migration, deployment, Supabase Auth mutation,
frontend change, or Git commit was performed.

## Compatibility findings

- Existing SQLAlchemy models already use portable `Uuid(as_uuid=True)`, `JSON`,
  `Float`, integer keys, and nullable text theme. Python UUIDs and PostgreSQL native
  UUIDs were verified. No model conversion or API response change was needed.
- One account per user, composite account/symbol position uniqueness, composite
  user/symbol watchlists, FK cascades, existing indexes, and descending timestamp/
  ID trade ordering work on both database backends. Delete and rollback tests
  confirm ownership boundaries.
- Text timestamps and float arithmetic are retained. PostgreSQL application
  connections now use UTC; ISO strings with offsets remain parseable by the
  existing backend. Historical source timestamps are copied exactly.
- The historical ownership migration forced SQLite-style recreation and assumed
  an unnamed SQLite constraint. Its PostgreSQL path now uses in-place ALTER and
  the reflected PostgreSQL constraint name. Fresh PostgreSQL schemas receive no
  bootstrap user/account. SQLite behavior remains unchanged. The baseline/theme
  revisions were unchanged; head remains `20260902_03` on both backends.
- This correction must occur in the earlier migration: a new forward revision
  cannot repair an earlier failure that prevents reaching it. Alembic documents
  the [PostgreSQL constraints involved in batch recreation](https://alembic.sqlalchemy.org/en/latest/batch.html).
- Startup refuses to create tables in an empty PostgreSQL or production SQLite
  database, requiring Alembic instead.

## Files and dependencies

| File | Change |
| --- | --- |
| `backend/app/db.py` | SQLite driver-name handling and PostgreSQL UTC connections |
| `backend/app/paper_trading.py` | Require Alembic for empty PostgreSQL/production databases |
| `backend/migrations/versions/20260829_02_multi_user_schema.py` | Narrow PostgreSQL migration compatibility path |
| `backend/requirements.txt` | Add `psycopg[binary]>=3.2,<4`; tested with 3.3.5 |
| `.env.example` | Safe PostgreSQL placeholder and current SQLite guidance |
| `compose.postgres-test.yml` | Loopback PostgreSQL 17, disposable tmpfs data, configurable local credentials |
| `backend/app/cli/migrate_sqlite_to_postgres.py` | Explicit dry-run, backup/copy, and independent verification CLI |
| `backend/tests/test_postgres_migration.py` | 45 SQLite/PostgreSQL migration, safety, and persistence cases |
| `docs/private-beta-setup.md` | Configuration, test commands, copy workflow, cutover and rollback runbook |
| `docs/phase7a-validation.md` | This implementation/validation record |

## Copy and verification behavior

From `backend`, set the distinct `MIGRATION_TARGET_DATABASE_URL` securely, then:

```powershell
& '.\venv\Scripts\python.exe' -m app.cli.migrate_sqlite_to_postgres --source 'C:/path/to/rehearsal.db' --dry-run
# Only after reviewing the dry-run result:
& '.\venv\Scripts\python.exe' -m app.cli.migrate_sqlite_to_postgres --source 'C:/path/to/rehearsal.db' --confirm
& '.\venv\Scripts\python.exe' -m app.cli.migrate_sqlite_to_postgres --source 'C:/path/to/rehearsal.db' --verify-only
```

The [operator runbook](private-beta-setup.md#copy-cli-inspect-confirm-verify)
contains a complete dry-run example and production cutover sequence. The CLI
requires both revisions at head, known schema, valid relationships, no bootstrap
identity, and an empty target for copying. RLS/custom or disabled triggers and
unvalidated constraints block copying. No schema provisioning or portfolio merging
occurs. Dry-run is read-only and creates no backup.

Confirmed copying creates and checks a unique SQLite backup, inserts all six
tables with original IDs and fields, resets all three integer sequences, and
compares every row/column before committing. Financial comparisons use relative
tolerance `1e-12` and absolute tolerance `1e-8`. Counts and per-user ownership,
balances, symbols, trade ranges, theme, and preference presence are reported.
URLs/passwords/query parameters are excluded from reports. Source reads are
read-only, snapshot-consistent, and include committed WAL contents.

Sequence changes use [transactional PostgreSQL RESTART](https://www.postgresql.org/docs/current/sql-altersequence.html),
so injected verification failures roll back rows and sequence changes together.
If a connection fails during COMMIT, the report explicitly marks the outcome as
unknown and requires inspecting target state before retrying. Independent
`--verify-only` also detects sequences behind migrated IDs without advancing them.

## Final validation

The complete backend suite ran with PostgreSQL tests enabled:

```text
230 passed, 146 subtests passed, 2 warnings in 45.61s
```

The two warnings are existing FastAPI `on_event` deprecations. There were no
skipped PostgreSQL cases in this final run. This includes:

- All 45 new focused database/migration cases and the existing migration tests.
- Empty SQLite and PostgreSQL Alembic upgrades through head and metadata checks.
- A populated PostgreSQL baseline upgrade preserving rows/relationships.
- Two-user repository isolation, constraints/FKs, cascades, rollback, and
  successful/failing atomic paper buys and sells.
- Populated temporary SQLite -> temporary PostgreSQL copying with exact IDs,
  backup verification, follow-up verification, and sequence continuation.
- Empty source tables, sequence regression detection, committed WAL backup,
  nonempty-target refusal, RLS refusal, and injected backup/insert/sequence/
  verification failures.
- Missing source, wrong mode/target, source read-only enforcement, schema/revision
  blockers, orphans, unexpected bootstrap rows, and float tolerance checks.

`git diff --check` passed. Docker was unavailable on the validation machine, so
the Compose launch itself was not executed. Live tests used official portable
PostgreSQL **17.11** binaries in a temporary cluster bound only to
`127.0.0.1:55439`, with random per-test databases. No installed PostgreSQL service
or application database was reused. The temporary server was stopped after testing.

The real `backend/app/paper_trading.db` was never opened by the new migration
utility or used as a test target. Its SHA-256 before and after validation matched:

```text
308A5326E33497310D44068FB0B5063F46732A046841DA640A2CF5C063F301AD
```

## Remaining work before production cutover

- Rehearse managed-provider TLS, networking, privileges, backup retention, and
  downtime against an approved source snapshot and empty managed target.
- Run the actual authenticated two-user acceptance checks after the separately
  authorized cutover. Local database tests do not certify live Supabase sessions.
- Existing beta provisioning/adoption tooling is SQLite-only; PostgreSQL
  onboarding support remains a separate operator task.
- Existing simultaneous same-account trading semantics are unchanged. Historical
  text timestamps are not normalized; inspect mixed manual formats/offsets if any.
- The utility loads complete snapshots in memory; size a rehearsal to actual data.
- Stop all writes during copy and verification. Once PostgreSQL accepts new writes,
  reverting to SQLite requires separately reviewed reconciliation; no reverse
  migration or automatic target reset is supplied.

Recommended commit message: `feat(db): add PostgreSQL migration path`

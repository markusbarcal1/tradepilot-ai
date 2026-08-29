# Paper-trading migrations

For a new empty database, run `alembic upgrade head` from `backend`. The current
head creates the multi-user-capable schema and deterministic bootstrap user/account.

The existing `app/paper_trading.db` already has this schema and data. Back it up,
verify its schema, then mark it at the baseline without running the baseline DDL:

```powershell
alembic stamp 20260828_01
```

Stamping adds only Alembic's version table; it does not run baseline DDL. After
checking the backup and stamp, apply Phase 2 with:

```powershell
alembic upgrade head
```

Revision `20260829_02` assigns the existing account, positions, and trades to
bootstrap user `00000000-0000-4000-8000-000000000001`, preserving row IDs,
monetary values, and timestamps. It replaces global position uniqueness with
`(account_id, symbol)` and adds user-owned watchlist and scanner-preference tables.

Do not run this procedure against `app/paper_trading.db` without first recording
its hash, size, account values, position/trade counts, and current revision. The
application refuses to modify a detected Phase 1B schema at startup; Alembic owns
the transition. Test migrations must use temporary databases or verified copies.

SQLite stores UUID values in a portable character representation and JSON as
text through SQLAlchemy. PostgreSQL will use its native UUID/JSON-compatible
implementations. Monetary values remain floating point for compatibility; a
future Numeric/Decimal migration should be planned separately.

Create future revisions with `alembic revision --autogenerate -m "description"`
and review generated operations before applying them with `alembic upgrade head`.

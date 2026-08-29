# Paper-trading schema baseline

For a new empty database, run `alembic upgrade head` from `backend`. This creates
the current paper-trading tables. Application startup then creates the initial
paper account if none exists.

The existing `app/paper_trading.db` already has this schema and data. Back it up,
verify its schema, then mark it at the baseline without running the baseline DDL:

```powershell
alembic stamp 20260828_01
```

Stamping adds only Alembic's version table; it does not run the migration. Phase
1B intentionally does not stamp or migrate the real local database automatically.

Create future revisions with `alembic revision --autogenerate -m "description"`
and review generated operations before applying them with `alembic upgrade head`.

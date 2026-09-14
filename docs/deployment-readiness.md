# Private-beta deployment readiness

Deployment targets: **Render** (FastAPI), **Vercel** (React/Vite), and
**Supabase** (Auth and authoritative PostgreSQL). Branch: `private-beta`.
The production PostgreSQL cutover is complete per the operator's current status;
the former production SQLite database is archived. Do not rerun the cutover.
This phase prepares the repository only: no deployment, production data changes,
credential rotation, or automatic commit.

## Render setup (manual)

Use one Python web service, one instance, and one Uvicorn process initially.
Dashboard configuration is sufficient; no Blueprint, Docker, disk, or migration
hook is needed for this service.

| Setting | Value |
| --- | --- |
| Branch | `private-beta` |
| Root directory | `backend` |
| Python | `3.12.10`, matching the tested local venv and `backend/.python-version` |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` |
| Automatic deploys | Disable until the first deployment is explicitly approved |

Set `PYTHON_VERSION` to the same version in Render to make the runtime selection
explicit. Render supplies `PORT`. Do not use `--reload` in hosting. The app's
`LOG_LEVEL` controls application logging; Uvicorn defaults to info (its
`--log-level` option controls server logging separately).

Required backend environment variable names:

- `ENVIRONMENT`
- `DATABASE_URL`
- `SUPABASE_AUTH_ISSUER`
- `SUPABASE_AUTH_AUDIENCE`
- `SUPABASE_JWKS_URL`
- `CORS_ORIGINS`
- `PYTHON_VERSION`

Optional backend variable names (bounded defaults are in `.env.example`):

- `DATABASE_POOL_SIZE`
- `DATABASE_MAX_OVERFLOW`
- `DATABASE_POOL_TIMEOUT`
- `DATABASE_POOL_RECYCLE`
- `SCANNER_MAX_WORKERS`
- `SCANNER_AUDIT`
- `LOG_LEVEL`

Use production mode. Supply the existing PostgreSQL connection securely with the
explicit `postgresql+psycopg` driver and percent-encoded credentials. Do not copy a
local Windows certificate path into Render: provision the provider CA as a Render
secret file and reference its runtime path when using `sslrootcert`. Preserve
verified TLS (`sslmode=verify-full`) and verify Render-to-Supabase network access,
hostname, port, and connection mode manually. See the existing cutover runbook for
connection and TLS details; no migration target URL is needed by the web service.

Use the project's asymmetric Auth issuer/JWKS configuration and intended JWT
audience. A service-role key is not needed by the API. Configure exact frontend
origins in `CORS_ORIGINS`, comma separated or a JSON array, without paths. Wildcard
origins are rejected and credentialed CORS uses the explicit list. Production
origins replace the localhost defaults; include localhost explicitly only if
needed. Do not guess a future Vercel domain or broadly allow preview domains.

## Vercel setup (manual)

| Setting | Value |
| --- | --- |
| Production branch | `private-beta` |
| Root directory | `frontend` |
| Framework preset | Vite |
| Node version | `24.x` |
| Install command | `npm ci` |
| Build command | `npm run build` |
| Output directory | `dist` |

The inspected local Node version is `26.7.0`. Vercel currently documents 24.x,
22.x, and 20.x, so select 24.x for hosting rather than pinning unsupported 26.x.
This is a hosting compatibility choice; the local Node installation is unchanged.
Vercel manages minor/patch updates within the selected major version.
Build/lint and auth/config checks also passed locally using temporary Node
`24.21.0`; no system Node replacement was needed.

Required frontend environment variable names:

- `VITE_API_BASE_URL`
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY` **or** `VITE_SUPABASE_PUBLISHABLE_KEY`

The existing publishable-key setting takes precedence when both are present.
Use only the public browser key. All `VITE_` values are embedded into public
JavaScript; never supply database credentials, JWT signing secrets, or a
service-role/secret key. Set the API base to the HTTPS Render origin. Vercel's
environment settings override local examples at build time; changes require a
new build. Builds reject missing required settings without printing their values.
The development server retains the localhost API fallback.

Navigation currently uses React state at `/`, without history-based page routes.
No `vercel.json` rewrite is necessary for the current app. Use `/` for invite
redirects; query strings and fragments carry invitation state. If path routing is
introduced, add and test Vercel's SPA fallback then.

In Supabase, configure the final frontend root as Site URL and add the exact invite
redirect URL(s) to the allowed redirect list. Retain local redirects only where
needed for development. Keep public signup disabled and provision beta users
through the existing operator workflow. Do not send invites during this phase.
Preview environments need deliberate API/CORS/Auth configuration and should not
automatically share production access.

## Audit findings and boundaries

- Runtime dependencies include FastAPI, Uvicorn, SQLAlchemy, Alembic, and
  `psycopg[binary]`; direct versions are pinned to the installed Python 3.12.10
  environment. `pip check` passes. Transitive dependencies are not fully locked;
  the first clean Linux Render build still needs verification.
- `app.main:app` imports from the backend root. Settings locate optional `.env`
  relative to source, not the working directory, and process environment wins.
  Hosting does not require a repository `.env` file.
- Normal application persistence uses SQLAlchemy with PostgreSQL support. SQLite
  PRAGMA/path handling is dialect-specific. Empty local/test SQLite databases
  retain compatibility bootstrap behavior; empty PostgreSQL or production
  databases require Alembic. Existing PostgreSQL startup inspects tables and
  returns without schema/data writes.
- **Alembic is schema authority.** Startup does not validate every table or the
  current Alembic revision, and production settings still retain the legacy
  SQLite default if `DATABASE_URL` is omitted. Explicit PostgreSQL configuration
  and an operator schema check are mandatory. Never run upgrades in build/start
  commands. Any future migration requires separate review and authorization.
- `/health` returns HTTP 200 with `{"status":"ok"}` without authentication.
  It is a lightweight liveness check, not a database/JWKS/provider readiness probe.
  An unauthenticated `/auth/me` returns HTTP 401 with a Bearer challenge.
  A valid identity without active beta membership returns 403.
- App analysis caches are process-local and disposable. yfinance also writes
  SQLite cookie/timezone/ISIN caches under the OS user cache directory. Render
  needs a writable ephemeral user cache; these are not application persistence
  and do not need a persistent disk. Standard output carries logs. External
  Yahoo/Nasdaq/JWKS access and provider rate limits must be checked from hosting.
- Scanner concurrency is bounded per scan, not globally across all requests.
  `SCANNER_AUDIT` is an optional environment toggle. Start with one instance and
  conservative scanner concurrency; assess overlapping scans and memory before
  increasing capacity. Each Uvicorn process has its own pool (default maximum
  seven database connections) and caches.
- Git ignores `.env` variants except safe `.env.example`, SQLite files/sidecars,
  backups, local reports, caches, and build outputs. Store raw migration evidence
  under ignored `backend/backups/`, `migration-snapshots/`, or `cutover-reports/`,
  or name it `*.local.json` / `*.local.md`. Sanitized runbooks remain tracked.
  Never commit secrets; ignore rules can be bypassed by force-add, so review the
  staged diff. No backup file should be deleted as part of deployment preparation.

## Local development and validation

From `backend`, activate `venv` and run `uvicorn app.main:app --reload`.
From `frontend`, run `npm run dev`. Local/private `.env` files are unchanged.
For frontend checks, run `npm test`, `npm run lint`, and `npm run build` with safe
test values for all required Vite settings when validating offline.

Run backend tests from `backend` with `venv/Scripts/python.exe -m pytest -q`,
overriding `ENVIRONMENT=test` and `DATABASE_URL=sqlite:///:memory:` in that test
process. Clear `TRADEPILOT_TEST_DATABASE_URL` to skip opt-in PostgreSQL tests;
those require separately provisioned disposable loopback PostgreSQL. Never test
against the authoritative database or the archived SQLite file.

## Post-deploy acceptance checklist (future authorized phase)

- Confirm build logs show the intended runtimes and successful clean installs.
- Confirm explicit production PostgreSQL/TLS settings and reviewed Alembic head;
  confirm no automatic migration or compatibility bootstrap ran.
- Check HTTPS `/health` returns 200; unauthenticated `/auth/me` returns 401.
- Verify CORS preflight accepts the exact frontend origin and rejects an unrelated
  origin; inspect the browser to confirm API requests target Render.
- Complete an authorized invitation at `/`, sign in, refresh, and sign out.
  Verify JWT validation, active beta membership, and disabled/unknown-user denial.
- With designated beta test accounts, verify two-user isolation, watchlists,
  theme/scanner preferences, and paper-trading persistence across restarts.
  This check writes test-account data and requires authorization in that phase.
- Verify analysis and streaming scans from the deployed network, including
  provider-unavailable behavior, overlapping scans, and cache recreation.
- Confirm no secrets appear in logs or frontend assets; only public browser
  configuration belongs in the frontend bundle.

Next step: review these changes, then prepare the manual hosting environment and
final URLs for a separately authorized first deployment. Do not initiate deployment
by importing a project or enabling Git integration during this audit.

## Validation recorded in this phase

- Python 3.12.10: `204 passed, 46 skipped, 150 subtests passed`; the skipped tests
  require opt-in disposable PostgreSQL. Two existing FastAPI startup-hook
  deprecation warnings remain. `pip check` and `git diff --check` passed.
- Frontend: tests, lint, and build passed with Node 26.7.0; Node 24.21.0 build,
  lint, auth/config checks passed too. Vite reports the existing bundle-size
  warning (approximately 699 kB minified JS); no bundling redesign was added.
- Actual Uvicorn subprocess with the hosting bind/port arguments passed health,
  unauthenticated auth, and allowed/denied CORS checks. It used production mode
  against a pre-created disposable SQLite schema; its file hash was unchanged.
  This proves local startup behavior, not managed PostgreSQL connectivity.
- Tracked files contained no matches for local credential values or the checked
  high-confidence secret patterns. Reachable Git history lists only safe examples
  for the audited `.env` paths. This is a scoped check, not exhaustive history
  secret-scanner certification. Ignore checks passed for secrets, sidecars,
  backup/report paths, caches, and build outputs; examples remain trackable.
- No production database connection, live auth/provider request, deployment,
  migration, backup deletion, credential rotation, or commit was performed.
  Clean Linux dependency installation and hosted acceptance remain pending.

## Hosting references

- [Render Python version](https://render.com/docs/python-version)
- [Render health checks](https://render.com/docs/health-checks)
- [Vercel Node versions](https://vercel.com/docs/functions/runtimes/node-js/node-js-versions)
- [Vite on Vercel](https://vercel.com/docs/frameworks/frontend/vite)
- [Supabase redirect URLs](https://supabase.com/docs/guides/auth/redirect-urls)

# Phase 6A.2B.2 — Expectation Persistence & Deterministic Earnings Surprise

Date: 2026-09-20  
Migration: `20260920_04`  
Mandatory API cost: $0

## Architecture

The implementation extends the existing `ExternalEvent` and `EventMeasurement` path:

```text
approved future provider
  -> normalized ExpectationSnapshot
  -> global append-only ExpectationRepository
  -> reporting/metric/value/temporal selector
  -> deterministic EventSurprise
  -> existing Earnings intelligence
  -> bounded OutlookContextPacket schema 2.2
```

There is no production expectation provider, scheduler, polling loop, startup network request, or background collection. `RepositoryExpectationProvider` is the provider-neutral read adapter. Acquisition and persistence are intentionally separate; a provider supplies observations and never calculates surprise, assigns direction, mutates actuals, or generates text.

## Snapshot contract and immutability

`ExpectationSnapshot` now carries optional normalized ticker, authoritative reporting identity, structured metric identity, currency, analyst count, low/high estimates, capture/provider-as-of timestamps, provider, temporal status, and origin. The older generic event fields remain compatible.

Persisted observations are global shared market intelligence and have no `user_id`. Duplicating identical market observations per beta user would waste storage and could produce inconsistent timelines.

`expectation_snapshots` is append-only at the repository boundary. A reused `snapshot_id` with different content is rejected. Exact repeated provider observations deduplicate through a SHA-256 fingerprint over:

- ticker and authoritative fiscal-period identity;
- metric identity;
- expected value/range, currency, and analyst count;
- provider and source URL;
- provider-as-of and source-published timestamps;
- surprise origin.

Capture/retrieval time is not in the fingerprint, so repeated polling of the same source observation does not create unlimited rows. A changed value, range, count, provider-as-of time, or source publication time creates a new immutable observation. This deliberately treats a later return to an identical timestamp-free payload as the same provider observation; a future provider with value-level as-of timestamps should always populate them.

The table stores query columns for ticker, fiscal year, fiscal period, metric key, and capture time, plus structured JSON identities/provenance. The repository returns chronological history and the newest observation. Existing SQLite-to-PostgreSQL tooling discovers the table from shared SQLAlchemy metadata and copies/verifies it with the other application tables.

## Temporal validation

A released comparison requires a conservative release boundary and:

```text
captured_at < release_at
provider_as_of_at < release_at, when present
source_published_at < release_at, when present
```

Equality and post-release observations are rejected. The newest compatible strictly pre-release snapshot wins, with `snapshot_id` as a stable tie-break.

Boundary rules are:

- exact `announced_at`: use that aware instant;
- before-market date only: use 00:00 America/New_York;
- after-market date only: use 16:00 America/New_York;
- during-market without an exact time, unknown session, or unresolved date: comparison unavailable.

Timezone conversion uses `America/New_York` and UTC. No exact release time is guessed. Rejection diagnostics include no snapshots, unresolved/mismatched reporting period, metric/accounting/share/scope mismatch, currency/unit mismatch, unknown timestamp, and post-release-only history.

## Reporting and metric compatibility

Both expectation and actual must have one authoritative issuer fiscal quarter. Fiscal year and quarter must match, and conflicting period ends are rejected. Calendar proximity is never used, preserving AAPL/NVDA and 52/53-week fiscal behavior.

Structured identities support:

- revenue;
- diluted GAAP EPS;
- basic GAAP EPS;
- adjusted EPS;
- explicit total-company, continuing-operations, other, or unknown scope;
- constant-currency distinction.

Revenue uses `accounting_basis=not_applicable` and `share_basis=not_applicable`. EPS requires a share basis. Unknown/provider-defined EPS basis is incompatible for surprise calculation. GAAP and adjusted EPS never compare. Diluted and basic EPS never compare. Unknown scope is rejected.

Existing SEC revenue actuals are marked total-company USD when the controlled interpreter emitted them. Existing SEC EPS actuals retain diluted/basic identity where known, but accounting basis is marked unknown because the legacy text rule does not always prove GAAP versus adjusted. This is an intentional conservative divergence from simply labeling all SEC-exhibit EPS as GAAP: those actuals remain visible, but the strict engine will not produce a beat/miss until basis is authoritative.

USD revenue thousand/million/billion units can be deterministically normalized. Other unit conversions are rejected. Currency must match exactly, and revenue expectations require explicit currency. Constant-currency revenue does not compare with ordinary reported revenue.

## Surprise engine

For compatible scalar values:

```text
difference = actual - expected
percent_difference = difference / abs(expected) * 100
```

Percentage is unavailable when expected is effectively zero or the comparison crosses zero, because the percent is misleading. The amount and direction remain available.

EPS arithmetic correctly treats:

- a smaller loss as a beat;
- a larger loss as a miss;
- expected loss / actual profit as a beat;
- expected profit / actual loss as a miss.

Comparison results are `beat`, `miss`, `approximately_in_line`, or `unavailable`. TradePilot calculations carry `origin=tradepilot_calculated`; a future vendor record must carry `provider_reported` and may not masquerade as a TradePilot reconstruction.

Approximately-in-line tolerance is versioned in code:

- revenue: 0.5% of absolute expected revenue;
- EPS: the greater of $0.01/share and 0.5% of absolute expected EPS;
- equality with the boundary is in line.

Tolerance is comparison precision, not materiality or scoring. Expectations, analyst counts, ranges, and future estimate history are non-directional alone.

## Released and upcoming semantics

Only a compatible verified pre-release actual-versus-expectation result can create deterministic beat/miss directionality. Existing verified YoY, margin, and guidance evidence remains unchanged.

For an upcoming event with a compatible authoritative reporting identity, the latest current snapshot can populate expected value, range, analyst count, and capture time as informational context. It cannot create positive or negative direction. The present Yahoo date-only event lacks authoritative fiscal identity, so no snapshot is silently attached to it.

Raw history stays in persistence. The existing bounded context packet receives only event measurement conclusions: actual/selected expected values for released events and the latest expected value for an eligible upcoming event. Prompt `outlook-analyst-2.4` and schema `2.2` are unchanged. Facts remain owned by Earnings, use opaque IDs, and remain subject to existing grounding validation.

Company guidance remains separate. It is not stored as analyst consensus and the SEC guidance interpreter remains authoritative.

## Diagnostics and limitations

`EventMeasurement.surprise` now preserves actual, expected, difference, percent when meaningful, comparison result, selected snapshot ID, origin, zero-crossing state, and deterministic rejection reason. Per-measurement diagnostics also expose candidate/compatible/temporally-valid counts, selected snapshot/capture time, release boundary, compatibility result, and origin. Existing event CLI JSON serialization exposes these fields without provider secrets.

Current limitations:

- production expectation provider: none;
- no automatic acquisition or scheduler;
- no historical consensus backfill;
- upcoming Yahoo events generally lack authoritative fiscal identity;
- legacy SEC EPS accounting basis remains unresolved unless explicitly enriched later;
- no revision scoring;
- beat probability unavailable;
- implied move unavailable;
- no UI change.

## Next recommended phase

Phase 6A.2B.3 should be a provider qualification and tiny prospective-capture proof. Select one legally approved source only after written confirmation of field semantics, storage/display rights, accounting basis, fiscal identity, timestamp guarantees, rate limits, and private-beta use. Activate it for an operator-controlled fixture universe, capture snapshots explicitly, and evaluate real pre-release-to-release joins without changing scoring, prompt, schema, or UI.

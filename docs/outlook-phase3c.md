# Outlook Phase 3C: evaluation and factual event semantics

## Selected method (before implementation)

An explicitly identified earnings release remains one independent event. Its
recognized financial metrics are factual factors, not competing representatives
of the entire event. Factor identity includes normalized metric, comparison,
reporting period and accounting basis. Unknown identities retain legacy handling.
Guidance independence and all category/overall calibration remain unchanged.

Within each factor, authoritative primary records take precedence. Eligibility
is checked before conflict detection, so below-threshold noise cannot suppress
supported facts. Duplicate reports contribute once. Contradictory eligible
assertions about the same factor exclude that factor; unrelated factors survive.
All records and exclusions remain in provenance.

For eligible distinct factors f, use existing support w_f=C_f*M_f*F_f and impact
I_f. One event has W=max(w_f), effective impact I=sum(I_f*w_f)/sum(w_f), and
directional contribution D=W*I. Thus identical aligned factors preserve the old
single-factor weight; adding metrics never sums independent-event support;
opposing factors are attenuated by their actual support. This is an explicit
representation choice requiring future empirical evaluation, not a calibrated
financial truth. Event interpretation confidence is the support-weighted mean
of factor confidences. Its category-confidence mass is W/C_event, preserving
the existing category confidence formula for single-factor events. No synthetic
integer impact or fabricated normalized evidence is created.

IDs, titles, provider names and input order may order display provenance but
cannot select financial values for this path. Duplicate factual ties use only
financial fields; freshness uses the oldest authoritative duplicate, preserving
the protection against refresh by syndication. Existing legacy clustering and
non-financial-event assessment remain unchanged.

## Scope and compatibility

No policy constants, freshness rules, interpreter impact/confidence/materiality
formulas, overall thresholds, provider limits, live configuration, or frontend
files changed. Guidance remains separate under existing independence rules.
The existing 48-hour lexical clustering is retained, including same-day repeated
filing behavior. This phase changes factual assessment *within* identified
earnings-result/margin clusters, not the general event-identity engine.

`OutlookEvidence` is unchanged. `FactorAssessment` retains factor identity,
all source records, representative provenance, freshness, support and exclusion.
`EvidenceContribution` adds these factor assessments and event confidence; its
representative is now only a compatible carrier of category/source metadata for
this path. Its representative impact must not be mistaken for the mixed event's
effective impact, which is contribution divided by support.

Eligibility precedes sign/numeric conflicts. Same-metric eligible assertions
with opposite signs or different explicit like-unit numeric values conflict.
Conflicting factors contribute zero while other supported dimensions survive.
The chosen duplicate uses maximum C*M, then confidence, materiality, conservative
absolute impact magnitude and publication time. Equal financial ties have the
same mathematics regardless of provenance ordering. `fsum` makes category sums
numerically stable without changing the category formula.

Freshness is the oldest confidence/materiality-qualified authoritative report
for that factor. Below-threshold old noise cannot expire a supported factor;
an old qualified duplicate still cannot be refreshed through republication.
Primary precedence is per factual dimension, including when a primary assertion
fails an eligibility gate: secondary reporting does not replace it.

An unspecified period/accounting basis is not assumed to mean GAAP. When it may
duplicate a more precisely identified factor, it is retained but excluded as
`ambiguous_factor_identity`. A secondary basis annotation cannot displace primary
evidence. Unsupported identities within a financial-factor cluster are retained
as `unidentified_factor`; clusters without any known financial factors keep the
legacy path. GAAP and explicitly non-GAAP identities are never blended as the
same fact. Production interpretation still only extracts the supported GAAP table
formats; no new non-GAAP parser was introduced.

## Corpus architecture and versioning

`app/evaluation/outlook/v1.json` is a checked-in offline corpus with schema version
`1.0` and corpus version `3c.1`. Bump the corpus version when adding or revising
expectations; bump the schema version for incompatible fixture changes.

The seed contains 34 small packages (slightly above the suggested 20–30 so all
five coverage scenarios remain individually inspectable), with 48 assessment
points. These are synthetic/sanitized examples, not a representative calibrated
financial dataset or a collection of downloaded SEC releases.

Each validated package includes issuer/context, sector/industry, event identity,
reporting period, materiality rationale, frozen SourceDocuments/optional short
HTML and/or normalized evidence, publication and observation timestamps, expected
supported/unsupported assertions, qualifiers, accounting basis, duplicate groups,
category/event/sign expectations and independent-event/availability constraints.
Replay points specify absolute aware timestamps. References, issuer consistency,
unique source IDs, bounds and replay names are validated.

The seed covers issuer-led revenue/EPS and preserved tariff-refund qualification;
NVDA-style GAAP tables and multi-anchor exhibits; deterioration and contraction;
mixed metrics; raise/cut/withdrawal; cyber, impairment, listing and bankruptcy;
duplicates, source precedence, factual contradictions, insignificant opposition;
future observations, stale evidence and expiry; extremes, cadence, dilution;
four meanings of Mixed; one/two/four/six-category coverage; revision relationships;
and correlated economic/market measurements. AAPL/NVDA-style fixtures are named
for structure only and use the synthetic ticker TEST. No ticker-specific code
branches or desired stock recommendations are encoded.

## Replay and operator entry point

From `backend`:

```powershell
.\venv\Scripts\python.exe -B -m app.cli.evaluate_outlook
.\venv\Scripts\python.exe -B -m app.cli.evaluate_outlook --verbose
.\venv\Scripts\python.exe -B -m app.cli.evaluate_outlook --case quarterly_cadence --json
```

`--corpus PATH` selects another validated corpus. The CLI writes to stdout only,
returns zero on success and nonzero for failed expectations, and never runs live
providers. JSON output includes versions, case/replay/check counts, mismatch kinds,
category support/direction/confidence, overall coverage, event/factor provenance,
exclusions, qualifiers in evidence basis, and unapplied relationship metadata.

`replay(package, assessment_at)` accepts an explicit timestamp, filters future
publication/observation before interpretation, parses frozen HTML where provided,
calls the production deterministic interpreter, then the production clustering,
freshness/category assessment and overall aggregation. No second scoring model,
system-clock patch, live data call or paid dependency is used. Offline tests block
socket connection attempts. Missing categories in this evidence-only replay are
insufficient; the harness does not pretend that synthetic Industry/Geopolitical
fixtures are configured production providers.

Each replay checks assertions, duplicate/independent-event expectations,
availability/coverage and arithmetic bounds. It also reruns ID-renaming and input
reversal invariants. Focused tests cover provider/headline ordering, harmless
reporting wording, duplicate-factor balance, symmetry, primary precedence,
future leakage and source provenance. This is lightweight enough for the normal
suite; verbose reports are optional. New real-source coverage will require human
review rather than inferring expectations from current output.

## Observed results and preserved calibration questions

* ID/order audit case: a .01-materiality opposing factor no longer suppresses the
  .8-materiality supported factor. At C=.9/F=1, event support is .72 in every order.
* AAPL-style revenue/EPS: one event with .72 publication support; frozen age
  48.4177415594 days gives approximately .341538 and remains insufficient.
* NVDA-style current/prior releases: four recognized metric observations form
  two releases. Ages 21.4241548922 and 119.4241548922 days give approximately
  .632027 combined support and remain insufficient. These are frozen regressions,
  not fresh live SEC verification.
* Mixed equally supported revenue up/margin down: one supported event with .72
  support and zero directional contribution; not a contradictory-duplicate error.
* Revenue/EPS each +1 at .72 support, margin -1 at .32 support: event support .72,
  effective impact (.72+.72-.32)/1.76, contribution approximately .458182.
* One perfect +2 or -2 event: support 1.0, still insufficient under two-event gate.

Quarterly releases exactly 90 days apart, C=.9/M=.8/impact=+1:

| Days after newer release | Eligible events | Support | Earnings |
| --- | ---: | ---: | --- |
| 0 | 2 | .900000 | Positive, available |
| 10 | 2 | .771520 | Positive, available |
| 15 | 2 | .714330 | Insufficient |
| 30 | 1 | .453572 | Insufficient |
| 60 | 1 | .285732 | Insufficient |

One earnings factor at day 119 has support .115153; at day 120 it is expired and
zero. The half-life and hard cutoff are unchanged.

The dilution case preserves three strong positives (support 2.16, directional
average .72, Positive), then four weak eligible positives (total approximately
2.32, average .331429, Mixed). The second replay is one second later so the weak
events can have later observation times; that tiny existing decay is retained.
The category formula remains sum(event contributions)/eligible event count.

Mixed cases carry separate semantic tags: neutral conditions, opposing events,
attenuated same-direction events, and category-level cancellation. User-facing
labels remain unchanged. Market-only, Company-only, Economic+Market and four
available categories produce partial overall coverage; all six synthetic
categories produce full coverage. No overall confidence formula was introduced.

## Revisions, correlation and limitations

The relationship schema retains original/subsequent IDs, reporting period, kind
(`amendment`, `correction`, `supersession`, `forecast_update`) and rationale. Replay
reports these but deliberately does not apply a supersession engine. The seed
uses equivalent original/corrected assertions to test representation. Future
changed-fact, withdrawn-guidance and effective-time fixtures remain needed.

FEDFUNDS/GS10 and combined SPY-QQQ trend/VIX fixtures demonstrate current separate
measurement counting. It is not proof of statistical independence. No correlation
penalty or macro sensitivity model was introduced.

Remaining limits: lexical event clustering can merge distinct nearby events or
miss differently worded cross-provider coverage; no universal event identity or
revision engine; unknown factor periods/bases are handled conservatively; numeric
conflict checks use explicit exact values, without reconciliation of rounding or
unit conversion; no new extraction formats or providers. Generic EPS and diluted
EPS remain distinct unless explicitly identified; true cross-format identity
requires future source-level semantics, not guessing.

Future expansion should add reviewed banks, energy, healthcare, consumer and
industrial disclosures, mature/growth/volatile issuers, genuine cross-format
duplicate reports, corrections and regulator events. Preserve publication versus
observation time, hold out issuers/formats, and test relative invariants rather
than tuning stock labels. The seed is not broad enough to calibrate financial
confidence, materiality or freshness numerically.

Unresolved calibration questions: event support max versus another bounded
combination; factor-confidence weighting; correlated measurements; quarterly
availability cadence; rare-event acknowledgment; count-based dilution; neutral
support; overall coverage weighting; empirical decay and materiality. Existing
thresholds and defaults remain unchanged pending that evidence.

## Visible behavior and files

Mixed financial releases can now remain eligible as one event; low-materiality
noise and arbitrary evidence IDs no longer choose their financial assessment.
Available-category explanations can list revenue, EPS and margin separately,
while evidence_count still counts the underlying release once. The existing
frontend renders these factors and source links without a UI change. Categories
may change legitimately for corrected mixed-factor cases; activation is not an
acceptance target. Unsupported/insufficient states remain honest.

Changed production files: `services/outlook_evidence.py` plus new
`services/outlook_factors.py`. New evaluation files: `models/outlook_evaluation.py`,
`services/outlook_evaluation.py`, `cli/evaluate_outlook.py`, and
`evaluation/outlook/v1.json`. Tests: new `tests/test_outlook_evaluation.py` and the
updated mixed-factor assertion in `tests/test_outlook_remediation.py`. This report
is the only documentation change.

No deployment, automatic commit, environment edit, paid API, LLM, Industry or
Geopolitical provider was introduced. Recommended next phase: independently
review and expand the corpus, particularly event identity and revisions, then
compare calibrated alternatives against held-out invariants and cases.

## Validation

Final full backend run: **529 passed, 46 skipped, 148 subtests passed** in about
13 seconds. The 58 new evaluation/regression tests include all corpus packages
and targeted metamorphic/semantic cases. Skips require an optional disposable
PostgreSQL target. Two existing FastAPI `on_event` deprecation warnings remain.

Corpus CLI: **34 cases, 48 historical replays, 394 checks passed, zero failures**.
Frontend: all four test scripts passed; lint and production build passed. The
existing greater-than-500-kB bundle warning remains. Diff/working-tree review and
`git diff --check` passed. No live network validation was required or performed
for this phase. Hosted acceptance and broader human-reviewed corpus certification
remain separate from this offline validation.

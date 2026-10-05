# Phase 3C.1: operator availability diagnostics

This change adds observability to `inspect_outlook` and `evaluate_outlook`.
No calibration values, freshness rules, interpreter defaults, event weighting,
category/overall formula, API response contract or frontend behavior changed.
The existing independent-event/support predicate is extracted verbatim into
`availability_failures` in the production evidence service. Production and the
diagnostic service call that same predicate; neither CLI implements its own gate.

## Fields and exact meanings

Every category reports:

* `supported_events`: eligible independent production clusters, not metrics.
* `source_observations`: normalized evidence records retained in those category
  clusters, including excluded/provenance-only records. This is not a count of
  unique publishers or downloaded documents. Future observations are excluded.
* `raw_support`: support before freshness decay for the currently eligible events
  and factors only. For multi-factor events it uses production `event_values`
  with each supported factor's decay removed, preserving the strongest-factor cap.
  Excluded or expired facts are not resurrected. It is not a sum of all metrics.
* `effective_support`: the production sum of eligible event weights, with decay;
  this is the value compared with minimum support.
* `minimum_support` and `minimum_events`: values from the same EvidencePolicy
  used for assessment (currently **0.75** and **2**).
* `freshest_event_age_days` / `oldest_event_age_days`: minimum/maximum age across
  supported events; an event uses the oldest authoritative publication among
  its contributing qualified factors/reports. This prevents syndication from
  making the diagnostic age younger. No supported events means null, not zero.
* `availability`: the actual category state.
* `reasons`: all failed count/support gates for insufficient categories plus
  applicable zero-evidence/exclusion explanations. Available categories have
  an empty reason list.
* `excluded_events`: counts of production exclusion codes, including in categories
  that still have supported events.

Raw and effective support are identical at full freshness; they differ after
decay. The illustrative request's minimum of .70 is not used: the current policy
still requires .75. No additional coverage requirement exists in the production
category gate, so no invented `coverage_requirement_not_met` code is emitted.

## Reasons

The shared gate emits `insufficient_independent_events` and/or
`support_below_threshold`. Equality passes both gates. Diagnostics also identify
`no_source_observations`, `all_evidence_stale` when every retained cluster has the
production expiry exclusion, and the actual cluster exclusion codes (such as
`low_confidence`, `low_materiality`, `provenance_only`, or
`conflicting_duplicate_interpretations`) when no supported events remain.
Not Material, provider unavailable/error and placeholder responses have separate
state explanations. Stale means reached the production age/explicit expiry cutoff;
future records have already been filtered and are not mislabeled stale.

## Consistent assessment clock

Live production responses do not include an assessment timestamp. Inspection
therefore reuses the fetched normalized evidence and reassesses it once at an
explicit completion timestamp through the production assessment/overall functions.
It does not refetch providers or alter their unavailable/error states. The printed
category result and diagnostic numbers consequently agree even at a hard expiry
boundary. This behavior is confined to tooling; application requests are unchanged.
Offline evaluation uses each existing frozen replay timestamp and its actual
production contributions without reassessment or wall-clock dependence.

## Usage and frozen examples

From `backend`:

```powershell
.\venv\Scripts\python.exe -B -m app.cli.inspect_outlook AAPL
.\venv\Scripts\python.exe -B -m app.cli.inspect_outlook NVDA --json
.\venv\Scripts\python.exe -B -m app.cli.evaluate_outlook --case nvda_style --verbose
.\venv\Scripts\python.exe -B -m app.cli.evaluate_outlook --case aapl_style --json
```

Inspection JSON retains the existing result fields and adds `assessment_at` and
`availability_diagnostics`. Evaluation JSON adds the same category diagnostics to
each replay. Verbose evaluation and normal inspection print six-decimal support,
counts, ages, state and explicit reasons for every category.

Frozen Phase 3C age regressions (not new live SEC requests):

| Earnings fixture | Events | Source observations | Raw | Effective | Reasons |
| --- | ---: | ---: | ---: | ---: | --- |
| AAPL style | 1 | 2 | .720000 | .341538 | insufficient_independent_events; support_below_threshold |
| NVDA style | 2 | 4 | 1.440000 | .632027 | support_below_threshold |

AAPL event age is approximately 48.418 days. NVDA event ages are approximately
21.424 and 119.424 days. Both use minimum support .75 and minimum events 2. These
are deterministic frozen examples; current live ages/counts may differ.

## Validation and files

All **347 relevant Outlook backend tests passed**. The unchanged offline corpus
passed **394 checks across 34 cases and 48 historical replays**. Regressions cover
multiple failed gates, exact boundaries, custom policy reuse, stale/future data,
duplicate observations, multi-factor support caps, Not Material/provider states,
inspection JSON, snapshot expiry boundaries, and AAPL/NVDA inspection/replay
agreement. Two existing FastAPI deprecation warnings remain.

Files: shared predicate in `services/outlook_evidence.py`; new
`services/outlook_diagnostics.py`; updates to `cli/inspect_outlook.py`,
`cli/evaluate_outlook.py`, and `services/outlook_evaluation.py`; new
`tests/test_outlook_diagnostics.py`; this report. Existing uncommitted Phase 3C
work is preserved. No calibration recommendation is encoded. No commit,
deployment, environment edit, or live provider fetch was performed for validation.

# Score cleanup: September 14, 2026

Trade Quality Score was removed before Outlook implementation. No replacement score was added.

## Component audit and decision

| Removed family | Former weight | Decision |
| --- | ---: | --- |
| Location | 30 | Support/resistance proximity and strength already exist in Technical Price Structure. Setup-specific breakout proximity and entry location are trade-planning concerns. Moving-average proximity rewarded entry placement rather than directional strength; do not migrate it. |
| Confirmation | 25 | Relative volume, RSI, and MACD-versus-signal already exist in Participation and Momentum. Remove duplicate, bullish-setup-gated scoring. |
| Risk/Reward | 20 | Entry, stop, target, reward/risk, and stop width evaluate a hypothetical trade. Remove from the score system. |
| Timing | 15 | Setup-stage points and moving-average extension describe early/late entries. RSI extension already exists in Momentum. Remove these duplicates and entry-timing judgments. |
| Confluence | 10 | Re-scores the preceding families as a generic aggregate. Remove. |

No metrics migrated. Technical Score remains version 2.0 with Trend 40, Momentum 30, Participation 15, and Price Structure 15. Its calculation, details, deterministic behavior, and 0–100 range are unchanged. Financial and Valuation calculations are unchanged. Trade Setup detection, its qualitative labels, trade-plan fields, and scanner eligibility filters are unchanged.

## API and scanner behavior

Removed analyzer calculation, five families, details helper, exclusive helpers, version/weight constants, deprecated calculation wrapper, `trade_quality_score` and `entry_score` response fields, and audit timings. Analyze routes return dictionaries; no dedicated response schema or database migration needed changing.

Scanner supports Technical, Financial, and Valuation priorities. Default selection changes from Technical plus Trade Quality to Technical alone. Explicit selections still use the arithmetic mean of available selected scores, preserving missing-data handling and alphabetical ties. The legacy no-priority path now sorts by Technical descending, then ticker, instead of Trade Quality then Technical then ticker. Removed score/grade fields and entry aliases from result objects. Invalid retired priority requests are rejected by existing validation. Restored frontend priorities are filtered to supported scores, falling back to Technical when a nonempty old selection has no supported scores left.

Removed dashboard card, scanner option/result badge, watchlist Q badge/state, response-validity requirement, and five breakdown labels/tooltips. Existing cards, collapsible behavior, and CSS are retained. The stack is Technical, Financial, Valuation.

## Files changed

- `backend/app/services/analyzer.py`, `backend/app/services/scanner.py`
- `frontend/src/App.jsx`, `frontend/src/components/ScannerPanel.jsx`, `frontend/src/components/Watchlist.jsx`
- `frontend/src/utils/analysisErrors.js`, `frontend/src/utils/scoreComponentConfig.js`
- `backend/tests/test_analysis_contract.py` (new), `test_scanner_audit.py`, `test_scanner_eligibility.py`, `test_scanner_ranking.py`, `test_technical_scoring.py`, `test_ticker_resolution_isolation.py`
- `frontend/tests/financial-score-panel.mjs`
- `README.md`, `backend/FINANCIAL_SCORING.md`, this report
- Deleted `backend/TRADE_QUALITY_SCORING.md` and `backend/tests/test_trade_quality_scoring.py`

## Validation and remaining references

The full pytest suite passed (195 passed, 46 skipped); the subsequently added HTTP contract test passed separately. PostgreSQL tests require a disposable target and were skipped. The initial unittest-discovery invocation reported pytest skips as errors; pytest correctly handles these tests. All tests used isolated databases, with the process database URL set to in-memory SQLite.

Frontend tests cover rendering of scanner results and watchlist without the removed fields, restored retired priorities, Technical details, and Financial/Valuation panels. Lint and production build passed; the existing large-bundle warning remains. HTTP analysis used deterministic fixture market data. Live provider behavior, interactive browser clicks, and browser console were not certified.

Remaining mentions are deliberate removal assertions, restored-preference regression fixtures, this report, and the historical timing in `SCANNER_PERFORMANCE_AUDIT.md`. Historical measurements and migrations were not rewritten. No active UI/API/calculation reference remains.

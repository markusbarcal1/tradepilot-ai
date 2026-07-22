# Technical scoring

`technical_score` uses technical score version `2.0`. It is the direct sum of four
capped signal families:

- Trend: 40 points (price, SMA20, and SMA50 alignment)
- Momentum: 30 points (RSI and MACD position)
- Participation: 15 points (relative volume)
- Price structure: 15 points (support and resistance location and strength)

The grade thresholds remain: Strong Bullish at 80, Bullish at 60, Neutral at
40, Bearish at 20, and Strong Bearish below 20. The legacy `score`, `grade`,
`positives`, and `negatives` fields remain available. Version `2.0` adds
`version` and a `components` object containing each family's score, cap, status,
reasons, and normalized inputs.

`trend_score` is temporarily emitted as a deprecated compatibility alias. It
references the same calculated result; the score is not calculated twice.

Missing or invalid family inputs produce an explicit `unavailable` status and
do not receive unreported neutral points. Version 1 and version 2 scores use
different calibration and must not be compared as though they were produced by
the same formula. Historical snapshots should retain their original score and
version rather than being overwritten with recalculated version 2 values.

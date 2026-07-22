# Trade quality scoring

`trade_quality_score` version `1.0` answers how attractive the currently
detected long trade is at the current price. It is the direct sum of five
independently capped families:

- Location: 30 points
- Confirmation: 25 points
- Risk / Reward: 20 points
- Timing: 15 points
- Confluence: 10 points

Location adapts to the existing `Breakout Watch`, `Pullback Bounce`, and
`Momentum Long` setup types. Confirmation uses relative volume, RSI, and MACD
position for the proposed entry. Risk / Reward validates the long entry, stop,
target, calculated ratio, and stop width. Timing uses setup stage, RSI, and
moving-average extension. Confluence counts aligned families rather than
individual correlated indicators.

Bearish and `No Clear Setup` states do not receive bullish trade-quality points.
Missing or invalid inputs remain visible through component status and reasons
and do not receive undisclosed neutral points.

`entry_score` is temporarily emitted as a deprecated compatibility alias. It
references the same calculated result; the score is not calculated twice.
Version `1.0` results should not be compared with historical Entry Score values
as though they used the same calibration.

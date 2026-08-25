import TradingChart from "./TradingChart";

function formatLastUpdated(value) {
  if (!value) return "Waiting for data";

  return new Date(value).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  });
}

function ChartPanel({
  analysis,
  positionAverageCost,
  positionShares,
  theme,
  timeframe,
  timeframes,
  lastUpdatedAt,
  chartResetKey,
  onTimeframeChange,
}) {
  return (
    <main className="center-panel">
      <div className="chart-box">
        <div className="chart-header">
          <div>
            <h3>{analysis.ticker} Candlestick Chart</h3>
            <span className="last-updated">
              Last updated {formatLastUpdated(lastUpdatedAt)}
            </span>
          </div>

          <div className="timeframe-buttons">
            {timeframes.map((tf) => (
              <button
                key={tf.label}
                className={
                  timeframe.label === tf.label
                    ? "timeframe active"
                    : "timeframe"
                }
                onClick={() => onTimeframeChange(tf)}
              >
                {tf.label}
              </button>
            ))}
          </div>
        </div>

        <TradingChart
          key={chartResetKey}
          data={analysis.chart_data}
          analysis={analysis}
          positionAverageCost={positionAverageCost}
          positionShares={positionShares}
          resetKey={chartResetKey}
          theme={theme}
        />

        <div className="legend">
          <span className="legend-blue">20 SMA</span>
          <span className="legend-yellow">50 SMA</span>
        </div>
      </div>
    </main>
  );
}

export default ChartPanel;

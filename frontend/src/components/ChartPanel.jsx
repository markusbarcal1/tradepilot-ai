import TradingChart from "./TradingChart";

function ChartPanel({
  analysis,
  timeframe,
  timeframes,
  onTimeframeChange,
}) {
  return (
    <main className="center-panel">
      <div className="chart-box">
        <div className="chart-header">
          <h3>{analysis.ticker} Candlestick Chart</h3>

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

        <TradingChart data={analysis.chart_data} analysis={analysis} />

        <div className="legend">
          <span className="legend-blue">20 SMA</span>
          <span className="legend-yellow">50 SMA</span>
        </div>
      </div>
    </main>
  );
}

export default ChartPanel;
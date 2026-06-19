import { useEffect, useState } from "react";

function ScannerPanel({ period, interval, onSelectTicker }) {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function fetchScanner() {
      setLoading(true);

      try {
        const res = await fetch(
          `http://localhost:8000/scan?period=${period}&interval=${interval}&limit=10`
        );

        const data = await res.json();
        setResults(data.results || []);
      } catch (err) {
        console.error("Scanner failed:", err);
        setResults([]);
      } finally {
        setLoading(false);
      }
    }

    fetchScanner();
  }, [period, interval]);

  return (
    <div className="scanner-panel">
      <div className="scanner-header">
        <h3>Bullish Scanner</h3>
        <span>{period} / {interval}</span>
      </div>

      {loading && <div className="scanner-empty">Scanning market...</div>}

      {!loading && results.length === 0 && (
        <div className="scanner-empty">
          No bullish setups found right now.
        </div>
      )}

      {!loading && results.map((stock) => (
        <div
          key={stock.ticker}
          className="scanner-card"
          onClick={() => onSelectTicker(stock.ticker)}
        >
          <div className="scanner-card-top">
            <strong>{stock.ticker}</strong>
            <span>${stock.price}</span>
          </div>

          <div className="scanner-scores">
            <span>Entry: {stock.entry_score}</span>
            <span>Trend: {stock.trend_score}</span>
          </div>

          <div className="scanner-setup">
            {stock.setup_type} · {stock.setup_quality}
          </div>

          <div className="scanner-trade-plan">
            Entry ${stock.entry} · Stop ${stock.stop} · Target ${stock.target}
          </div>

          <div className="scanner-risk">
            R/R: {stock.risk_reward}:1
          </div>
        </div>
      ))}
    </div>
  );
}

export default ScannerPanel;
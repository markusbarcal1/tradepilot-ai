import { useEffect, useRef, useState } from "react";
import { isRequestCanceled, scanMarket } from "../api/client";

function ScannerPanel({ period, interval, onSelectTicker }) {
  const scannerRequestRef = useRef(0);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const requestId = scannerRequestRef.current + 1;
    scannerRequestRef.current = requestId;

    async function fetchScanner() {
      setLoading(true);

      try {
        const response = await scanMarket(period, interval, 10, {
          signal: controller.signal,
        });

        if (scannerRequestRef.current !== requestId) return;

        setResults(response.data.results || []);
      } catch (err) {
        if (
          isRequestCanceled(err) ||
          scannerRequestRef.current !== requestId
        ) {
          return;
        }

        console.error("Scanner failed:", err);
        setResults([]);
      } finally {
        if (scannerRequestRef.current === requestId) {
          setLoading(false);
        }
      }
    }

    fetchScanner();

    return () => {
      controller.abort();
      scannerRequestRef.current += 1;
    };
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

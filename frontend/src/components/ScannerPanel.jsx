import { useEffect, useRef, useState } from "react";
import { isRequestCanceled, scanMarket } from "../api/client";

const SCANNER_UNIVERSES = [
  { value: "test", label: "Test" },
  { value: "mega_cap", label: "Mega Cap" },
  { value: "tech", label: "Tech" },
  { value: "semiconductors", label: "Semiconductors" },
  { value: "sp500_sample", label: "S&P 500 Sample" },
  { value: "sp500", label: "S&P 500" },
];

const DEFAULT_UNIVERSE = "test";
const DEFAULT_SCAN_LIMIT = 10;
const SP500_SCAN_SYMBOL_LIMIT = 100;
const STORAGE_KEY = "tradepilot-scanner-universe";

function getUniverseLabel(universe) {
  return (
    SCANNER_UNIVERSES.find((item) => item.value === universe)?.label ||
    universe
  );
}

function ScannerPanel({ period, interval, onSelectTicker }) {
  const scannerRequestRef = useRef(0);
  const [selectedUniverse, setSelectedUniverse] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return SCANNER_UNIVERSES.some((item) => item.value === saved)
      ? saved
      : DEFAULT_UNIVERSE;
  });
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const requestId = scannerRequestRef.current + 1;
    scannerRequestRef.current = requestId;

    async function fetchScanner() {
      setLoading(true);

      try {
        const response = await scanMarket(period, interval, DEFAULT_SCAN_LIMIT, {
          universe: selectedUniverse,
          maxSymbols:
            selectedUniverse === "sp500" ? SP500_SCAN_SYMBOL_LIMIT : undefined,
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
  }, [period, interval, selectedUniverse]);

  const handleUniverseChange = (event) => {
    const nextUniverse = event.target.value;

    setSelectedUniverse(nextUniverse);
    localStorage.setItem(STORAGE_KEY, nextUniverse);
  };

  return (
    <div className="scanner-panel">
      <div className="scanner-controls">
        <select
          value={selectedUniverse}
          onChange={handleUniverseChange}
          aria-label="Scanner universe"
        >
          {SCANNER_UNIVERSES.map((universe) => (
            <option key={universe.value} value={universe.value}>
              {universe.label}
            </option>
          ))}
        </select>
      </div>

      <div className="scanner-header">
        <h3>Bullish Scanner</h3>
        <span>{getUniverseLabel(selectedUniverse)} · {period} / {interval}</span>
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

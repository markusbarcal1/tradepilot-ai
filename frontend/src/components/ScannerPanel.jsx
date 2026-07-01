import { useEffect, useRef, useState } from "react";
import { isRequestCanceled, scanMarket } from "../api/client";

const SCANNER_TIMEFRAMES = [
  { label: "Daily", period: "1y", interval: "1d" },
  { label: "1h", period: "60d", interval: "1h" },
  { label: "30m", period: "60d", interval: "30m" },
  { label: "5m", period: "5d", interval: "5m" },
  { label: "1m", period: "1d", interval: "1m" },
];

const SCANNER_UNIVERSES = [
  { value: "test", label: "Test" },
  { value: "mega_cap", label: "Mega Cap" },
  { value: "tech", label: "Tech" },
  { value: "semiconductors", label: "Semiconductors" },
  { value: "sp500_sample", label: "S&P 500 Sample" },
  { value: "sp500", label: "S&P 500" },
];

const DEFAULT_UNIVERSE = "test";
const DEFAULT_TIMEFRAME = SCANNER_TIMEFRAMES[0];
const DEFAULT_SCAN_LIMIT = 10;
const SP500_SCAN_SYMBOL_LIMIT = 100;
const STORAGE_KEY = "tradepilot-scanner-state";

function getTimeframeByLabel(label) {
  return (
    SCANNER_TIMEFRAMES.find((item) => item.label === label) ||
    DEFAULT_TIMEFRAME
  );
}

function getStoredScannerState() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));

    if (!saved) return null;

    return {
      universe: SCANNER_UNIVERSES.some((item) => item.value === saved.universe)
        ? saved.universe
        : DEFAULT_UNIVERSE,
      timeframe: getTimeframeByLabel(saved.timeframeLabel),
      results: Array.isArray(saved.results) ? saved.results : [],
      metadata: saved.metadata || null,
      hasScanned: Boolean(saved.hasScanned),
    };
  } catch {
    return null;
  }
}

function getUniverseLabel(universe) {
  return (
    SCANNER_UNIVERSES.find((item) => item.value === universe)?.label ||
    universe
  );
}

function ScannerPanel({ onSelectTicker }) {
  const scannerRequestRef = useRef({ controller: null, id: 0 });
  const [selectedUniverse, setSelectedUniverse] = useState(() => {
    return getStoredScannerState()?.universe || DEFAULT_UNIVERSE;
  });
  const [selectedTimeframe, setSelectedTimeframe] = useState(() => {
    return getStoredScannerState()?.timeframe || DEFAULT_TIMEFRAME;
  });
  const [results, setResults] = useState(() => {
    return getStoredScannerState()?.results || [];
  });
  const [scanMetadata, setScanMetadata] = useState(() => {
    return getStoredScannerState()?.metadata || null;
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [hasScanned, setHasScanned] = useState(() => {
    return getStoredScannerState()?.hasScanned || false;
  });

  const runScanner = async () => {
    scannerRequestRef.current.controller?.abort();

    const controller = new AbortController();
    const requestId = scannerRequestRef.current.id + 1;
    scannerRequestRef.current = { controller, id: requestId };

    setLoading(true);
    setError("");
    setHasScanned(true);

    try {
      const response = await scanMarket(
        selectedTimeframe.period,
        selectedTimeframe.interval,
        DEFAULT_SCAN_LIMIT,
        {
          universe: selectedUniverse,
          maxSymbols:
            selectedUniverse === "sp500" ? SP500_SCAN_SYMBOL_LIMIT : undefined,
          signal: controller.signal,
        }
      );

      if (scannerRequestRef.current.id !== requestId) return;

      const nextResults = response.data.results || [];
      const nextMetadata = {
        universe: selectedUniverse,
        universeLabel: getUniverseLabel(selectedUniverse),
        timeframeLabel: selectedTimeframe.label,
        period: selectedTimeframe.period,
        interval: selectedTimeframe.interval,
        scannedAt: new Date().toISOString(),
      };

      setResults(nextResults);
      setScanMetadata(nextMetadata);
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          universe: selectedUniverse,
          timeframeLabel: selectedTimeframe.label,
          results: nextResults,
          metadata: nextMetadata,
          hasScanned: true,
        })
      );
    } catch (err) {
      if (
        isRequestCanceled(err) ||
        scannerRequestRef.current.id !== requestId
      ) {
        return;
      }

      console.error("Scanner failed:", err);
      setResults([]);
      setError("Scanner failed. Try a different timeframe or universe.");
    } finally {
      if (scannerRequestRef.current.id === requestId) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    return () => {
      scannerRequestRef.current.controller?.abort();
      scannerRequestRef.current.id += 1;
    };
  }, []);

  const handleUniverseChange = (event) => {
    const nextUniverse = event.target.value;

    setSelectedUniverse(nextUniverse);
  };

  const handleTimeframeChange = (event) => {
    const nextTimeframe =
      SCANNER_TIMEFRAMES.find((item) => item.label === event.target.value) ||
      DEFAULT_TIMEFRAME;

    setSelectedTimeframe(nextTimeframe);
  };

  const displayUniverseLabel =
    scanMetadata?.universeLabel || getUniverseLabel(selectedUniverse);
  const displayTimeframeLabel =
    scanMetadata?.timeframeLabel || selectedTimeframe.label;

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

        <select
          value={selectedTimeframe.label}
          onChange={handleTimeframeChange}
          aria-label="Scanner timeframe"
        >
          {SCANNER_TIMEFRAMES.map((timeframe) => (
            <option key={timeframe.label} value={timeframe.label}>
              {timeframe.label}
            </option>
          ))}
        </select>

        <button type="button" onClick={runScanner} disabled={loading}>
          {loading ? "Scanning..." : "Scan"}
        </button>
      </div>

      <div className="scanner-header">
        <h3>Bullish Scanner</h3>
        <span>{displayUniverseLabel} · {displayTimeframeLabel}</span>
      </div>

      {loading && <div className="scanner-empty">Scanning market...</div>}

      {!loading && error && <div className="scanner-empty">{error}</div>}

      {!loading && !error && !hasScanned && (
        <div className="scanner-empty">
          Choose filters, then click Scan.
        </div>
      )}

      {!loading && !error && hasScanned && results.length === 0 && (
        <div className="scanner-empty">
          No bullish setups found right now.
        </div>
      )}

      {!loading && !error && results.map((stock) => (
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
            Entry ${stock.entry} · Stop ${stock.stop} · Target ${stock.target} ·
            R/R {stock.risk_reward}:1
          </div>
        </div>
      ))}
    </div>
  );
}

export default ScannerPanel;

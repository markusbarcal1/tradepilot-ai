import { useEffect, useRef, useState } from "react";
import { isRequestCanceled, streamScanMarket } from "../api/client";

const SCANNER_TIMEFRAMES = [
  { label: "Daily", period: "1y", interval: "1d" },
  { label: "1h", period: "60d", interval: "1h" },
  { label: "30m", period: "60d", interval: "30m" },
  { label: "5m", period: "5d", interval: "5m" },
  { label: "1m", period: "1d", interval: "1m" },
];

const SCANNER_UNIVERSES = [
  { value: "sp500", label: "S&P 500" },
  { value: "nasdaq", label: "Nasdaq" },
];

const DEFAULT_UNIVERSE = "sp500";
const DEFAULT_TIMEFRAME = SCANNER_TIMEFRAMES[0];
const DEFAULT_SCAN_LIMIT = 10;

function getTimeframeByLabel(label) {
  return (
    SCANNER_TIMEFRAMES.find((item) => item.label === label) ||
    DEFAULT_TIMEFRAME
  );
}

function getUniverseLabel(universe) {
  return (
    SCANNER_UNIVERSES.find((item) => item.value === universe)?.label ||
    universe
  );
}

function getInitialScannerState(savedState) {
  if (!savedState) return null;

  return {
    universe: SCANNER_UNIVERSES.some((item) => item.value === savedState.universe)
      ? savedState.universe
      : DEFAULT_UNIVERSE,
    timeframe: getTimeframeByLabel(savedState.timeframeLabel),
    results: Array.isArray(savedState.results) ? savedState.results : [],
    metadata: savedState.metadata || null,
    hasScanned: Boolean(savedState.hasScanned),
  };
}

function ScannerPanel({ savedState, onStateChange, onSelectTicker }) {
  const scannerRequestRef = useRef({ controller: null, id: 0 });
  const initialState = getInitialScannerState(savedState);
  const [selectedUniverse, setSelectedUniverse] = useState(() => {
    return initialState?.universe || DEFAULT_UNIVERSE;
  });
  const [selectedTimeframe, setSelectedTimeframe] = useState(() => {
    return initialState?.timeframe || DEFAULT_TIMEFRAME;
  });
  const [results, setResults] = useState(() => {
    return initialState?.results || [];
  });
  const [scanMetadata, setScanMetadata] = useState(() => {
    return initialState?.metadata || null;
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [scanProgress, setScanProgress] = useState(null);
  const [hasScanned, setHasScanned] = useState(() => {
    return initialState?.hasScanned || false;
  });

  const runScanner = async () => {
    scannerRequestRef.current.controller?.abort();

    const controller = new AbortController();
    const requestId = scannerRequestRef.current.id + 1;
    scannerRequestRef.current = { controller, id: requestId };

    setLoading(true);
    setError("");
    setScanProgress(null);
    setHasScanned(true);

    try {
      const scanOptions = {
        universe: selectedUniverse,
        signal: controller.signal,
      };
      const responseData = await streamScanMarket(
        selectedTimeframe.period,
        selectedTimeframe.interval,
        DEFAULT_SCAN_LIMIT,
        scanOptions,
        ({ event, data }) => {
          if (scannerRequestRef.current.id !== requestId) return;

          if (
            (event === "start" || event === "progress") &&
            Number.isFinite(data?.scanned) &&
            Number.isFinite(data?.total)
          ) {
            setScanProgress({
              scanned: data.scanned,
              total: data.total,
              failed: data.failed || 0,
            });
          }
        }
      );

      if (scannerRequestRef.current.id !== requestId) return;

      const nextResults = responseData.results || [];
      const nextMetadata = {
        universe: selectedUniverse,
        universeLabel: getUniverseLabel(selectedUniverse),
        timeframeLabel: selectedTimeframe.label,
        period: selectedTimeframe.period,
        interval: selectedTimeframe.interval,
        scannedCount: responseData.scanned_count,
        maxSymbols: responseData.max_symbols,
        errorCount: responseData.error_count,
        scannedAt: new Date().toISOString(),
      };

      setResults(nextResults);
      setError("");
      setScanMetadata(nextMetadata);
      setScanProgress(null);
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
      setScanProgress(null);
    } finally {
      if (scannerRequestRef.current.id === requestId) {
        setLoading(false);
        setScanProgress(null);
      }
    }
  };

  useEffect(() => {
    return () => {
      scannerRequestRef.current.controller?.abort();
      scannerRequestRef.current.id += 1;
    };
  }, []);

  useEffect(() => {
    onStateChange({
      universe: selectedUniverse,
      timeframeLabel: selectedTimeframe.label,
      results,
      metadata: scanMetadata,
      hasScanned,
    });
  }, [
    selectedUniverse,
    selectedTimeframe,
    results,
    scanMetadata,
    hasScanned,
    onStateChange,
  ]);

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
  const scannedCountLabel =
    Number.isFinite(scanMetadata?.scannedCount)
      ? ` · ${scanMetadata.scannedCount} scanned`
      : "";
  const failedCountLabel =
    Number.isFinite(scanMetadata?.errorCount) && scanMetadata.errorCount > 0
      ? ` · ${scanMetadata.errorCount} failed`
      : "";
  const loadingScanLabel =
    Number.isFinite(scanProgress?.scanned) && Number.isFinite(scanProgress?.total)
      ? `Scanning ${scanProgress.scanned}/${scanProgress.total} symbols${
          scanProgress.failed ? ` · ${scanProgress.failed} failed` : ""
        }`
      : "Scanning market...";

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

        <button type="button" onClick={() => runScanner()} disabled={loading}>
          {loading ? "Scanning..." : "Scan"}
        </button>
      </div>

      <div className="scanner-header">
        <h3>Bullish Scanner</h3>
        <span>
          {displayUniverseLabel} · {displayTimeframeLabel}{scannedCountLabel}
          {failedCountLabel}
        </span>
      </div>

      {loading && <div className="scanner-empty">{loadingScanLabel}</div>}

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
            <span>Quality: {stock.trade_quality_score ?? stock.entry_score}</span>
            <span>Technical: {stock.technical_score}</span>
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

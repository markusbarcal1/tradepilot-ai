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
const SCANNER_FILTERS_STORAGE_KEY = "tradepilot-scanner-filters";
const DEFAULT_ELIGIBILITY = {
  minimumHistoryBars: 100,
  excludeEtfs: true,
  excludeLeveragedInverse: true,
  excludeVolatilityProducts: true,
  excludeWarrantsRightsUnits: true,
  excludePreferredShares: true,
  excludeBlankCheckCompanies: true,
};

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
  const persistedState = (() => {
    try {
      return JSON.parse(
        localStorage.getItem(SCANNER_FILTERS_STORAGE_KEY) || "null"
      );
    } catch {
      return null;
    }
  })();

  const state = { ...(persistedState || {}), ...(savedState || {}) };
  if (!Object.keys(state).length) return null;

  return {
    universe: SCANNER_UNIVERSES.some((item) => item.value === state.universe)
      ? state.universe
      : DEFAULT_UNIVERSE,
    timeframe: getTimeframeByLabel(state.timeframeLabel),
    results: Array.isArray(state.results) ? state.results : [],
    metadata: state.metadata || null,
    hasScanned: Boolean(state.hasScanned),
    eligibilityEnabled: state.eligibilityEnabled !== false,
    minimumPrice: Number.isFinite(state.minimumPrice) ? state.minimumPrice : 5,
    minimumVolume: Number.isFinite(state.minimumVolume) ? state.minimumVolume : 500000,
    minimumHistoryBars: Number.isFinite(state.minimumHistoryBars) ? state.minimumHistoryBars : DEFAULT_ELIGIBILITY.minimumHistoryBars,
    excludeEtfs: state.excludeEtfs !== false,
    excludeLeveragedInverse: state.excludeLeveragedInverse !== false,
    excludeVolatilityProducts: state.excludeVolatilityProducts !== false,
    excludeWarrantsRightsUnits: state.excludeWarrantsRightsUnits !== false,
    excludePreferredShares: state.excludePreferredShares !== false,
    excludeBlankCheckCompanies: state.excludeBlankCheckCompanies !== false,
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
  const [eligibilityEnabled, setEligibilityEnabled] = useState(() => {
    return initialState?.eligibilityEnabled !== false;
  });
  const [minimumPrice, setMinimumPrice] = useState(() => {
    return initialState?.minimumPrice ?? 5;
  });
  const [minimumVolume, setMinimumVolume] = useState(() => {
    return initialState?.minimumVolume ?? 500000;
  });
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [minimumHistoryBars, setMinimumHistoryBars] = useState(
    () => initialState?.minimumHistoryBars ?? DEFAULT_ELIGIBILITY.minimumHistoryBars
  );
  const [excludeEtfs, setExcludeEtfs] = useState(
    () => initialState?.excludeEtfs ?? DEFAULT_ELIGIBILITY.excludeEtfs
  );
  const [excludeLeveragedInverse, setExcludeLeveragedInverse] = useState(
    () => initialState?.excludeLeveragedInverse ?? DEFAULT_ELIGIBILITY.excludeLeveragedInverse
  );
  const [excludeVolatilityProducts, setExcludeVolatilityProducts] = useState(
    () => initialState?.excludeVolatilityProducts ?? DEFAULT_ELIGIBILITY.excludeVolatilityProducts
  );
  const [excludeWarrantsRightsUnits, setExcludeWarrantsRightsUnits] = useState(
    () => initialState?.excludeWarrantsRightsUnits ?? DEFAULT_ELIGIBILITY.excludeWarrantsRightsUnits
  );
  const [excludePreferredShares, setExcludePreferredShares] = useState(
    () => initialState?.excludePreferredShares ?? DEFAULT_ELIGIBILITY.excludePreferredShares
  );
  const [excludeBlankCheckCompanies, setExcludeBlankCheckCompanies] = useState(
    () => initialState?.excludeBlankCheckCompanies ?? DEFAULT_ELIGIBILITY.excludeBlankCheckCompanies
  );

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
        eligibility: {
          enabled: eligibilityEnabled,
          minimum_price: Number(minimumPrice) || 5,
          minimum_average_volume: Number(minimumVolume) || 500000,
          minimum_history_bars: Number(minimumHistoryBars) || 100,
          exclude_etfs: excludeEtfs,
          exclude_leveraged_etfs: excludeLeveragedInverse,
          exclude_inverse_etfs: excludeLeveragedInverse,
          exclude_volatility_products: excludeVolatilityProducts,
          exclude_warrants: excludeWarrantsRightsUnits,
          exclude_rights: excludeWarrantsRightsUnits,
          exclude_units: excludeWarrantsRightsUnits,
          exclude_preferred_shares: excludePreferredShares,
          exclude_blank_check_companies: excludeBlankCheckCompanies,
        },
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
        eligibilitySummary: responseData.audit?.eligibility || null,
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
    localStorage.setItem(SCANNER_FILTERS_STORAGE_KEY, JSON.stringify({
      universe: selectedUniverse,
      timeframeLabel: selectedTimeframe.label,
      eligibilityEnabled,
      minimumPrice: Number(minimumPrice),
      minimumVolume: Number(minimumVolume),
      minimumHistoryBars: Number(minimumHistoryBars),
      excludeEtfs,
      excludeLeveragedInverse,
      excludeVolatilityProducts,
      excludeWarrantsRightsUnits,
      excludePreferredShares,
      excludeBlankCheckCompanies,
    }));
  }, [
    selectedUniverse,
    selectedTimeframe,
    eligibilityEnabled,
    minimumPrice,
    minimumVolume,
    minimumHistoryBars,
    excludeEtfs,
    excludeLeveragedInverse,
    excludeVolatilityProducts,
    excludeWarrantsRightsUnits,
    excludePreferredShares,
    excludeBlankCheckCompanies,
  ]);

  useEffect(() => {
    onStateChange({
      universe: selectedUniverse,
      timeframeLabel: selectedTimeframe.label,
      results,
      metadata: scanMetadata,
      hasScanned,
      eligibilityEnabled,
      minimumPrice,
      minimumVolume,
      minimumHistoryBars,
      excludeEtfs,
      excludeLeveragedInverse,
      excludeVolatilityProducts,
      excludeWarrantsRightsUnits,
      excludePreferredShares,
      excludeBlankCheckCompanies,
    });
  }, [
    selectedUniverse,
    selectedTimeframe,
    results,
    scanMetadata,
    hasScanned,
    eligibilityEnabled,
    minimumPrice,
    minimumVolume,
    minimumHistoryBars,
    excludeEtfs,
    excludeLeveragedInverse,
    excludeVolatilityProducts,
    excludeWarrantsRightsUnits,
    excludePreferredShares,
    excludeBlankCheckCompanies,
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

  const displayUniverseLabel = getUniverseLabel(selectedUniverse);
  const displayTimeframeLabel = selectedTimeframe.label;
  const loadingScanLabel =
    Number.isFinite(scanProgress?.scanned) && Number.isFinite(scanProgress?.total)
      ? `Scanning ${scanProgress.scanned}/${scanProgress.total} symbols${
          scanProgress.failed ? ` · ${scanProgress.failed} failed` : ""
        }`
      : "Scanning market...";
  const eligibilitySummary = scanMetadata?.eligibilitySummary;
  const eligibilityControls = [
    ["Exclude ETFs", excludeEtfs, setExcludeEtfs],
    ["Exclude leveraged and inverse products", excludeLeveragedInverse, setExcludeLeveragedInverse],
    ["Exclude volatility products", excludeVolatilityProducts, setExcludeVolatilityProducts],
    ["Exclude warrants, rights, and units", excludeWarrantsRightsUnits, setExcludeWarrantsRightsUnits],
    ["Exclude preferred shares", excludePreferredShares, setExcludePreferredShares],
    ["Exclude blank-check companies", excludeBlankCheckCompanies, setExcludeBlankCheckCompanies],
  ];

  return (
    <div className="scanner-panel">
      <div className="scanner-header">
        <h3>Bullish Scanner</h3>
        <span>Find technically strong trade candidates</span>
      </div>

      <div className="scanner-primary-controls">
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
      </div>

      <div className="scanner-filter-section">
        <label className="scanner-toggle-row">
          <span className="scanner-toggle-copy">
            <span className="scanner-toggle-title">Eligibility Filters</span>
            <span className="scanner-toggle-subtitle">Exclude low-price and low-volume securities</span>
          </span>
          <input
            className="scanner-toggle-input"
            type="checkbox"
            checked={eligibilityEnabled}
            onChange={(event) => setEligibilityEnabled(event.target.checked)}
            aria-label="Enable eligibility filters"
          />
          <span className="scanner-toggle-switch" aria-hidden="true" />
        </label>

        <button type="button" className="scanner-advanced-toggle"
          onClick={() => setAdvancedOpen((open) => !open)}
          aria-expanded={advancedOpen}>
          <span>Advanced Filters</span>
          <span aria-hidden="true">{advancedOpen ? "⌄" : "›"}</span>
        </button>
        {advancedOpen && (
          <div className="scanner-advanced-content">
            <div className="scanner-eligibility-inputs">
              <label className="scanner-field">
                <span>Minimum Price</span>
                <span className="scanner-input-prefix">
                  <span>$</span>
                  <input type="number" min="0" step="1" value={minimumPrice}
                    onChange={(event) => setMinimumPrice(event.target.value)}
                    disabled={!eligibilityEnabled} />
                </span>
              </label>
              <label className="scanner-field">
                <span>Minimum Avg Volume</span>
                <input type="number" min="0" step="1000" value={minimumVolume}
                  onChange={(event) => setMinimumVolume(event.target.value)}
                  disabled={!eligibilityEnabled} />
              </label>
            </div>
            {eligibilityControls.map(([label, checked, setter]) => (
              <label className="scanner-check-row" key={label}>
                <input type="checkbox" checked={checked}
                  onChange={(event) => setter(event.target.checked)}
                  disabled={!eligibilityEnabled} />
                <span>{label}</span>
              </label>
            ))}
            <label className="scanner-field scanner-history-field">
              <span>Minimum history bars</span>
              <input type="number" min="1" step="1" value={minimumHistoryBars}
                onChange={(event) => setMinimumHistoryBars(event.target.value)}
                disabled={!eligibilityEnabled} />
            </label>
          </div>
        )}
      </div>

      <button className="scanner-scan-button" type="button" onClick={runScanner} disabled={loading}>
        {loading ? "Scanning…" : "Scan Market"}
      </button>

      <div className="scanner-context">
        {displayUniverseLabel} · {displayTimeframeLabel} · Eligibility {eligibilityEnabled ? "enabled" : "disabled"}
      </div>

      {loading && <div className="scanner-empty">{loadingScanLabel}</div>}

      {!loading && error && <div className="scanner-empty">{error}</div>}

      {!loading && !error && !hasScanned && (
        <div className="scanner-empty">
          Choose your filters and scan for bullish opportunities.
        </div>
      )}

      {!loading && !error && hasScanned && results.length === 0 && (
        <div className="scanner-empty">
          No qualifying bullish setups were found.
          <span>Try lowering the eligibility thresholds or changing the timeframe.</span>
        </div>
      )}

      {!loading && !error && eligibilitySummary && (
        <div className="scanner-summary">
          {eligibilitySummary.symbols_checked || scanMetadata?.scannedCount || 0} scanned ·{" "}
          {eligibilitySummary.symbols_eligible || 0} eligible ·{" "}
          {eligibilitySummary.symbols_excluded || 0} excluded
          <span>{results.length} bullish {results.length === 1 ? "setup" : "setups"} found</span>
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

import { useEffect, useRef, useState } from "react";
import { isRequestCanceled, streamScanMarket } from "../api/client";
import { getScoreColorClass } from "../utils/scoreColors";

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
const SCORING_OPTIONS = [
  { id: "technical", label: "Technical" },
  { id: "trade_quality", label: "Trade Quality" },
  { id: "financial", label: "Financial" },
  { id: "valuation", label: "Valuation" },
];
const DEFAULT_SCORING_PRIORITIES = ["technical", "trade_quality"];
const DEFAULT_ELIGIBILITY = {
  minimumPrice: 5,
  minimumVolume: 500000,
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
  const state = { ...(savedState || {}) };
  if (!Object.keys(state).length) return null;

  const scoringPriorities = Array.isArray(state.scoringPriorities)
    ? state.scoringPriorities.filter((value) =>
        SCORING_OPTIONS.some((option) => option.id === value)
      )
    : DEFAULT_SCORING_PRIORITIES;

  return {
    universe: SCANNER_UNIVERSES.some((item) => item.value === state.universe)
      ? state.universe
      : DEFAULT_UNIVERSE,
    timeframe: getTimeframeByLabel(state.timeframeLabel),
    results: Array.isArray(state.results) ? state.results : [],
    metadata: state.metadata || null,
    hasScanned: Boolean(state.hasScanned),
    scoringPriorities,
    eligibilityEnabled: state.eligibilityEnabled !== false,
    minimumPrice: Number.isFinite(state.minimumPrice) ? state.minimumPrice : DEFAULT_ELIGIBILITY.minimumPrice,
    minimumVolume: Number.isFinite(state.minimumVolume) ? state.minimumVolume : DEFAULT_ELIGIBILITY.minimumVolume,
    minimumHistoryBars: Number.isFinite(state.minimumHistoryBars) ? state.minimumHistoryBars : DEFAULT_ELIGIBILITY.minimumHistoryBars,
    excludeEtfs: state.excludeEtfs !== false,
    excludeLeveragedInverse: state.excludeLeveragedInverse !== false,
    excludeVolatilityProducts: state.excludeVolatilityProducts !== false,
    excludeWarrantsRightsUnits: state.excludeWarrantsRightsUnits !== false,
    excludePreferredShares: state.excludePreferredShares !== false,
    excludeBlankCheckCompanies: state.excludeBlankCheckCompanies !== false,
  };
}

function ScannerPanel({
  savedState,
  onStateChange,
  onPreferencesChange,
  onSelectTicker,
}) {
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
  const [scoringPriorities, setScoringPriorities] = useState(() => {
    return initialState?.scoringPriorities || DEFAULT_SCORING_PRIORITIES;
  });
  const [eligibilityEnabled, setEligibilityEnabled] = useState(() => {
    return initialState?.eligibilityEnabled !== false;
  });
  const [minimumPrice, setMinimumPrice] = useState(() => {
    return initialState?.minimumPrice ?? DEFAULT_ELIGIBILITY.minimumPrice;
  });
  const [minimumVolume, setMinimumVolume] = useState(() => {
    return initialState?.minimumVolume ?? DEFAULT_ELIGIBILITY.minimumVolume;
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
    if (!scoringPriorities.length) {
      setError("Select at least one scoring priority before scanning.");
      setScanProgress(null);
      return;
    }

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
        scores: scoringPriorities,
        eligibility: {
          enabled: eligibilityEnabled,
          minimum_price: Number(minimumPrice) || DEFAULT_ELIGIBILITY.minimumPrice,
          minimum_average_volume: Number(minimumVolume) || DEFAULT_ELIGIBILITY.minimumVolume,
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
    onPreferencesChange({
      universe: selectedUniverse,
      timeframeLabel: selectedTimeframe.label,
      scoringPriorities,
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
    });
  }, [
    selectedUniverse,
    selectedTimeframe,
    scoringPriorities,
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
    onPreferencesChange,
  ]);

  useEffect(() => {
    onStateChange({
      universe: selectedUniverse,
      timeframeLabel: selectedTimeframe.label,
      results,
      metadata: scanMetadata,
      hasScanned,
      scoringPriorities,
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
    scoringPriorities,
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

  const handleScoringPriorityChange = (scoreId) => {
    setScoringPriorities((current) => {
      if (current.includes(scoreId)) {
        return current.filter((value) => value !== scoreId);
      }
      return [...current, scoreId];
    });
    setError("");
  };

  const resetEligibilityFilters = () => {
    setMinimumPrice(DEFAULT_ELIGIBILITY.minimumPrice);
    setMinimumVolume(DEFAULT_ELIGIBILITY.minimumVolume);
    setMinimumHistoryBars(DEFAULT_ELIGIBILITY.minimumHistoryBars);
    setExcludeEtfs(DEFAULT_ELIGIBILITY.excludeEtfs);
    setExcludeLeveragedInverse(DEFAULT_ELIGIBILITY.excludeLeveragedInverse);
    setExcludeVolatilityProducts(DEFAULT_ELIGIBILITY.excludeVolatilityProducts);
    setExcludeWarrantsRightsUnits(DEFAULT_ELIGIBILITY.excludeWarrantsRightsUnits);
    setExcludePreferredShares(DEFAULT_ELIGIBILITY.excludePreferredShares);
    setExcludeBlankCheckCompanies(DEFAULT_ELIGIBILITY.excludeBlankCheckCompanies);
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
        <h3>Opportunity Scanner</h3>
        <span>Find strong trade opportunities</span>
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

      <div className="scanner-filter-section scanner-priorities-section">
        <span className="scanner-toggle-title">Scoring Priorities</span>
        <span className="scanner-toggle-subtitle">Choose scores used to rank eligible results</span>
        <div className="scanner-priority-grid">
          {SCORING_OPTIONS.map((option) => (
            <label className="scanner-check-row" key={option.id}>
              <input
                type="checkbox"
                checked={scoringPriorities.includes(option.id)}
                onChange={() => handleScoringPriorityChange(option.id)}
              />
              <span>{option.label}</span>
            </label>
          ))}
        </div>
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
            <button
              type="button"
              className="scanner-reset-filters"
              onClick={resetEligibilityFilters}
            >
              Reset to Defaults
            </button>
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

      {!loading && error && <div className="scanner-empty" role="alert">{error}</div>}

      {!loading && !error && !hasScanned && (
        <div className="scanner-empty">
          Choose your filters and scan for trade opportunities.
        </div>
      )}

      {!loading && !error && hasScanned && results.length === 0 && (
        <div className="scanner-empty">
          No qualifying opportunities were found.
          <span>Try lowering the eligibility thresholds or changing the timeframe.</span>
        </div>
      )}

      {!loading && !error && eligibilitySummary && (
        <div className="scanner-summary">
          {eligibilitySummary.symbols_checked || scanMetadata?.scannedCount || 0} scanned ·{" "}
          {eligibilitySummary.symbols_eligible || 0} eligible ·{" "}
          {eligibilitySummary.symbols_excluded || 0} excluded
          <span>{results.length} {results.length === 1 ? "opportunity" : "opportunities"} found</span>
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
            <span className={getScoreColorClass(stock.scanner_score)}>
              Scanner: {stock.scanner_score ?? "N/A"}
              {stock.scanner_score_available_components < stock.scanner_score_selected_components
                ? ` · ${stock.scanner_score_available_components}/${stock.scanner_score_selected_components} scores`
                : ""}
            </span>
            <span className={getScoreColorClass(stock.technical_score)}>
              Technical: {stock.technical_score ?? "N/A"}
            </span>
            <span className={getScoreColorClass(stock.trade_quality_score ?? stock.entry_score)}>
              Quality: {stock.trade_quality_score ?? stock.entry_score ?? "N/A"}
            </span>
            <span className={getScoreColorClass(stock.financial_score)}>
              Financial: {stock.financial_score ?? "N/A"}
            </span>
            <span className={getScoreColorClass(stock.valuation_score)}>
              Valuation: {stock.valuation_score ?? "N/A"}
            </span>
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

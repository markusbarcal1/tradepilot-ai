import { useEffect, useRef, useState } from "react";
import {
  analyzeTicker as fetchAnalysis,
  analyzeTickers as fetchBatchAnalysis,
  isRequestCanceled,
  validateTicker,
} from "./api/client";
import Header from "./components/Header";
import MetricsPanel from "./components/MetricsPanel";
import ChartPanel from "./components/ChartPanel";
import ThesisPanel from "./components/ThesisPanel";
import ScorePanel from "./components/ScorePanel";
import SetupPanel from "./components/SetupPanel";
import QuickTradePanel from "./components/QuickTradePanel";
import PaperPortfolioSummary from "./components/PaperPortfolioSummary";
import PortfolioPage from "./components/PortfolioPage";
import Watchlist from "./components/Watchlist";
import ScannerPanel from "./components/ScannerPanel";
import { getPaperPortfolio } from "./api/paperTrading";
import "./App.css";

const TIMEFRAMES = [
  { label: "Monthly", period: "10y", interval: "1mo" },
  { label: "Weekly", period: "5y", interval: "1wk" },
  { label: "Daily", period: "1y", interval: "1d" },
  { label: "1h", period: "60d", interval: "1h" },
  { label: "30m", period: "60d", interval: "30m" },
  { label: "5m", period: "5d", interval: "5m" },
  { label: "1m", period: "1d", interval: "1m" },
];

const DEFAULT_WATCHLIST = [
  "AAPL",
  "NVDA",
  "AMD",
  "META",
  "MSFT",
  "PLTR",
  "TSLA",
];

function App() {
  const analysisRequestRef = useRef({ controller: null, id: 0 });
  const validationRequestRef = useRef({ controller: null, id: 0 });
  const watchlistRequestRef = useRef({ controller: null, id: 0 });

  const [ticker, setTicker] = useState("AAPL");
  const [submittedTicker, setSubmittedTicker] = useState("AAPL");
  const [timeframe, setTimeframe] = useState(TIMEFRAMES[2]);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [currentView, setCurrentView] = useState("dashboard");

  const [watchlist, setWatchlist] = useState(() => {
    const saved = localStorage.getItem("tradepilot-watchlist");
    return saved ? JSON.parse(saved) : DEFAULT_WATCHLIST;
  });

  const [watchlistScores, setWatchlistScores] = useState({});
  const [watchlistError, setWatchlistError] = useState("");
  const [addingTicker, setAddingTicker] = useState(false);
  const [paperPortfolio, setPaperPortfolio] = useState(null);
  const [paperPortfolioLoading, setPaperPortfolioLoading] = useState(false);
  const [paperPortfolioError, setPaperPortfolioError] = useState("");

  const showWatchlistError = (message) => {
    setWatchlistError(message);

    setTimeout(() => {
      setWatchlistError("");
    }, 2500);
  };

  const analyzeTicker = async (
    symbol = submittedTicker,
    selectedTimeframe = timeframe
  ) => {
    analysisRequestRef.current.controller?.abort();

    const controller = new AbortController();
    const requestId = analysisRequestRef.current.id + 1;
    analysisRequestRef.current = { controller, id: requestId };

    setLoading(true);
    setError("");

    try {
      const response = await fetchAnalysis(
        symbol,
        selectedTimeframe.period,
        selectedTimeframe.interval,
        { signal: controller.signal }
      );

      if (analysisRequestRef.current.id !== requestId) return;

      setAnalysis(response.data);
    } catch (err) {
      if (
        isRequestCanceled(err) ||
        analysisRequestRef.current.id !== requestId
      ) {
        return;
      }

      console.error(err);
      setAnalysis(null);
      setError(
        "Could not analyze ticker. Check the symbol, interval, or backend server."
      );
    } finally {
      if (analysisRequestRef.current.id === requestId) {
        setLoading(false);
      }
    }
  };

  const refreshWatchlistScores = async (
    selectedTimeframe = timeframe,
    symbols = watchlist
  ) => {
    watchlistRequestRef.current.controller?.abort();

    const controller = new AbortController();
    const requestId = watchlistRequestRef.current.id + 1;
    watchlistRequestRef.current = { controller, id: requestId };

    if (symbols.length === 0) {
      setWatchlistScores({});
      return;
    }

    try {
      const response = await fetchBatchAnalysis(
        symbols,
        selectedTimeframe.period,
        selectedTimeframe.interval,
        { signal: controller.signal }
      );

      const scoreMap = {};

      (response.data.results || []).forEach((item) => {
        scoreMap[item.ticker] = {
          trend: item.trend_score?.score,
          entry: item.entry_score?.score,
        };
      });

      if (watchlistRequestRef.current.id !== requestId) return;

      setWatchlistScores(scoreMap);
    } catch (err) {
      if (
        isRequestCanceled(err) ||
        watchlistRequestRef.current.id !== requestId
      ) {
        return;
      }

      console.error("Could not refresh watchlist scores:", err);
    }
  };

  const refreshPaperPortfolio = async () => {
    setPaperPortfolioLoading(true);
    setPaperPortfolioError("");

    try {
      const response = await getPaperPortfolio();

      setPaperPortfolio(response.data);
    } catch (err) {
      console.error("Could not refresh paper portfolio:", err);
      setPaperPortfolioError("Paper portfolio unavailable.");
    } finally {
      setPaperPortfolioLoading(false);
    }
  };

  const handleAnalyzeClick = () => {
    const cleanTicker = ticker.trim().toUpperCase();

    if (!cleanTicker) return;

    setSubmittedTicker(cleanTicker);
    analyzeTicker(cleanTicker, timeframe);
  };

  const handleWatchlistSelect = (symbol) => {
    setTicker(symbol);
    setSubmittedTicker(symbol);
    analyzeTicker(symbol, timeframe);
  };

  const handleTimeframeChange = (newTimeframe) => {
    setTimeframe(newTimeframe);
    analyzeTicker(submittedTicker, newTimeframe);
    refreshWatchlistScores(newTimeframe);
  };

  const handleAddToWatchlist = async (symbol) => {
    const cleanSymbol = symbol.trim().toUpperCase();

    setWatchlistError("");

    if (!cleanSymbol) return;

    if (watchlist.includes(cleanSymbol)) {
      showWatchlistError("Ticker already exists.");
      return;
    }

    setAddingTicker(true);
    validationRequestRef.current.controller?.abort();

    const controller = new AbortController();
    const requestId = validationRequestRef.current.id + 1;
    validationRequestRef.current = { controller, id: requestId };

    try {
      const response = await validateTicker(cleanSymbol, {
        signal: controller.signal,
      });

      if (validationRequestRef.current.id !== requestId) return;

      if (!response.data.valid) {
        showWatchlistError("Invalid ticker symbol.");
        return;
      }

      const updatedWatchlist = [...watchlist, cleanSymbol];

      setWatchlist(updatedWatchlist);
      refreshWatchlistScores(timeframe, updatedWatchlist);
    } catch (err) {
      if (
        isRequestCanceled(err) ||
        validationRequestRef.current.id !== requestId
      ) {
        return;
      }

      console.error(err);
      showWatchlistError("Could not validate ticker.");
    } finally {
      if (validationRequestRef.current.id === requestId) {
        setAddingTicker(false);
      }
    }
  };

  const handleRemoveFromWatchlist = (symbol) => {
    const updatedWatchlist = watchlist.filter((stock) => stock !== symbol);

    setWatchlist(updatedWatchlist);

    setWatchlistScores((prevScores) => {
      const updatedScores = { ...prevScores };
      delete updatedScores[symbol];
      return updatedScores;
    });
  };

  const handleNavigate = (view) => {
    if (view === "portfolio") {
      refreshPaperPortfolio();
      setCurrentView("portfolio");
      return;
    }

    if (view === "dashboard") {
      setCurrentView("dashboard");
    }
  };

  const handlePortfolioSelect = (symbol) => {
    const cleanSymbol = symbol.trim().toUpperCase();

    if (!cleanSymbol) return;

    setTicker(cleanSymbol);
    setSubmittedTicker(cleanSymbol);
    setCurrentView("dashboard");
    analyzeTicker(cleanSymbol, timeframe);
  };

  useEffect(() => {
    analyzeTicker("AAPL", TIMEFRAMES[2]);
    refreshWatchlistScores(TIMEFRAMES[2], watchlist);
    refreshPaperPortfolio();
  }, []);

  useEffect(() => {
    localStorage.setItem("tradepilot-watchlist", JSON.stringify(watchlist));
  }, [watchlist]);

  useEffect(() => {
    return () => {
      analysisRequestRef.current.controller?.abort();
      validationRequestRef.current.controller?.abort();
      watchlistRequestRef.current.controller?.abort();
      analysisRequestRef.current.id += 1;
      validationRequestRef.current.id += 1;
      watchlistRequestRef.current.id += 1;
    };
  }, []);

  return (
    <div className="app">
      <div className="workstation-wrapper">
        <div className="workstation">
          <Header
            ticker={ticker}
            setTicker={setTicker}
            onAnalyze={handleAnalyzeClick}
            loading={loading}
            currentView={currentView}
            onNavigate={handleNavigate}
          />

          {error && <p className="error">{error}</p>}

          {currentView === "portfolio" && (
            <PortfolioPage
              portfolio={paperPortfolio}
              loading={paperPortfolioLoading}
              error={paperPortfolioError}
              onBack={() => setCurrentView("dashboard")}
              onSelectSymbol={handlePortfolioSelect}
            />
          )}

          {currentView === "dashboard" && analysis && (
            <div className="dashboard">
              <div className="left-column">
                <Watchlist
                  stocks={watchlist}
                  selectedStock={submittedTicker}
                  watchlistScores={watchlistScores}
                  timeframe={timeframe}
                  addingTicker={addingTicker}
                  watchlistError={watchlistError}
                  onSelectStock={handleWatchlistSelect}
                  onAddStock={handleAddToWatchlist}
                  onRemoveStock={handleRemoveFromWatchlist}
                />
                <ScannerPanel
                  onSelectTicker={handleWatchlistSelect}
                />

                <MetricsPanel analysis={analysis} />
              </div>

              <ChartPanel
                analysis={analysis}
                timeframe={timeframe}
                timeframes={TIMEFRAMES}
                onTimeframeChange={handleTimeframeChange}
              />

              <aside className="right-panel">
                <PaperPortfolioSummary
                  portfolio={paperPortfolio}
                  loading={paperPortfolioLoading}
                  error={paperPortfolioError}
                />

                <div className="right-card-grid">
                  <div className="panel-box analysis-summary-card">
                    <ThesisPanel
                      tradeThesis={analysis.trade_thesis}
                      embedded
                    />

                    <ScorePanel
                      title="Trend Score"
                      scoreData={analysis.trend_score}
                      embedded
                    />

                    <ScorePanel
                      title="Entry Score"
                      scoreData={analysis.entry_score}
                      embedded
                    />
                  </div>

                  <div className="right-action-column">
                    <SetupPanel tradeSetup={analysis.trade_setup} />

                    <QuickTradePanel
                      symbol={analysis.ticker}
                      currentPrice={analysis.price}
                      onTradeExecuted={refreshPaperPortfolio}
                    />
                  </div>
                </div>
              </aside>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;

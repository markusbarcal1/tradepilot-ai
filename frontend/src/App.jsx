import { useEffect, useState } from "react";
import axios from "axios";
import Header from "./components/Header";
import MetricsPanel from "./components/MetricsPanel";
import ChartPanel from "./components/ChartPanel";
import ThesisPanel from "./components/ThesisPanel";
import ScorePanel from "./components/ScorePanel";
import SetupPanel from "./components/SetupPanel";
import ResultPanel from "./components/ResultPanel";
import Watchlist from "./components/Watchlist";
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

const WATCHLIST = [
  "AAPL",
  "NVDA",
  "AMD",
  "META",
  "MSFT",
  "PLTR",
  "TSLA",
];

function App() {
  const [ticker, setTicker] = useState("AAPL");
  const [submittedTicker, setSubmittedTicker] = useState("AAPL");
  const [timeframe, setTimeframe] = useState(TIMEFRAMES[2]);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [watchlistScores, setWatchlistScores] = useState({});

  const handleWatchlistSelect = (symbol) => {
    setTicker(symbol);
    setSubmittedTicker(symbol);
    analyzeTicker(symbol, timeframe);
  };

  const refreshWatchlistScores = async (selectedTimeframe = timeframe) => {
  try {
    const results = await Promise.all(
      WATCHLIST.map(async (symbol) => {
        const response = await axios.get(
          `http://127.0.0.1:8000/analyze/${symbol}?period=${selectedTimeframe.period}&interval=${selectedTimeframe.interval}`
        );

        return {
          ticker: response.data.ticker,
          trend: response.data.trend_score?.score,
          entry: response.data.entry_score?.score,
        };
      })
    );

    const scoreMap = {};

    results.forEach((item) => {
      scoreMap[item.ticker] = {
        trend: item.trend,
        entry: item.entry,
      };
    });

    setWatchlistScores(scoreMap);
  } catch (err) {
    console.error("Could not refresh watchlist scores:", err);
  }
};

  const analyzeTicker = async (symbol = submittedTicker, selectedTimeframe = timeframe) => {
    setLoading(true);
    setError("");

    try {
      const response = await axios.get(
        `http://127.0.0.1:8000/analyze/${symbol}?period=${selectedTimeframe.period}&interval=${selectedTimeframe.interval}`
      );
      setAnalysis(response.data);

    } catch (err) {
      console.error(err);
      setAnalysis(null);
      setError("Could not analyze ticker. Check the symbol, interval, or backend server.");
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyzeClick = () => {
    const cleanTicker = ticker.trim().toUpperCase();
    setSubmittedTicker(cleanTicker);
    analyzeTicker(cleanTicker, timeframe);
  };

  const handleTimeframeChange = async (newTimeframe) => {
    setTimeframe(newTimeframe);
    analyzeTicker(submittedTicker, newTimeframe);
    refreshWatchlistScores(newTimeframe);
  };

  useEffect(() => {
    analyzeTicker("AAPL", TIMEFRAMES[2]);
    refreshWatchlistScores(TIMEFRAMES[2]);
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
        />
          {error && <p className="error">{error}</p>}

          {analysis && (
            <div className="dashboard">
              <div className="left-column">
                <Watchlist
                  stocks={WATCHLIST}
                  selectedStock={submittedTicker}
                  watchlistScores={watchlistScores}
                  timeframe={timeframe}
                  onSelectStock={handleWatchlistSelect}
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
                <ThesisPanel tradeThesis={analysis.trade_thesis} />
                <ScorePanel
                  title="Trend Score"
                  scoreData={analysis.trend_score}
                />
                <ScorePanel
                  title="Entry Score"
                  scoreData={analysis.entry_score}
                />
                <SetupPanel
                  tradeSetup={analysis.trade_setup}
                />
                <ResultPanel analysis={analysis} />
              </aside>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
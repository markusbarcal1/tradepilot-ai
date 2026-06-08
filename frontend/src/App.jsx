import { useEffect, useState } from "react";
import axios from "axios";
import Header from "./components/Header";
import MetricsPanel from "./components/MetricsPanel";
import ChartPanel from "./components/ChartPanel";
import ThesisPanel from "./components/ThesisPanel";
import ScorePanel from "./components/ScorePanel";
import SetupPanel from "./components/SetupPanel";
import ResultPanel from "./components/ResultPanel";
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

function App() {
  const [ticker, setTicker] = useState("AAPL");
  const [submittedTicker, setSubmittedTicker] = useState("AAPL");
  const [timeframe, setTimeframe] = useState(TIMEFRAMES[2]);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

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

  const handleTimeframeChange = (newTimeframe) => {
    setTimeframe(newTimeframe);
    analyzeTicker(submittedTicker, newTimeframe);
  };

  useEffect(() => {
    analyzeTicker("AAPL", TIMEFRAMES[2]);
  }, []);


  return (
    <div className="app">
      <div className="workstation-wrapper">
       <div className="workstation">
        <Header
          ticker={ticker}
          setTicker={setTicker}
          onAnalyze={handleAnalyzeClick}
        />
          {loading && <p className="status">Loading market data...</p>}
          {error && <p className="error">{error}</p>}

          {analysis && (
            <div className="dashboard">
              <MetricsPanel analysis={analysis} />
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
import SearchBar from "./SearchBar";

function Header({ ticker, setTicker, onAnalyze, loading }) {
  return (
    <header className="top-bar">
      <div>
        <h1>TradePilot AI</h1>
        <p className="subtitle">AI-assisted trading intelligence dashboard</p>
      </div>

      <SearchBar
        ticker={ticker}
        setTicker={setTicker}
        onAnalyze={onAnalyze}
        loading={loading}
      />
    </header>
  );
}

export default Header;
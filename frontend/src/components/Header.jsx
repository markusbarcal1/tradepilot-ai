import SearchBar from "./SearchBar";

function Header({
  ticker,
  setTicker,
  onAnalyze,
  loading,
  currentView,
  onNavigate,
}) {
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

      <nav className="top-nav" aria-label="Primary navigation">
        {["Dashboard", "Watchlist", "Scanner", "Portfolio"].map((item) => {
          const view = item.toLowerCase();
          const isActive = currentView === view;

          return (
            <button
              key={item}
              type="button"
              className={isActive ? "active" : ""}
              onClick={() => onNavigate(view)}
            >
              {item}
            </button>
          );
        })}

        <button type="button" className="theme-toggle" aria-label="Theme">
          ◐
        </button>
      </nav>
    </header>
  );
}

export default Header;

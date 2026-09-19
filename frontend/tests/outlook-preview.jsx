import { useState } from "react";
import { createRoot } from "react-dom/client";
import OutlookPanel from "../src/components/OutlookPanel";
import { outlookFixtures } from "./outlook-fixtures.mjs";
import { eventFixture } from "./outlook-event-fixtures.mjs";
import macroFixture from "./outlook-macro-fixture.json";
import "../src/App.css";
import "./outlook-preview.css";
export default function Preview() {
  const [scenario, setScenario] = useState("technology");
  const [width, setWidth] = useState("280");
  const [theme, setTheme] = useState("dark");
  const [state, setState] = useState("ready");
  return <main className="outlook-preview">
    <h1>Outlook fixture review</h1>
    <p>Offline fixtures · Actual component and dashboard theme tokens · No API calls</p>
    <div className="outlook-preview-controls">
      <label>Scenario <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
        <option value="technology">Technology · Mixed</option><option value="energy">Energy · Positive</option>
        <option value="negative">Overall Negative</option><option value="empty">No available categories</option>
        <option value="notMaterial">Not Material</option><option value="events">FOMC events · ABTC</option>
        <option value="macro">FOMC + macro events · ABTC</option>
      </select></label>
      <label>Card width <select value={width} onChange={(e) => setWidth(e.target.value)}>
        {[220, 280, 340, 520].map((n) => <option key={n} value={n}>{n}px</option>)}
      </select></label>
      <label>Request state <select value={state} onChange={(e) => setState(e.target.value)}>
        <option value="ready">Ready</option><option value="loading">Loading</option><option value="error">API failure</option>
      </select></label>
      <button type="button" onClick={() => { const next = theme === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = next; setTheme(next); }}>Switch to {theme === "dark" ? "light" : "dark"} theme</button>
    </div>
    <div className="panel-box analysis-summary-card outlook-preview-column" style={{ width: `${width}px` }}>
      <OutlookPanel data={["events", "macro"].includes(scenario) ? { ...outlookFixtures.technology, ticker: "ABTC", event_intelligence: scenario === "events" ? eventFixture : macroFixture } : outlookFixtures[scenario]} embedded loading={state === "loading"} error={state === "error" ? "fixture" : ""}/>
    </div>
  </main>;
}
createRoot(document.getElementById("root")).render(<Preview />);

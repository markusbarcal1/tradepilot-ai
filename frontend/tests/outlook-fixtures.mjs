const unavailable = { status: "insufficient_data", label: null, factors: [], evidence: [], summary: "Insufficient independent evidence: 0 qualifying events." };
function industry(label, sector, benchmark, returns, relative, breadth) {
  const sample = ["P1", "P2", "P3", "P4", "P5", "P6"];
  const observations = [
    { id: "breadth", title: "Sector peer breadth", event_type: "industry_peer_breadth", impact: 1,
      summary: `${sector} peer strength: ${Math.round(breadth[0]*100)}% positive over 21 sessions; ${Math.round(breadth[1]*100)}% above the 50-session average. Coverage 6/6; target excluded. This is a sector sample, not industry-wide breadth.`,
      source_details: { positive_return_breadth: breadth[0], above_sma50_breadth: breadth[1], peer_coverage: 6, peer_sample: sample } },
    { id: "performance", title: "Sector trend and relative strength", event_type: "sector_performance", impact: 0,
      summary: `${sector} sector trend and relative performance are ${label.toLowerCase()}. Multiple horizons form one sector performance event.`,
      source_details: { windows_sessions: [21, 63], benchmark, market_benchmark: "SPY", return_21: returns[0], return_63: returns[1], relative_21: relative[0], relative_63: relative[1] } },
  ].map((e) => ({ ...e, raw_provider: "industry", source: "Yahoo Finance sector market data", source_url: `https://finance.yahoo.com/quote/${benchmark}/`, published_at: "2026-09-17T20:00:00Z" }));
  return { status: "available", label, value: label === "Positive" ? 1 : 0,
    summary: "2 independent events support this assessment; 1 positive and 0 negative contributions.",
    factors: observations.map((e, index) => ({ title: e.title, description: e.summary, impact: index === 0 ? "Positive" : label, evidence_ids: [e.id] })), evidence: observations };
}
const base = {
  ticker: "AAPL", status: "partial", label: "Mixed", value: 0, available_categories: 3,
  summary: "Based on 3 available categories. External context, not a trading recommendation.",
  metadata: { uses_placeholder_data: false },
  categories: { company: unavailable, earnings: unavailable,
    industry: industry("Mixed", "Technology", "XLK", [.013, .013], [.019, -.018], [4/6, 5/6]),
    economic: { status: "available", label: "Mixed", summary: "4 independent events support this assessment.", factors: [
      { title: "Inflation context", impact: "Mixed", description: "Inflation indicators give a mixed view of the economic environment.", evidence_ids: ["fred"] }],
      evidence: [{ id: "fred", source: "Federal Reserve Economic Data", source_url: "https://fred.stlouisfed.org/series/CPIAUCSL" }] },
    market: { status: "available", label: "Positive", summary: "2 independent events support this assessment.", factors: [
      { title: "Broad equity-market trend", impact: "Positive", description: "Broad equity benchmarks are above their medium-term averages.", evidence_ids: ["market"] }],
      evidence: [{ id: "market", source: "Yahoo Finance", source_url: "https://finance.yahoo.com/quote/SPY/" }] },
    geopolitical: unavailable },
};
export const outlookFixtures = {
  technology: base,
  energy: { ...base, ticker: "XOM", label: "Positive", categories: { ...base.categories,
    industry: industry("Positive", "Energy", "XLE", [.013, .188], [.019, .156], [5/6, 1]) } },
  negative: { ...base, ticker: "TSLA", label: "Negative" },
  empty: { ...base, ticker: "TEST", status: "unavailable", label: null, available_categories: 0,
    categories: Object.fromEntries(Object.keys(base.categories).map((k) => [k, unavailable])) },
  notMaterial: { ...base, ticker: "REVIEWED", categories: { ...base.categories,
    geopolitical: { status: "not_material", label: null, summary: "Reviewed evidence has no material company exposure.", factors: [], evidence: [] } } },
};

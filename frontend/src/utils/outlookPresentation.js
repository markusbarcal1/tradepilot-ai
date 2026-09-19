// Presentation only: labels, availability and factor directions come from the API.
export const OUTLOOK_CATEGORIES = {
  company: "Company", earnings: "Earnings", industry: "Industry",
  economic: "Economic", market: "Market", geopolitical: "Geopolitical",
};
const STATES = {
  unavailable: "Unavailable", insufficient_data: "Insufficient Data",
  error: "Temporarily unavailable", not_material: "Not Material", placeholder: "Not connected",
};
export function outlookLabel(item) {
  return ["available", "partial"].includes(item?.status)
    ? (typeof item.label === "string" ? item.label : "Unavailable")
    : STATES[item?.status] || "Unavailable";
}
export function outlookTone(label) {
  if (["Positive", "Very Positive"].includes(label)) return "positive";
  if (["Negative", "Very Negative"].includes(label)) return "negative";
  if (label === "Mixed") return "mixed";
  return label === "Not Material" ? "immaterial" : "muted";
}
export function initialOutlookCategory() {
  return null;
}
export function selectOutlookCategory(current, next) {
  return Object.hasOwn(OUTLOOK_CATEGORIES, next) ? (current === next ? null : next) : current;
}
export function categoryIntroduction(key, category) {
  if (category?.status === "insufficient_data") {
    return key === "geopolitical"
      ? "Not enough supported geopolitical evidence is linked to this company."
      : "There is not enough supported evidence to assess this area yet.";
  }
  if (category?.status === "not_material") return "Reviewed evidence does not establish a material relationship to this company.";
  if (category?.status === "error") return "Context for this area is temporarily unavailable. This is a data issue, not an investment conclusion.";
  if (category?.status === "placeholder") return "This area is a preview; external intelligence is not connected.";
  if (category?.status !== "available") return "Context for this area is not currently available.";
  const subject = {
    company: "Company developments", earnings: "Earnings conditions", industry: "Sector conditions",
    economic: "Economic conditions", market: "Broad market conditions", geopolitical: "Supported geopolitical exposures",
  }[key];
  return `${subject} are ${outlookLabel(category).toLowerCase()}.`;
}
export function safeSourceUrl(url) {
  if (typeof url !== "string") return null;
  try { return ["https:", "http:"].includes(new URL(url).protocol) ? url : null; }
  catch { return null; }
}
const sourceText = (value) => typeof value === "string" ? value.trim() : "";
export function sourceLabel(item) {
  const details = item.source_details || {};
  // Observation titles about trends are not titles of the linked data resource.
  if (item.raw_provider === "fred" && sourceText(details.series_title)) return details.series_title;
  if (["market", "industry"].includes(item.raw_provider)) {
    const url = safeSourceUrl(item.source_url);
    const quote = url && new URL(url).pathname.match(/^\/quote\/([^/]+)\/?$/);
    let symbol;
    try { symbol = quote && decodeURIComponent(quote[1]); } catch { /* Fall back to evidence metadata. */ }
    const known = [details.symbol, details.benchmark, ...(Array.isArray(details.benchmarks) ? details.benchmarks.map((row) => row.symbol) : [])];
    if (symbol && known.includes(symbol)) {
      if (item.raw_provider === "industry" && sourceText(details.sector)) return `${details.sector} Sector Market Data`;
      return `${symbol === "^VIX" ? "VIX" : symbol} Market Data`;
    }
  }
  return sourceText(item.title) || sourceText(item.source) || "Source";
}
export function categorySources(category) {
  const sources = new Map();
  for (const item of category?.evidence || []) {
    const entries = [{ name: sourceLabel(item), url: item.source_url }, ...(item.exposure_links || [])
      .filter((link) => link.source_url).map((link) => ({ name: "Exposure reference", url: link.source_url }))];
    for (const entry of entries) {
      const url = safeSourceUrl(entry.url);
      if (!entry.name && !url) continue;
      const key = url || entry.name;
      if (!sources.has(key)) sources.set(key, { name: entry.name || "Source", url });
    }
  }
  return [...sources.values()];
}
export function factorEvidence(category, factor) {
  const ids = new Set(factor.evidence_ids || []);
  return (category?.evidence || []).filter((item) => ids.has(item.id));
}
const finite = (value) => typeof value === "number" && Number.isFinite(value);
export function industryMeasurements(category, factor) {
  const records = factorEvidence(category, factor);
  // Never combine observations or choose between competing measurements in the UI.
  if (records.length !== 1 || records[0].raw_provider !== "industry") return null;
  const item = records[0], details = item.source_details || {};
  if (item.event_type === "sector_performance" && Array.isArray(details.windows_sessions) && details.windows_sessions.join(",") === "21,63"
      && [details.return_21, details.return_63, details.relative_21, details.relative_63].every(finite)
      && typeof details.benchmark === "string" && typeof details.market_benchmark === "string") {
    return { kind: "performance", details };
  }
  if (item.event_type === "industry_peer_breadth"
      && [details.positive_return_breadth, details.above_sma50_breadth].every((n) => finite(n) && n >= 0 && n <= 1)
      && Number.isInteger(details.peer_coverage) && Array.isArray(details.peer_sample)
      && details.peer_coverage >= 0 && details.peer_coverage <= details.peer_sample.length) {
    return { kind: "breadth", details };
  }
  return null;
}
export const formatReturn = (value) => `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
export const formatRelative = (value) => `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)} pp`;

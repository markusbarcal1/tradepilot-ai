import assert from "node:assert/strict";
import fs from "node:fs/promises";
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { Window } from "happy-dom";
import { createServer } from "vite";

process.env.VITE_API_BASE_URL = "http://api.test";
process.env.VITE_SUPABASE_URL = "https://project.supabase.co";
process.env.VITE_SUPABASE_PUBLISHABLE_KEY = "sb_publishable_test";
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const window = new Window({ url: "http://localhost/" });
globalThis.window = window;
globalThis.document = window.document;
globalThis.HTMLElement = window.HTMLElement;
globalThis.Node = window.Node;
globalThis.localStorage = window.localStorage;
Object.defineProperty(globalThis, "navigator", { value: window.navigator, configurable: true });

const vite = await createServer({ server: { middlewareMode: true }, appType: "custom", logLevel: "error" });
const container = document.createElement("div");
document.body.appendChild(container);
const root = createRoot(container);

const category = (rating, summary, options = {}) => ({
  rating, summary, key_points: options.keyPoints || [],
  supporting_fact_ids: options.factIds || ["fact:hidden"], limitations: options.limitations || [],
});
const completeResponse = {
  overall: { rating: "very_positive", summary: "Verified conditions remain strongly constructive." },
  categories: {
    company: category("mostly_positive", "Company developments are supportive.", { keyPoints: [{ text: "Execution remains durable.", supporting_fact_ids: ["fact:company"] }] }),
    earnings: category("very_positive", "Recent earnings performance remains strong."),
    industry: category("mixed", "Industry conditions contain both strengths and constraints.", { limitations: ["Peer breadth remains limited."] }),
    economic: category("mostly_negative", "Economic conditions remain a headwind."),
    market: category("very_negative", "Broad market conditions are under pressure."),
    geopolitical: category("insufficient_data", "There is not enough verified geopolitical evidence.", { factIds: [] }),
  },
  what_to_watch: [{ event_id: "event:hidden", reason: "The next scheduled earnings report could materially change the outlook." }],
};
const historyWindow = (label, count, companyStep, benchmarkStep) => ({ label, session_count: count,
  points: Array.from({ length: count }, (_, index) => ({
    date: new Date(Date.UTC(2026, 5, 1 + index)).toISOString().slice(0, 10),
    company_cumulative_return: index * companyStep,
    benchmark_cumulative_return: index * benchmarkStep,
    relative_performance: index * (companyStep - benchmarkStep),
  })) });
const marketWindow = (label, count, spyStep, qqqStep) => ({ label, session_count: count,
  points: Array.from({ length: count }, (_, index) => ({
    date: new Date(Date.UTC(2026, 4, 1 + index)).toISOString().slice(0, 10),
    spy_cumulative_return: index * spyStep, qqq_cumulative_return: index * qqqStep,
  })) });
const research = {
  schema_version: "1", as_of: "2026-09-25T12:00:00Z", ticker: "NVDA",
  earnings: { fiscal_year: 2027, fiscal_period: "Q2", release_date: "2026-08-26",
    metrics: [
      { id: "metric-revenue", label: "Revenue", value: 96.2, unit: "USD_billion", change: 106, change_unit: "percent", period: "FY2027 Q2", comparison_label: "Reported year over year", comparison_type: "year_over_year", comparison_basis: "reported_change_only", source_ids: ["source-sec"] },
      { id: "metric-margin", label: "Gross Margin", value: 75, unit: "percent", previous_value: 72.4, change: 2.6, change_unit: "percentage_points", period: "FY2027 Q2", comparison_label: "Year over year", comparison_type: "year_over_year", comparison_basis: "exact_values", comparison_period: "Q2 FY2026", source_ids: ["source-sec"] },
    ], guidance: [], qualifier: "Verified recent issuer results from the accepted research snapshot. Two observations are a comparison, not a historical trend.",
    next_event: { id: "next-earnings", category: "earnings", event_type: "earnings_release", title: "NVDA Earnings", date: "2026-11-18", market_session: "unknown", schedule_certainty: "provider_reported", source_ids: ["source-calendar"] } },
  industry: { industry_name: "Semiconductors", classification_quality: "exact_industry",
    benchmark: { symbol: "SOXX", name: "Semiconductor ETF", benchmark_type: "industry_etf" },
    history: { schema_version: "1", snapshot_id: "abcdefabcdefabcdefabcdef", ticker: "NVDA",
      as_of: "2026-09-25T12:00:00Z", series_start: "2026-06-01", series_end: "2026-09-08",
      price_adjustment_basis: "yahoo_auto_adjust_true", currency: "USD", classification_quality: "exact_industry",
      taxonomy_version: "1", mapping_version: "1", available_windows: ["1M", "3M", "6M"],
      windows: [historyWindow("1M", 22, 1, .5), historyWindow("3M", 64, .4, .2), historyWindow("6M", 100, .2, .1)],
      coverage: { common_session_count: 100, company_missing_session_count: 0, benchmark_missing_session_count: 0,
        has_gaps: false, company_last_session: "2026-09-08", benchmark_last_session: "2026-09-08" },
      cumulative_return_unit: "percentage_points", relative_performance_unit: "percentage_points",
      source_ids: ["source-market"], qualifier: "Adjusted price return; not a total-return index." },
    comparisons: [{ window_sessions: 21, company_return: .055, benchmark_return: .102, relative_difference: -.047 }, { window_sessions: 63, company_return: .149, benchmark_return: -.094, relative_difference: .243 }],
    breadth: { state: "mixed", configured_count: 9, valid_count: 8, positive_return_participation: .625, above_sma50_participation: .75, median_return_21: .08, constituent_sample: ["AMD", "AVGO"] }, source_ids: ["source-market"] },
  economic: { trends: [{ id: "metric-unemployment", label: "Unemployment Rate", value: 4.1, unit: "percent", previous_value: 4.3, change: -.2, change_unit: "percentage_points", source_ids: ["source-fred"] }, { id: "metric-gs10", label: "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity, Quoted on an Investment Basis", value: 4.68, unit: "percent", previous_value: 4.48, change: .2, change_unit: "percentage_points", source_ids: ["source-fred"] }], releases: [{ id: "release", title: "Employment Situation", date: "2026-09-04", details: { headline_mom: "0.4 percent", real_gdp: "1.5 percent_saar", payrolls: "162000 jobs" }, source_ids: ["source-fred"] }], qualifier: "Latest available FRED vintage." },
  market: { benchmarks: [{ symbol: "SPY", close: 767.18, sma50: 759.46, prior_sma50: 757.65, trend: "above_rising", observation_date: "2026-09-24", source_ids: ["source-market"] }], volatility: { symbol: "^VIX", close: 15.67, regime: "normal", observation_date: "2026-09-24", source_ids: ["source-market"] },
    history: { schema_version: "1", snapshot_id: "marketmarketmarketmarket12", as_of: "2026-09-25T12:00:00Z", price_adjustment_basis: "yahoo_auto_adjust_true",
      windows: [marketWindow("1M", 22, .1, .2), marketWindow("3M", 64, .08, .12), marketWindow("6M", 100, .05, .09)],
      equity_coverage: { common_session_count: 100, has_gaps: false, spy_last_session: "2026-09-24", qqq_last_session: "2026-09-24" },
      vix_points: Array.from({ length: 20 }, (_, index) => ({ date: new Date(Date.UTC(2026, 8, 1 + index)).toISOString().slice(0, 10), level: 14 + index * .1 })),
      vix_threshold_low: 15, vix_threshold_high: 25, qualifier: "Broad-market proxies; VIX is an index level." } },
  company: { events: [], empty_message: "No qualifying material company developments were identified in the current research window." },
  geopolitical: { events: [{ id: "event-geo", event_type: "export_control", title: "Advanced computing export policy", summary: "Conditional licensing relief.", date: "2026-01-15", details: { form: null, filing_date: null, geography: "China, Macau", product_group: "advanced_computing", policy_change: "conditional_licensing_relief" }, qualifier: "Industry relevance does not establish product qualification, customer exposure, revenue exposure, or exact financial impact.", source_ids: ["source-bis"] }], empty_message: "No qualifying issuer-relevant geopolitical developments were identified." },
  what_to_watch: [{ id: "event-watch", title: "NVDA Earnings", date: "2026-11-18", market_session: "unknown", schedule_certainty: "provider_reported", reason: "The next scheduled earnings report could materially change the outlook.", source_ids: ["source-calendar"] }],
  sources: [
    { id: "source-sec", title: "SEC earnings release", name: "SEC EDGAR", url: "https://example.com/sec" },
    { id: "source-market", title: "Market data", name: "Yahoo Finance", url: "https://example.com/market" },
    { id: "source-fred", title: "Unemployment Rate", name: "FRED", url: "https://example.com/fred" },
    { id: "source-bis", title: "Federal Register rule", name: "BIS", url: "https://example.com/bis" },
    { id: "source-calendar", title: "Earnings Calendar", name: "Yahoo Finance", url: "https://example.com/calendar" },
  ],
};
const availableResult = { status: "available", analysis: completeResponse, research };

try {
  const { default: AIAnalysisPage } = await vite.ssrLoadModule("/src/components/AIAnalysisPage.jsx");
  let clicks = 0;
  let submitted = null;
  const render = async (props = {}) => act(async () => root.render(React.createElement(AIAnalysisPage, {
    draftTicker: "NVDA", onDraftTickerChange: () => {}, analyzedTicker: null, result: null,
    onAnalyze: (symbol) => { clicks += 1; submitted = symbol; }, ...props,
  })));
  await render();
  assert.match(container.textContent, /AI Analysis.*Research ticker.*Analyze/s);
  await act(async () => container.querySelector(".ai-local-search").requestSubmit());
  assert.equal(clicks, 1, "local Analyze click fires exactly once");
  assert.equal(submitted, "NVDA");

  await render({ analyzedTicker: "NVDA", result: availableResult });
  assert.match(container.textContent, /Executive outlook.*Very Positive.*Verified conditions remain strongly constructive/s);
  assert.match(container.textContent, /Research report.*NVDA/s);
  const sectionHeadings = [...container.querySelectorAll(".research-section > .research-section-header h3")].map((node) => node.textContent);
  assert.deepEqual(sectionHeadings, ["Earnings", "Industry", "Company", "Economic", "Market", "Geopolitical", "What to Watch"]);
  assert.match(container.textContent, /Verified financial results.*FY2027 Q2.*Revenue.*\$96.2B.*\+106% Reported year over year.*source did not provide an independently accepted prior amount/s);
  assert.match(container.textContent, /Gross Margin.*75%.*\+2.6 pp Year over year.*Q2 FY2026.*72.4%/s);
  assert.equal(container.querySelectorAll(".earnings-two-point").length, 1, "only an exact two-value comparison renders a two-point visual");
  assert.equal(container.querySelectorAll(".earnings-two-point > div").length, 2, "the comparison contains exactly two accepted observations");
  assert.equal(container.querySelector(".earnings-metric a").getAttribute("href"), "https://example.com/sec");
  assert.match(container.textContent, /Next earnings.*Nov 18, 2026.*Session not confirmed.*Provider reported — not issuer-confirmed/s);
  assert.match(container.textContent, /About This Data.*comparison, not a historical trend.*No consensus, surprise, forecast, probability, implied move, or multi-quarter history is inferred/s);
  assert.match(container.textContent, /Exact industry.*Semiconductors.*Accepted comparison benchmark.*SOXX.*21-Trading-Session Adjusted-Price Return.*63-Trading-Session Adjusted-Price Return/s);
  assert.match(container.textContent, /Historical Adjusted-Price Returns.*NVDA adjusted-price return.*SOXX benchmark adjusted-price return.*6M observation period:.*NVDA \+19.80%.*SOXX \+9.90%/s);
  assert.match(container.textContent, /percentage-point difference.*Relative Adjusted-Price Return.*zero line means equal adjusted-price returns.*does not predict future returns/si);
  assert.equal(container.querySelectorAll('[aria-label="Historical performance timeframe"] button').length, 3);
  const clicksBeforeChart = clicks;
  await act(async () => container.querySelector('[aria-label="Historical performance timeframe"] button').click());
  assert.match(container.textContent, /1M observation period:.*NVDA \+21.00%.*SOXX \+10.50%/s);
  assert.equal(clicks, clicksBeforeChart, "chart timeframe changes never request AI analysis");
  assert.match(container.querySelector(".research-chart-legend").getAttribute("aria-label"), /chart legend/i);
  const oneMonthOnly = { ...research.industry.history, available_windows: ["1M"], windows: [research.industry.history.windows[0]] };
  await render({ analyzedTicker: "NVDA", result: { ...availableResult, research: { ...research,
    industry: { ...research.industry, history: oneMonthOnly } } }, theme: "light" });
  assert.equal(container.querySelector('.research-timeframes button[aria-pressed="true"]').textContent, "1M");
  assert.equal([...container.querySelectorAll(".research-timeframes button")].filter((button) => button.disabled).length, 2);
  assert.match(container.textContent, /Industry Breadth.*8 of 9 constituents accepted.*not every company in the industry.*Constituent sample coverage.*8 \/ 9.*Positive 21-session adjusted-price returns.*62.5%.*Above the 50-day moving average.*75%.*Median 21-session adjusted-price return.*\+8%/s);
  assert.match(container.textContent, /About This Data.*TradePilot does not independently reconstruct or verify a dividend-reinvested total-return index/s);
  assert.match(container.textContent, /Unemployment Rate.*4.1%.*Previous comparable: 4.3%/s);
  assert.match(container.textContent, /10-Year Treasury Yield.*Headline MoM.*0.4%.*Real GDP.*1.5% annualized.*162,000 jobs/s);
  assert.equal(container.querySelectorAll(".research-metrics.macro .value-positive, .research-metrics.macro .value-negative").length, 0);
  assert.match(container.textContent, /SPY.*767.18.*50-day moving average.*759.46.*VIX.*15.67.*normal volatility regime/s);
  assert.match(container.textContent, /Historical Broad-Market Adjusted-Price Returns.*SPY.*S&P 500 ETF benchmark.*QQQ.*Nasdaq-100 ETF benchmark.*6M observation period:.*SPY \+4.95%.*QQQ \+8.91%/s);
  assert.match(container.textContent, /Historical VIX Index Level.*Latest 15.67.*normal regime.*index points.*low below 15.*elevated at 25 or higher/s);
  const marketClicks = clicks;
  const marketButtons = container.querySelectorAll('[aria-label="Broad-market historical timeframe"] button');
  assert.equal(marketButtons.length, 3);
  await act(async () => marketButtons[0].click());
  assert.match(container.textContent, /1M observation period:.*SPY \+2.10%.*QQQ \+4.20%/s);
  assert.equal(clicks, marketClicks, "Market chart interactions never request AI analysis");
  assert.match(container.textContent, /No qualifying material company developments/);
  assert.match(container.textContent, /Advanced computing export policy.*China, Macau.*does not establish product qualification/s);
  assert.match(container.textContent, /Advanced Computing.*Conditional Licensing Relief/s);
  assert.doesNotMatch(container.textContent, /form.*null|filing date.*null|conditional_licensing_relief|advanced_computing/i);
  assert.match(container.textContent, /Insufficient Data.*There is not enough verified geopolitical evidence/s);
  assert.match(container.textContent, /What to Watch.*Nov 18, 2026.*NVDA Earnings.*Session not confirmed.*next scheduled earnings report/s);
  assert.match(container.textContent, /SEC earnings release.*Federal Register rule.*Earnings Calendar/s);
  assert.equal(container.querySelectorAll(".research-interpretation details").length, 2);
  assert.doesNotMatch(container.textContent, /fact:hidden|fact:company|event:hidden|hidden-provider|hidden-fingerprint/);

  const details = [...container.querySelectorAll(".research-interpretation details")]
    .find((node) => node.textContent.includes("Execution remains durable"));
  await act(async () => details.querySelector("summary").click());
  assert.match(details.textContent, /Supporting interpretation.*Execution remains durable/s);
  await render({ analyzedTicker: "NVDA", result: { ...availableResult, research: { ...research, what_to_watch: [] } } });
  assert.match(container.textContent, /No material upcoming events were selected/);
  const sparseIndustry = { ...research.industry, history: null };
  await render({ analyzedTicker: "NVDA", result: { ...availableResult, research: { ...research, industry: sparseIndustry } }, theme: "light" });
  assert.match(container.textContent, /Historical visualization is unavailable.*21-Trading-Session Adjusted-Price Return.*Industry Breadth/s);
  const sparseEarnings = { schema_version: "1", metrics: [], guidance: [], next_event: research.earnings.next_event,
    qualifier: research.earnings.qualifier };
  await render({ analyzedTicker: "NVDA", result: { ...availableResult, research: { ...research, earnings: sparseEarnings } } });
  assert.match(container.textContent, /No verified recent earnings results are available.*Next earnings.*Provider reported — not issuer-confirmed/s);
  assert.equal(container.querySelectorAll(".earnings-metric, .earnings-two-point").length, 0);
  assert.doesNotMatch(container.textContent, /\$96.2B|72.4%/);

  await render({ draftTicker: "AAPL", analyzedTicker: "NVDA", result: availableResult });
  assert.match(container.textContent, /Research report.*NVDA.*Verified conditions remain strongly constructive/s);
  assert.equal(container.querySelector("#ai-analysis-ticker").value, "AAPL");
  await render({ draftTicker: "AAPL", analyzedTicker: "NVDA", result: availableResult, loading: true, analyzingTicker: "AAPL" });
  assert.match(container.textContent, /Analyzing AAPL/);
  assert.equal(container.querySelector("button").disabled, true);
  assert.equal(container.querySelector("button").getAttribute("aria-busy"), "true");
  await render({ draftTicker: "AAPL", analyzedTicker: "NVDA", result: availableResult, error: "private provider details", errorTicker: "AAPL" });
  assert.match(container.textContent, /Analysis unavailable for AAPL/);
  assert.doesNotMatch(container.textContent, /private provider details/);

  const app = await fs.readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
  const header = await fs.readFile(new URL("../src/components/Header.jsx", import.meta.url), "utf8");
  const search = await fs.readFile(new URL("../src/components/SearchBar.jsx", import.meta.url), "utf8");
  const client = await fs.readFile(new URL("../src/api/client.js", import.meta.url), "utf8");
  assert.doesNotMatch(app, /<OutlookPanel|fetchOutlook|loadOutlookAnalysis/);
  assert.match(app, /currentView === "ai-analysis"/);
  assert.match(app, /generateAIAnalysis\(symbol, \{ signal: controller\.signal \}\)/);
  assert.match(app, /setAnalyzedTicker\(symbol\)/);
  assert.match(app, /const \[aiDraftTicker, setAIDraftTicker\] = useState\(null\)/);
  assert.match(app, /view === "ai-analysis" && aiDraftTicker === null/);
  assert.match(app, /draftTicker=\{aiDraftTicker \|\| ""\}/);
  assert.match(app, /analyzedTicker=\{analyzedTicker\}/);
  assert.match(app, /aiAnalysisRequestRef\.current\.id !== requestId/);
  assert.match(header, /AI Analysis.*ai-analysis/s);
  assert.match(search, /"GO"/);
  assert.doesNotMatch(search, />Analyze</);
  assert.match(client, /api\.post\(`\/outlook\/\$\{encodeURIComponent\(symbol\)\}\/analysis`, null, \{/);
  assert.doesNotMatch(client, /force|refresh/);
  assert.equal((app.match(/requestAIAnalysis\(cleanTicker\)/g) || []).length, 1,
    "only the local handler may request AI analysis");
  assert.doesNotMatch(app, /useEffect\([\s\S]{0,300}requestAIAnalysis/);
  assert.match(app, /<ScorePanel/);
  assert.match(app, /<FinancialScorePanel/);
  assert.match(app, /<ValuationScorePanel/);
  const presentation = await fs.readFile(new URL("../src/utils/aiAnalysisPresentation.js", import.meta.url), "utf8");
  const styles = await fs.readFile(new URL("../src/App.css", import.meta.url), "utf8");
  const marketCharts = await fs.readFile(new URL("../src/components/MarketHistoryCharts.jsx", import.meta.url), "utf8");
  assert.match(styles, /\.ai-analysis-foundation[\s\S]*width: min\(1480px, 100%\)/);
  assert.match(styles, /\.ai-analysis-foundation[\s\S]*padding: 24px/);
  assert.match(styles, /\.ai-analysis-result[^}]*gap: 30px/);
  assert.match(styles, /\.research-section[^}]*padding: 2px 0 30px/);
  assert.match(styles, /\.research-chart-main[^}]*min-height: 280px/);
  assert.match(styles, /\.market-chart-equity[^}]*min-height: 280px/);
  assert.match(styles, /\.market-chart-vix[^}]*min-height: 190px/);
  assert.match(styles, /@media \(min-width: 721px\) and \(max-width: 1100px\)[\s\S]*repeat\(2, minmax\(0, 1fr\)\)/);
  assert.match(styles, /\.research-interpretation[\s\S]*max-width: 900px/);
  assert.match(styles, /\.ai-analysis-page[\s\S]*overflow-x: hidden/);
  assert.match(styles, /\.vix-boundary-labels[\s\S]*inset: 0 72px 0 0/);
  assert.match(marketCharts, /axisLabelVisible: false/);
  assert.match(marketCharts, /Low below.*Elevated.*\+/s);
  assert.match(presentation, /very_positive.*Very Positive.*mostly_positive.*Mostly Positive.*mixed.*Mixed.*mostly_negative.*Mostly Negative.*very_negative.*Very Negative.*insufficient_data.*Insufficient Data/s);
  assert.doesNotMatch(presentation, /Buy|Sell|Hold|price target/i);
  console.log("AI Analysis result UX and explicit-generation boundary tests passed.");
} finally {
  await act(async () => root.unmount());
  await vite.close();
  window.happyDOM.abort();
}

import assert from "node:assert/strict";
import fs from "node:fs/promises";
import React, { act } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { Window } from "happy-dom";
import { createServer } from "vite";
import { outlookFixtures } from "./outlook-fixtures.mjs";
import { eventFixture, probabilityFixture, earningsFixture } from "./outlook-event-fixtures.mjs";
import { outlookLabel, outlookTone, initialOutlookCategory, selectOutlookCategory,
  categoryIntroduction, categorySources, sourceLabel, industryMeasurements } from "../src/utils/outlookPresentation.js";
const window = new Window({ url: "http://localhost" });
Object.assign(globalThis, { window, document: window.document, HTMLElement: window.HTMLElement, Node: window.Node, IS_REACT_ACT_ENVIRONMENT: true });
const { createRoot } = await import("react-dom/client");
const { default: userEvent } = await import("@testing-library/user-event");
const user = userEvent.setup({ document: window.document });
const vite = await createServer({ server: { middlewareMode: true }, appType: "custom" });
const container = document.createElement("div");
document.body.append(container);
const root = createRoot(container);
try {
  const { default: OutlookPanel } = await vite.ssrLoadModule("/src/components/OutlookPanel.jsx");
  const render = (props) => renderToStaticMarkup(React.createElement(OutlookPanel, props));
  const mount = async (props) => { await act(async () => root.render(React.createElement(OutlookPanel, props))); };
  const button = (name) => [...container.querySelectorAll(".outlook-category-button")].find((b) => b.querySelector(".outlook-category-name").textContent === name);
  const choose = async (name) => { await act(async () => user.click(button(name))); };
  let pageScrollCalls = 0;
  window.scrollTo = window.scrollBy = () => { pageScrollCalls += 1; };
  const detail = () => container.querySelector(".outlook-detail");
  const primary = () => { const clone = container.cloneNode(true); clone.querySelectorAll(".outlook-methodology").forEach((n) => n.remove()); return clone.textContent; };
  for (const key of ["technology", "energy", "negative"]) {
    const data = outlookFixtures[key], html = render({ data, embedded: true });
    assert.match(html, /^<section/);
    assert.equal((html.match(/class="outlook-category-button"/g) || []).length, 6);
    assert.ok(html.includes(data.label) && html.includes(`outlook-status--${outlookTone(data.label)}`));
    assert.match(html, /3 of 6 categories available/);
    assert.doesNotMatch(html, /progressbar|\/100/);
  }
  await mount({ data: outlookFixtures.technology });
  assert.equal(detail(), null);
  assert.equal(container.querySelectorAll('[aria-pressed="true"]').length, 0);
  await choose("Industry");
  assert.equal(detail().querySelector("h4").textContent, "Industry");
  assert.equal(container.querySelectorAll('.outlook-category-button[aria-pressed="true"]').length, 1);
  for (const text of ["Why this rating", "Sector peer breadth", "Sector trend and relative strength"]) assert.ok(primary().includes(text));
  assert.doesNotMatch(primary(), /independent events|contributions|qualifying events|industry-wide breadth/);
  assert.equal(container.querySelectorAll('a[href="https://finance.yahoo.com/quote/XLK/"]').length, 1);
  assert.equal(container.querySelector("a").rel, "noopener noreferrer");
  const methodology = container.querySelector(".outlook-methodology");
  assert.equal(methodology.open, false);
  await act(async () => user.click(methodology.querySelector("summary")));
  assert.equal(methodology.open, true);
  assert.match(methodology.textContent, /independent events/);
  assert.match(methodology.textContent, /sector sample, not industry-wide breadth/i);
  await choose("Industry");
  assert.equal(detail(), null);
  await choose("Industry");
  await choose("Market");
  assert.equal(container.querySelectorAll(".outlook-detail").length, 1);
  assert.equal(detail().querySelector("h4").textContent, "Market");
  assert.match(detail().textContent, /Broad equity-market trend/);
  assert.doesNotMatch(detail().textContent, /Sector peer breadth/);
  await choose("Geopolitical");
  assert.match(detail().textContent, /Not enough supported geopolitical evidence/);
  assert.equal(detail().querySelectorAll(".outlook-driver").length, 0);
  await choose("Geopolitical");
  assert.equal(detail(), null);
  // User-event emulates native keyboard default actions against the mounted DOM.
  document.activeElement.blur();
  await act(async () => user.tab());
  assert.equal(document.activeElement, button("Company"));
  await act(async () => user.keyboard("{Enter}"));
  assert.equal(detail().querySelector("h4").textContent, "Company");
  assert.equal(document.activeElement, button("Company"));
  await act(async () => user.keyboard(" "));
  assert.equal(detail(), null);
  await act(async () => { await user.tab(); await user.tab(); await user.keyboard(" "); });
  assert.equal(document.activeElement, button("Industry"));
  assert.equal(detail().querySelector("h4").textContent, "Industry");
  assert.equal(document.getElementById(button("Industry").getAttribute("aria-controls")).hidden, false);
  await mount({ data: outlookFixtures.empty });
  assert.equal(detail(), null);
  assert.equal(container.querySelectorAll(".outlook-category-button").length, 6);
  await choose("Company");
  assert.match(detail().textContent, /not enough supported evidence/);
  await mount({ data: outlookFixtures.notMaterial });
  await choose("Geopolitical");
  assert.match(detail().textContent, /Not Material/);
  assert.match(detail().textContent, /does not establish a material relationship/);
  assert.ok(detail().querySelector(".outlook-status--immaterial"));
  await mount({ data: outlookFixtures.energy });
  assert.equal(detail(), null);
  await choose("Industry");
  assert.equal(detail().querySelector("h4").textContent, "Industry");
  assert.match(detail().textContent, /independent events support this assessment/);
  const lone = structuredClone(outlookFixtures.empty);
  lone.ticker = "NVDA";
  lone.categories.geopolitical = { ...lone.categories.geopolitical, evidence: [{ id: "geo", title: "Conditional export licensing", summary: "Approval is not guaranteed.", impact: 1,
    source: "Federal Register / BIS", source_url: "https://www.federalregister.gov/",
    exposure_links: [{ description: "Industry-level match only.", source_url: "https://finance.yahoo.com/quote/NVDA/profile/" }] }] };
  await mount({ data: lone }); await choose("Geopolitical");
  assert.match(detail().textContent, /Insufficient independent evidence/);
  assert.doesNotMatch(primary(), /Conditional export licensing|Approval is not guaranteed|Positive/);
  assert.equal(detail().querySelectorAll("a").length, 2);
  assert.equal(detail().querySelector(":scope > .outlook-sources"), null);
  assert.equal(detail().querySelectorAll(".outlook-methodology a").length, 2);
  const reviewed = structuredClone(lone);
  reviewed.ticker = "REVIEWED";
  reviewed.categories.geopolitical.status = "not_material";
  await mount({ data: reviewed }); await choose("Geopolitical");
  assert.equal(detail().querySelector(":scope > .outlook-sources"), null);
  assert.equal(detail().querySelectorAll(".outlook-methodology a").length, 2);
  const company = structuredClone(lone);
  company.ticker = "ABTC";
  company.categories.company.evidence = Array.from({ length: 8 }, (_, i) => ({
    title: `Form 8-K document ${i}`, source: "SEC EDGAR", source_url: `https://www.sec.gov/document/${i}`,
  }));
  await mount({ data: company }); await choose("Company");
  assert.doesNotMatch(primary(), /SEC EDGAR|Form 8-K|Sources/);
  assert.equal(detail().querySelectorAll(".outlook-methodology a").length, 8);
  await mount({ data: outlookFixtures.technology, loading: true });
  assert.equal(detail(), null); assert.equal(container.querySelectorAll("button:disabled").length, 6);
  assert.match(primary(), /Loading Outlook/);
  await mount({ data: outlookFixtures.energy });
  assert.equal(detail(), null);
  assert.equal(container.querySelectorAll('[aria-pressed="true"]').length, 0);
  assert.equal(pageScrollCalls, 0);
  await mount({ data: outlookFixtures.technology, error: "private provider error" });
  assert.equal(detail(), null); assert.match(primary(), /temporarily unavailable/);
  assert.doesNotMatch(primary(), /private provider error/);
  assert.match(render({}), /Outlook data is unavailable/);
  assert.match(render({ data: { status: "placeholder", metadata: { uses_placeholder_data: true } } }), /Preview.*Intelligence not connected/);
  assert.equal(outlookLabel({ status: "insufficient_data", label: "Positive", value: 2 }), "Insufficient Data");
  assert.equal(outlookLabel({ status: "available", value: 2 }), "Unavailable");
  assert.equal(initialOutlookCategory(outlookFixtures.empty.categories), null);
  assert.equal(initialOutlookCategory(outlookFixtures.technology.categories), null);
  const sourceCases = [
    { raw_provider: "fred", source: "FRED", source_details: { series_title: "Real GDP" }, source_url: "https://fred.stlouisfed.org/series/GDP", expected: "Real GDP" },
    { raw_provider: "sec", title: "ABTC Form 8-K", source: "SEC EDGAR", source_url: "https://www.sec.gov/document/1", expected: "ABTC Form 8-K" },
    { raw_provider: "market", source: "Yahoo", source_details: { benchmarks: [{ symbol: "SPY" }, { symbol: "QQQ" }] }, source_url: "https://finance.yahoo.com/quote/SPY/", expected: "SPY Market Data" },
    { raw_provider: "market", source_details: { symbol: "^VIX" }, source_url: "https://finance.yahoo.com/quote/%5EVIX/", expected: "VIX Market Data" },
    { source: "Provider fallback", source_url: "https://example.com/fallback", expected: "Provider fallback" },
  ];
  for (const item of sourceCases) {
    assert.equal(sourceLabel(item), item.expected);
    const data = structuredClone(outlookFixtures.technology);
    data.ticker = item.expected;
    data.categories.economic.evidence = [item];
    delete data.category_intelligence.economic;
    await mount({ data }); await choose("Economic");
    assert.equal(detail().querySelector(".outlook-sources a").textContent, item.expected);
    assert.equal(detail().querySelector("a").getAttribute("href"), item.source_url);
  }
  const sec = sourceCases[1];
  assert.equal(categorySources({ evidence: [sec, { ...sec, source_url: "https://www.sec.gov/document/2" }, sec] }).length, 2);
  assert.equal(selectOutlookCategory("industry", "market"), "market");
  assert.equal(selectOutlookCategory("industry", "industry"), null);
  assert.equal(selectOutlookCategory("industry", "bogus"), "industry");
  assert.notEqual(categoryIntroduction("company", { status: "not_material" }), categoryIntroduction("company", { status: "insufficient_data" }));
  const category = structuredClone(outlookFixtures.technology.categories.industry), performance = category.factors[1];
  category.evidence[1].source_details.return_21 = null;
  assert.equal(industryMeasurements(category, performance), null);
  category.evidence[1].source_details.return_21 = 0;
  assert.equal(industryMeasurements(category, performance).details.return_21, 0);
  category.evidence[1].source_details.return_21 = Infinity;
  assert.equal(industryMeasurements(category, performance), null);
  assert.equal(categorySources({ evidence: [{ source: "Unsafe", source_url: "javascript:alert(1)" }] })[0].url, null);
  const css = await fs.readFile(new URL("../src/App.css", import.meta.url), "utf8"), outlookCss = css.slice(css.indexOf(".outlook-card {"));
  assert.match(outlookCss, /repeat\(2, minmax\(0, 1fr\)\)/);
  assert.match(outlookCss, /@container outlook \(min-width: 480px\)/);
  assert.match(outlookCss, /@container outlook \(max-width: 239px\)/);
  assert.match(outlookCss, /:focus-visible/);
  assert.match(outlookCss, /overflow-anchor: none/);
  assert.doesNotMatch(outlookCss, /#[0-9a-f]{3,8}\b|rgba?\(/i);
  for (const theme of ["dark", "light"]) {
    document.documentElement.dataset.theme = theme; await mount({ data: outlookFixtures.technology });
    assert.equal(container.querySelectorAll(".outlook-category-button").length, 6);
    assert.ok(container.querySelector(".outlook-status--mixed"));
    const block = css.split(`[data-theme="${theme}"] {`)[1].split("}")[0];
    const tokens = Object.fromEntries([...block.matchAll(/(--[\w-]+):\s*(#[\da-f]+)/gi)].map((m) => [m[1], m[2]]));
    const luminance = (hex) => {
      const c = hex.match(/[a-f0-9]{2}/gi).map((n) => parseInt(n, 16) / 255)
        .map((n) => n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4);
      return c[0] * .2126 + c[1] * .7152 + c[2] * .0722;
    };
    for (const token of ["--text-positive", "--text-negative", "--text-warning", "--text-secondary", "--text-secondary-strong"]) {
      const a = luminance(tokens[token]), b = luminance(tokens["--bg-canvas"]);
      assert.ok((Math.max(a, b) + .05) / (Math.min(a, b) + .05) >= 4.5, `${theme}: ${token} contrast`);
    }
  }
  const eventData = { ...outlookFixtures.technology, ticker: "ABTC", event_intelligence: structuredClone(eventFixture) };
  await mount({ data: eventData });
  assert.equal(detail(), null);
  assert.equal(container.querySelectorAll(".outlook-category-button").length, 6);
  assert.match(container.querySelector(".outlook-events").textContent, /Upcoming.*Recent/s);
  assert.match(container.querySelector(".outlook-events").textContent, /Oct 28, 2026/);
  assert.match(container.querySelector(".outlook-events").textContent, /\+25 bp/);
  assert.equal(container.querySelectorAll(".outlook-event[open]").length, 0);
  const eventDetails = container.querySelectorAll(".outlook-event")[1];
  await act(async () => user.click(eventDetails.querySelector("summary")));
  assert.equal(eventDetails.open, true);
  assert.match(eventDetails.textContent, /3.50–3.75%/);
  assert.match(eventDetails.textContent, /3.75–4.00%/);
  assert.match(eventDetails.textContent, /Why this matters to ABTC/);
  assert.match(eventDetails.textContent, /Stock direction is uncertain/);
  assert.equal(container.querySelector(".outlook-event-expectation"), null);
  assert.equal(eventDetails.querySelector("a").rel, "noopener noreferrer");
  eventData.event_intelligence.recent[0].event.expectation = probabilityFixture;
  eventData.event_intelligence.recent[0].event.expectation_status = "available";
  eventData.event_intelligence.recent[0].event.surprise = { status: "as_expected" };
  await mount({ data: eventData });
  assert.match(container.querySelector(".outlook-event-expectation").textContent, /Event outcome probabilities/);
  assert.match(container.querySelector(".outlook-event-expectation").textContent, /Hold: 30%/);
  assert.match(container.querySelector(".outlook-event-expectation").textContent, /Before announcement/);
  assert.match(container.textContent, /As expected/);
  assert.doesNotMatch(container.textContent, /chance ABTC rises|stock probability/i);
  eventData.event_intelligence.recent[0].event.expectation = { ...probabilityFixture, expires_at: "2026-09-15T19:00:00Z" };
  await mount({ data: eventData });
  assert.equal(container.querySelector(".outlook-event-expectation"), null);
  await mount({ data: { ...eventData, ticker: "NVDA" } });
  assert.equal(container.querySelectorAll(".outlook-event[open]").length, 0);
  await mount({ data: eventData, loading: true });
  assert.equal(container.querySelector(".outlook-events"), null);
  await mount({ data: { ...eventData, event_intelligence: { status: "temporarily_unavailable" } } });
  assert.match(container.textContent, /Event Intelligence is temporarily unavailable/);
  assert.equal(pageScrollCalls, 0);
  const withProvenance = structuredClone(outlookFixtures.technology);
  withProvenance.ticker = "POLICY";
  withProvenance.categories.economic.evidence.push({ id: "fomc", raw_provider: "fomc", scoring_eligible: false,
    title: "FOMC Rate Decision", summary: "Relevant context; direction uncertain.", source: "Federal Reserve",
    source_url: "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm" });
  delete withProvenance.category_intelligence.economic;
  await mount({ data: withProvenance }); await choose("Economic");
  assert.doesNotMatch(primary(), /FOMC Rate Decision/);
  assert.match(detail().querySelector(".outlook-methodology").textContent, /FOMC Rate Decision/);
  assert.ok(detail().querySelector('.outlook-methodology a[href*="federalreserve.gov"]'));
  const macroFixture = JSON.parse(await fs.readFile(new URL("./outlook-macro-fixture.json", import.meta.url), "utf8"));
  await mount({ data: { ...eventData, event_intelligence: macroFixture } });
  const macroDetails = [...container.querySelectorAll(".outlook-event")];
  assert.equal(macroDetails.length, macroFixture.upcoming.length + macroFixture.recent.length);
  assert.equal(container.querySelectorAll(".outlook-event[open]").length, 0);
  const cpi = macroDetails.find((d) => /CPI Inflation/.test(d.textContent) && /Actual:/.test(d.textContent));
  assert.match(cpi.textContent, /August 2026/);
  assert.match(cpi.textContent, /Headline CPI MoM.*Actual: 0.4%/s);
  assert.match(cpi.textContent, /Core CPI YoY.*Actual: 2.4%/s);
  assert.match(cpi.textContent, /Consensus unavailable/);
  assert.doesNotMatch(cpi.textContent, /Expected:|Surprise:/);
  assert.ok(cpi.querySelector('a[href*="bls.gov"]'));
  const employment = macroDetails.find((d) => /Employment Situation/.test(d.textContent) && /Actual:/.test(d.textContent));
  assert.match(employment.textContent, /\+162,000 jobs/);
  assert.match(employment.textContent, /Unemployment rate.*4.1%/s);
  const gdp = macroDetails.find((d) => /GDP/.test(d.textContent) && /Actual:/.test(d.textContent));
  assert.match(gdp.textContent, /Q2 2026/);
  assert.match(gdp.textContent, /Second Estimate/);
  assert.match(gdp.textContent, /Previous estimate: 1.5% annualized/);
  assert.match(container.querySelector(".outlook-events").textContent, /8:30 AM EDT/);
  const actualCpi = macroFixture.recent.find((r) => r.event.event_type === "macro_cpi").event;
  const measurement = actualCpi.measurements[0];
  measurement.expectation_status = "available";
  measurement.expectation = { ...probabilityFixture, outcomes: [], basis: "structured_consensus",
    observed_at: "2026-09-11T11:30:00Z", expires_at: "2026-09-11T13:30:00Z", expected_value: { amount: .3, unit: "percent" } };
  measurement.surprise = { status: "higher_than_expected" };
  await mount({ data: { ...eventData, event_intelligence: macroFixture } });
  assert.match(container.textContent, /Expected: 0.3%/);
  assert.match(container.textContent, /Surprise: Higher than expected/);
  assert.equal(container.querySelectorAll(".outlook-event-expectation").length, 0);
  assert.doesNotMatch(container.querySelector(".outlook-events").textContent, /Event outcome probabilities/);
  measurement.expectation.expires_at = "2026-09-10T13:30:00Z";
  await mount({ data: { ...eventData, event_intelligence: macroFixture } });
  assert.doesNotMatch(container.querySelector(".outlook-events").textContent, /Expected:|Surprise:/);
  const mixedEvents = structuredClone(macroFixture);
  mixedEvents.upcoming.push(...structuredClone(earningsFixture.upcoming));
  mixedEvents.recent.push(...structuredClone(earningsFixture.recent));
  mixedEvents.upcoming.sort((a, b) => new Date(a.event.scheduled_date) - new Date(b.event.scheduled_date));
  mixedEvents.recent.sort((a, b) => new Date(b.event.announced_at) - new Date(a.event.announced_at));
  await mount({ data: { ...eventData, ticker: "NVDA", event_intelligence: mixedEvents } });
  const eventRows = [...container.querySelectorAll(".outlook-event")];
  const upcomingEarnings = eventRows.find((row) => /NVDA Earnings/.test(row.textContent) && /Scheduled/.test(row.textContent));
  assert.match(upcomingEarnings.textContent, /After market.*Issuer event/s);
  assert.doesNotMatch(upcomingEarnings.textContent, /Actual:/);
  const recentEarnings = eventRows.find((row) => /NVDA Earnings/.test(row.textContent) && /Released/.test(row.textContent));
  assert.match(recentEarnings.textContent, /FY2026 Q2/);
  assert.match(recentEarnings.textContent, /Period ended.*Jul 27, 2026/s);
  assert.match(recentEarnings.textContent, /Revenue.*Actual: \$30.04B/s);
  assert.match(recentEarnings.textContent, /Diluted EPS.*Actual: \$0.67/s);
  assert.match(recentEarnings.textContent, /Gross Margin.*Previous estimate: 70.1%/s);
  assert.match(recentEarnings.textContent, /Guidance.*Raised/s);
  assert.match(recentEarnings.textContent, /Consensus unavailable/);
  assert.doesNotMatch(recentEarnings.textContent, /Expected:|Surprise:/);
  assert.ok(recentEarnings.querySelector('a[href*="sec.gov"]'));
  const earningsWithConsensus = structuredClone(earningsFixture);
  const eps = earningsWithConsensus.recent[0].event.measurements[1];
  eps.expectation_status = "available";
  eps.expectation = { ...probabilityFixture, event_id: earningsWithConsensus.recent[0].event.event_id,
    measurement_key: "diluted_eps", reference_period: "FY2026 Q2", release_type: "Earnings release",
    basis: "structured_consensus", outcomes: [], expected_value: { amount: .60, unit: "USD_per_share" },
    observed_at: "2026-08-20T18:05:00Z", expires_at: "2026-08-20T20:06:00Z" };
  eps.surprise = { status: "higher_than_expected", percent_difference: 11.66666667 };
  await mount({ data: { ...eventData, ticker: "NVDA", event_intelligence: earningsWithConsensus } });
  assert.match(container.textContent, /Expected: \$0.60/);
  assert.match(container.textContent, /Surprise: \+11.7%/);
  assert.doesNotMatch(container.textContent, /probability.*beat/i);
  const decisionData = structuredClone(outlookFixtures.technology);
  decisionData.ticker = "NVDA";
  decisionData.event_intelligence = earningsFixture;
  decisionData.key_events = [{ event_id: "earnings:NVDA:next", title: "NVDA Earnings", status: "upcoming",
    event_date: "2026-10-20", importance: "high", timing: "After Market", certainty: "Provider Reported" }];
  decisionData.categories.earnings = { status: "available", label: "Positive", value: 1,
    summary: "2 independent events support this assessment.", factors: [], evidence: [] };
  decisionData.category_intelligence.earnings = { category: "earnings", availability: "available", rating: "Positive",
    summary: "Earnings outlook is positive.", positive_drivers: [
      { label: "Diluted EPS beat", direction: "positive", importance: "high", value: "$0.67", change: "+11.7%" },
      { label: "Gross Margin improved", direction: "positive", importance: "medium", change: "+5.0 pp" },
      { label: "Guidance raised", direction: "positive", importance: "high" }],
    negative_drivers: [], neutral_mixed_drivers: [], evidence_sufficiency: "2 qualifying events; current support threshold met.", omitted_driver_count: 0,
    important_metrics: [
      { key: "diluted_eps", label: "Diluted EPS", actual: "$0.67", expected: "$0.60", result: "+11.7%", indicator: "Beat", comparison_status: "available" },
      { key: "revenue", label: "Revenue", actual: "$30.04B", expected: null, result: null, indicator: null, comparison_status: "unavailable" }],
    latest_material_event: { event_id: "earnings:NVDA:FY2026:Q2", title: "NVDA Earnings", status: "occurred", event_date: "2026-08-20", importance: "high" },
    next_material_event: decisionData.key_events[0], sources: [{ name: "NVIDIA FY2026 Q2 Earnings Release", url: "https://www.sec.gov/Archives/nvda-exhibit.htm" }],
    beat_probability: null, implied_move: null };
  await mount({ data: decisionData });
  assert.match(button("Earnings").textContent, /Diluted EPS beat.*\+11.7%.*Guidance raised/s);
  assert.match(container.querySelector(".outlook-key-events").textContent, /Oct 20.*NVDA Earnings.*HIGH IMPACT/s);
  assert.equal(container.querySelector(".outlook-all-events").open, false);
  await choose("Earnings");
  assert.match(detail().textContent, /Important metrics.*Diluted EPS.*Beat.*Expected.*\$0.60.*Actual.*\$0.67/s);
  assert.match(detail().textContent, /Revenue.*Reported.*\$30.04B.*Comparison unavailable/s);
  assert.match(detail().textContent, /Why this rating.*Guidance raised/s);
  assert.equal(detail().querySelector(".outlook-methodology").open, false);
  assert.equal(detail().querySelector(".outlook-methodology summary").textContent, "Sources & methodology");
  assert.ok(detail().querySelector('a[href*="sec.gov"]'));
  assert.doesNotMatch(detail().textContent, /beat probability|implied move/i);
  const app = await fs.readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
  assert.doesNotMatch(app, /<OutlookPanel|fetchOutlook|loadOutlookAnalysis/);
  assert.match(app, /<ScorePanel/);
  assert.match(app, /<FinancialScorePanel/);
  assert.match(app, /<ValuationScorePanel/);
  console.log("Outlook summary, selection, keyboard, evidence, provenance, availability and theme tests passed.");
} finally {
  await act(async () => root.unmount()); await vite.close(); window.happyDOM.abort();
}

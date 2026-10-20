import assert from "node:assert/strict";
import fs from "node:fs/promises";
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { Window } from "happy-dom";
import { createServer } from "vite";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const window = new Window({ url: "http://localhost/" });
globalThis.window = window;
globalThis.document = window.document;
globalThis.HTMLElement = window.HTMLElement;
globalThis.Node = window.Node;
Object.defineProperty(globalThis, "navigator", { value: window.navigator, configurable: true });

const vite = await createServer({ server: { middlewareMode: true }, appType: "custom", logLevel: "error" });
const container = document.createElement("div");
document.body.appendChild(container);
const root = createRoot(container);

const annualPoint = (fiscalYear, exactEPS, options = {}) => ({
  fiscal_year: fiscalYear,
  period_start: `${fiscalYear - 1}-02-01`,
  period_end: `${fiscalYear}-01-31`,
  exact_eps: exactEPS,
  unit: "USD_per_share",
  observation_type: "reported",
  reporting_status: "original",
  provenance_label: "SEC filing GAAP diluted EPS",
  source_ids: ["sec-public"],
  ...options,
});

const quarterDates = { Q1: ["02-01", "04-30"], Q2: ["05-01", "07-31"],
  Q3: ["08-01", "10-31"], Q4: ["11-01", "01-31"] };
const quarterlyPoint = (fiscalYear, quarter, exactEPS, options = {}) => {
  const [start, end] = quarterDates[quarter];
  return annualPoint(fiscalYear, exactEPS, {
    fiscal_quarter: quarter,
    period_start: `${quarter === "Q4" ? fiscalYear - 1 : fiscalYear}-${start}`,
    period_end: `${fiscalYear}-${end}`,
    ...options,
  });
};

const history = (changes = {}) => ({
  schema_version: "1",
  certification_policy: "sec-gaap-diluted-eps-history-1",
  share_basis: "diluted",
  accounting_basis: "gaap",
  unit: "USD_per_share",
  annual: { state: "available", reasons: [], observation_count: 3 },
  quarterly: { state: "available", reasons: [], observation_count: 3 },
  annual_points: [annualPoint(2024, "-1.2300"), annualPoint(2025, "0"), annualPoint(2026, "2.450")],
  quarterly_points: [quarterlyPoint(2026, "Q3", "0.30"), quarterlyPoint(2026, "Q1", "-0.10"),
    quarterlyPoint(2026, "Q2", "0")],
  ...changes,
});

try {
  const { default: EPSHistoryChart } = await vite.ssrLoadModule("/src/components/EPSHistoryChart.jsx");
  const { epsTooltipRows, normalizeAnnualEPSPoints, normalizeQuarterlyEPSPoints,
    segmentAnnualEPSPoints, segmentQuarterlyEPSPoints, shouldShowZeroBaseline } =
    await vite.ssrLoadModule("/src/utils/epsHistoryPresentation.js");

  const annual = normalizeAnnualEPSPoints(history());
  assert.deepEqual(annual.map((row) => row.chartValue), [-1.23, 0, 2.45],
    "signed negative, zero, and positive values are plotted");
  assert.equal(annual[0].exactLabel, "-1.2300", "exact decimal precision remains a string");
  assert.deepEqual(epsTooltipRows(annual[0], "annual"), ["FY2024",
    "Diluted EPS: -1.2300 USD/share", "Basis: Reported GAAP diluted",
    "Reporting status: Original", "Source: SEC filing GAAP diluted EPS"]);
  assert.equal(shouldShowZeroBaseline(annual), true, "a signed range displays the zero reference");
  assert.equal(shouldShowZeroBaseline(normalizeAnnualEPSPoints(history({ annual_points: [
    annualPoint(2024, "1.10"), annualPoint(2025, "2.20")] }))), false,
  "a positive-only range does not force zero into view");

  const nonCalendar = normalizeQuarterlyEPSPoints(history());
  assert.deepEqual(nonCalendar.map((row) => row.fiscal_quarter), ["Q1", "Q2", "Q3"],
    "fiscal identities, not calendar dates, determine ordering");
  assert.equal(nonCalendar[0].period_start, "2026-02-01");
  assert.deepEqual(segmentQuarterlyEPSPoints(nonCalendar).map((segment) => segment.length), [3]);

  const annualGaps = normalizeAnnualEPSPoints(history({ annual: { state: "partial", reasons: ["missing_fiscal_periods"] },
    annual_points: [annualPoint(2022, "1"), annualPoint(2024, "2")] }));
  assert.deepEqual(segmentAnnualEPSPoints(annualGaps).map((segment) => segment.map((row) => row.fiscal_year)),
    [[2022], [2024]]);
  const quarterGaps = normalizeQuarterlyEPSPoints(history({ quarterly: { state: "partial", reasons: ["missing_fiscal_periods"] },
    quarterly_points: [quarterlyPoint(2025, "Q4", "1"), quarterlyPoint(2026, "Q2", "2")] }));
  assert.deepEqual(segmentQuarterlyEPSPoints(quarterGaps).map((segment) => segment.length), [1, 1]);
  const comparisonBreak = normalizeQuarterlyEPSPoints(history({ quarterly_points: [
    quarterlyPoint(2026, "Q1", "0.10"),
    quarterlyPoint(2026, "Q2", "0.20", { comparison_break_before: true })] }));
  assert.deepEqual(segmentQuarterlyEPSPoints(comparisonBreak).map((segment) => segment.length), [1, 1]);
  assert.match(epsTooltipRows(comparisonBreak[1], "quarterly").join(" "),
    /Comparability: Not established with prior period/);
  const sortedAnnualBreak = normalizeAnnualEPSPoints(history({ annual_points: [
    annualPoint(2026, "3", { comparison_break_before: true }), annualPoint(2024, "1"),
    annualPoint(2025, "2")] }));
  assert.deepEqual(segmentAnnualEPSPoints(sortedAnnualBreak).map((segment) =>
    segment.map((row) => row.fiscal_year)), [[2024, 2025], [2026]],
  "annual comparison breaks remain effective after fiscal sorting");

  assert.deepEqual(normalizeAnnualEPSPoints(history({ annual_points: [annualPoint(2026, "1"), annualPoint(2026, "2")] })), [],
    "duplicate fiscal identities fail closed");
  for (const change of [{ accounting_basis: "adjusted" }, { share_basis: "basic" },
    { unit: "USD" }, { certification_policy: "unsupported" }]) {
    assert.deepEqual(normalizeAnnualEPSPoints(history(change)), []);
  }
  assert.deepEqual(normalizeAnnualEPSPoints(history({ annual_points: [
    annualPoint(2026, "1", { observation_type: "adjusted" }),
    annualPoint(2027, "1", { unit: "USD" }), annualPoint(2028, "NaN") ] })), []);

  const render = async (props) => act(async () => root.render(React.createElement(EPSHistoryChart, props)));
  const originalFetch = globalThis.fetch;
  let fetchCalls = 0;
  globalThis.fetch = async () => { fetchCalls += 1; throw new Error("unexpected request"); };
  const sourceMap = new Map([["sec-public", { id: "sec-public", title: "SEC EDGAR filing",
    url: "https://www.sec.gov/Archives/example.htm" }]]);
  await render({ epsHistory: history(), sourceMap, theme: "dark" });
  assert.match(container.textContent, /Annual Diluted EPS History.*3 certified annual observations, FY2024 to FY2026/s);
  assert.equal(container.querySelector('[aria-label="Diluted EPS history period"] button[aria-pressed="true"]').textContent, "Annual");
  assert.ok(container.querySelector(".eps-history-chart"), "responsive auto-size chart container renders");
  await act(async () => container.querySelectorAll(".eps-history-modes button")[1].click());
  assert.equal(fetchCalls, 0, "mode switching makes no network or AI request");
  assert.match(container.textContent, /Quarterly Diluted EPS History.*3 certified quarterly observations, FY2026 Q1 to FY2026 Q3/s);
  await render({ epsHistory: history({ quarterly: { state: "partial", reasons: ["missing_fiscal_periods"] },
    quarterly_points: [quarterlyPoint(2026, "Q1", "0.10"), quarterlyPoint(2026, "Q3", "0.30")] }), sourceMap, theme: "light" });
  await act(async () => container.querySelectorAll(".eps-history-modes button")[1].click());
  assert.match(container.textContent, /2 certified quarterly observations.*Some fiscal periods are missing or conflicted.*shown as breaks/s);

  for (const state of ["conflict", "unavailable"]) {
    await render({ epsHistory: history({ annual: { state, reasons: [state === "conflict" ? "conflicted_fiscal_periods" : "no_certified_observations"] }, annual_points: [] }), sourceMap });
    await act(async () => container.querySelectorAll(".eps-history-modes button")[0].click());
    assert.match(container.textContent, state === "conflict" ? /evidence conflicts/ : /No certified/);
  }
  globalThis.fetch = originalFetch;

  const componentSource = await fs.readFile(new URL("../src/components/EPSHistoryChart.jsx", import.meta.url), "utf8");
  assert.match(componentSource, /attributionLogo:\s*true/, "TradingView attribution remains enabled");
  assert.match(componentSource, /shouldShowZeroBaseline\(points\)/,
    "the zero baseline is conditional on the plotted range");
  assert.match(componentSource, /axisLabelVisible:\s*false, title:\s*""/,
    "the zero baseline does not duplicate the formatted axis label");
  assert.match(componentSource, /autoSize:\s*true/, "chart is responsive");
  assert.match(componentSource, /dark:.*light:/s, "dark and light chart themes are defined");
  assert.doesNotMatch(componentSource, /evidence_identity|growth_pct/i);
  const pageSource = await fs.readFile(new URL("../src/components/AIAnalysisPage.jsx", import.meta.url), "utf8");
  assert.match(pageSource, /<RevenueHistoryChart[^>]*\s*\/><EPSHistoryChart[^>]*\s*\/>.*research-next-event/s,
    "EPS history is directly beneath Revenue History and before Next Earnings");

  console.log("Diluted EPS history presentation, validation, chart, and UI-state tests passed.");
} finally {
  await act(async () => root.unmount());
  await vite.close();
  window.happyDOM.abort();
}

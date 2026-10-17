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

const annualPoint = (fiscalYear, exactRevenue, options = {}) => ({
  fiscal_year: fiscalYear,
  period_start: `${fiscalYear - 1}-01-01`,
  period_end: `${fiscalYear}-12-31`,
  exact_revenue: exactRevenue,
  currency: "USD",
  observation_type: "reported",
  yoy_growth_pct: null,
  provenance_label: "SEC 10-K annual revenue",
  source_ids: ["source-public"],
  ...options,
});

const unavailableGrowth = (reason = "first_observation") => ({ state: "unavailable",
  exact_growth_pct: null, display_growth_pct: null, reason,
  current_source_kind: "directly_reported", comparison_source_kind: null,
  uses_derived_evidence: false });
const availableGrowth = (display = "5.1", derived = false) => ({ state: "available",
  exact_growth_pct: display, display_growth_pct: display, reason: null,
  current_source_kind: derived ? "derived" : "directly_reported",
  comparison_source_kind: "directly_reported", uses_derived_evidence: derived });
const quarterlyPoint = (fiscalYear, fiscalQuarter, periodEnd, exactRevenue, options = {}) => ({
  fiscal_year: fiscalYear,
  fiscal_quarter: fiscalQuarter,
  display_label: `FY${fiscalYear} ${fiscalQuarter}`,
  period_start: "2024-01-01",
  period_end: periodEnd,
  duration_days: 91,
  exact_revenue: exactRevenue,
  revenue_billions: "1",
  currency: "USD",
  source_kind: "directly_reported",
  derived: false,
  source_policy: "historical-financial-observation-schema-1",
  evidence_identity: "must-not-render",
  derivation_policy: null,
  derivation_formula_identity: null,
  reconciliation_policy: null,
  qoq: unavailableGrowth(),
  yoy: unavailableGrowth("prior_same_fiscal_quarter_unavailable"),
  ...options,
});

try {
  const { default: RevenueHistoryChart } = await vite.ssrLoadModule("/src/components/RevenueHistoryChart.jsx");
  const { annualTooltipRows, formatExactRevenue, normalizeAnnualRevenuePoints,
    normalizeQuarterlyRevenuePoints, quarterlyTooltipRows, quarterlyUnavailableMessage,
    segmentAnnualRevenuePoints, segmentQuarterlyRevenuePoints } =
    await vite.ssrLoadModule("/src/utils/revenueHistoryPresentation.js");

  const annualRows = [annualPoint(2025, "416161000000", { yoy_growth_pct: "6.43" }),
    annualPoint(2023, "383285000000"),
    annualPoint(2024, "391035000000", { observation_type: "certified_derived" })];
  const normalizedAnnual = normalizeAnnualRevenuePoints(annualRows);
  assert.deepEqual(normalizedAnnual.map((row) => row.fiscal_year), [2023, 2024, 2025]);
  assert.equal(formatExactRevenue("416161000000"), "$416,161,000,000");
  assert.deepEqual(annualTooltipRows(normalizedAnnual[2]), ["FY2025", "Revenue: $416,161,000,000",
    "YoY growth: +6.43%", "Status: Reported", "Source: SEC 10-K annual revenue"]);
  assert.match(annualTooltipRows(normalizedAnnual[1]).join(" "), /Certified derived.*SEC 10-K annual revenue/);

  const annualGaps = normalizeAnnualRevenuePoints([
    annualPoint(2021, "100"), annualPoint(2022, "120"), annualPoint(2024, "180")]);
  assert.deepEqual(segmentAnnualRevenuePoints(annualGaps).map((segment) =>
    segment.map((row) => row.fiscal_year)), [[2021, 2022], [2024]]);
  assert.deepEqual(normalizeAnnualRevenuePoints([
    annualPoint(2025, "not-a-number"), annualPoint(2026, "200", { currency: "EUR" }),
    annualPoint(2027, "300", { observation_type: "projected" }),
    annualPoint(2028, "400", { period_end: "2028-02-30" })]), []);
  assert.deepEqual(normalizeAnnualRevenuePoints([
    annualPoint(2025, "100"), annualPoint(2025, "101")]), []);

  // Fiscal identity, not calendar month, determines ordering and adjacency.
  const quarterlyRows = [
    quarterlyPoint(2025, "Q2", "2025-03-29", "95359000000", {
      qoq: availableGrowth("-23.3") }),
    quarterlyPoint(2025, "Q1", "2024-12-28", "124300000000"),
    quarterlyPoint(2025, "Q4", "2025-09-27", "102466000000", {
      source_kind: "derived", derived: true, qoq: availableGrowth("9.0", true),
      yoy: availableGrowth("2.0", true), derivation_policy: "revenue-q4-derivation-1",
      derivation_formula_identity: "FY-minus-Q1-minus-Q2-minus-Q3",
      reconciliation_policy: "revenue-q4-reconciliation-1" }),
    quarterlyPoint(2025, "Q3", "2025-06-28", "94036000000", {
      qoq: availableGrowth("-1.4") }),
  ];
  const normalizedQuarterly = normalizeQuarterlyRevenuePoints(quarterlyRows);
  assert.deepEqual(normalizedQuarterly.map((row) => row.fiscal_quarter), ["Q1", "Q2", "Q3", "Q4"]);
  assert.equal(normalizedQuarterly[0].period_end, "2024-12-28", "non-calendar fiscal Q1 is retained");
  assert.equal(normalizedQuarterly[3].exactLabel, "$102,466,000,000");
  assert.deepEqual(segmentQuarterlyRevenuePoints(normalizedQuarterly).map((row) => row.length), [4]);
  const derivedTooltip = quarterlyTooltipRows(normalizedQuarterly[3]);
  assert.deepEqual(derivedTooltip, ["FY2025 Q4", "Revenue: $102,466,000,000",
    "QoQ growth: +9%", "YoY growth: +2%", "Status: Certified derived Q4",
    "Method: Certified FY minus Q1 minus Q2 minus Q3"]);
  assert.doesNotMatch(derivedTooltip.join(" "), /evidence_identity|must-not-render/);
  assert.match(quarterlyTooltipRows(normalizedQuarterly[0]).join(" "),
    /QoQ growth: unavailable.*YoY growth: unavailable.*Status: Reported.*SEC Company Facts/s);

  const quarterGaps = normalizeQuarterlyRevenuePoints([
    quarterlyPoint(2024, "Q4", "2024-12-31", "100"),
    quarterlyPoint(2025, "Q2", "2025-06-30", "120")]);
  assert.deepEqual(segmentQuarterlyRevenuePoints(quarterGaps).map((row) => row.length), [1, 1]);
  const malformedQuarterly = [
    quarterlyPoint(2025, "Q1", "2025-03-31", "bad"),
    quarterlyPoint(2025, "Q2", "2025-06-31", "100"),
    quarterlyPoint(2025, "Q3", "2025-09-30", "100", { currency: "EUR" }),
    quarterlyPoint(2025, "Q4", "2025-12-31", "100", { source_kind: "unknown" }),
    quarterlyPoint(2026, "Q1", "2026-03-31", "100", { qoq: { state: "unknown" } }),
  ];
  assert.deepEqual(normalizeQuarterlyRevenuePoints(malformedQuarterly), []);
  const duplicate = quarterlyPoint(2025, "Q1", "2025-03-31", "100");
  assert.deepEqual(normalizeQuarterlyRevenuePoints([duplicate,
    { ...duplicate, exact_revenue: "101" }]), []);

  assert.match(quarterlyUnavailableMessage("insufficient_data"), /insufficient/);
  assert.match(quarterlyUnavailableMessage("conflict"), /conflicts/);
  assert.match(quarterlyUnavailableMessage("unavailable"), /unavailable/);

  const revenueHistory = { availability: "available", annual_points: annualRows,
    points: quarterlyRows };
  let fetchCalls = 0;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => { fetchCalls += 1; throw new Error("unexpected network request"); };
  const render = async (props) => act(async () => root.render(React.createElement(RevenueHistoryChart, props)));
  await render({ revenueHistory, theme: "dark" });
  assert.match(container.textContent, /Annual Revenue History.*3 certified annual observations, FY2023 to FY2025/s);
  assert.equal(container.querySelector('[aria-label="Revenue history period"] button[aria-pressed="true"]').textContent, "Annual");
  assert.equal(container.querySelector(".revenue-history-chart") !== null, true);
  await act(async () => container.querySelectorAll(".revenue-history-modes button")[1].click());
  assert.equal(fetchCalls, 0, "switching views makes no network request");
  assert.match(container.textContent, /Quarterly Revenue History.*4 certified quarterly observations, FY2025 Q1 to FY2025 Q4/s);
  assert.match(container.textContent, /Certified derived Q4/);
  assert.doesNotMatch(container.textContent, /must-not-render/);
  await render({ revenueHistory, theme: "light" });
  assert.match(container.textContent, /Quarterly Revenue History/);
  globalThis.fetch = originalFetch;

  for (const availability of ["insufficient_data", "conflict", "unavailable"]) {
    await render({ revenueHistory: { availability, annual_points: annualRows, points: quarterlyRows }, theme: "dark" });
    await act(async () => container.querySelectorAll(".revenue-history-modes button")[1].click());
    assert.match(container.textContent, availability === "insufficient_data" ? /insufficient/ : /unavailable/);
    assert.equal(container.querySelector(".revenue-history-chart"), null);
    await act(async () => container.querySelectorAll(".revenue-history-modes button")[0].click());
    assert.match(container.textContent, /Annual Revenue History.*3 certified annual observations/s,
      "quarterly state does not hide annual observations");
  }

  for (const file of ["RevenueHistoryChart.jsx", "ResearchPerformanceChart.jsx",
    "MarketHistoryCharts.jsx", "TradingChart.jsx"]) {
    const source = await fs.readFile(new URL(`../src/components/${file}`, import.meta.url), "utf8");
    assert.match(source, /attributionLogo:\s*true/,
      `${file} must explicitly preserve TradingView attribution`);
  }

  console.log("Annual and quarterly revenue history chart integrity and UI-state tests passed.");
} finally {
  await act(async () => root.unmount());
  await vite.close();
  window.happyDOM.abort();
}

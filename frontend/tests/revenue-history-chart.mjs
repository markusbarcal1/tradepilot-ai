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

const point = (fiscalYear, exactRevenue, options = {}) => ({
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

try {
  const { default: RevenueHistoryChart } = await vite.ssrLoadModule("/src/components/RevenueHistoryChart.jsx");
  const { annualTooltipRows, formatExactRevenue, normalizeAnnualRevenuePoints,
    segmentAnnualRevenuePoints } = await vite.ssrLoadModule("/src/utils/revenueHistoryPresentation.js");

  const rows = [point(2025, "416161000000", { yoy_growth_pct: "6.43" }),
    point(2023, "383285000000"), point(2024, "391035000000", { observation_type: "certified_derived" })];
  const normalized = normalizeAnnualRevenuePoints(rows);
  assert.deepEqual(normalized.map((row) => row.fiscal_year), [2023, 2024, 2025]);
  assert.equal(formatExactRevenue("416161000000"), "$416,161,000,000");
  assert.deepEqual(annualTooltipRows(normalized[2]), ["FY2025", "Revenue: $416,161,000,000",
    "YoY growth: +6.43%", "Status: Reported", "Source: SEC 10-K annual revenue"]);
  assert.match(annualTooltipRows(normalized[1]).join(" "), /Certified derived.*SEC 10-K annual revenue/);

  const gapRows = normalizeAnnualRevenuePoints([point(2021, "100"), point(2022, "120"), point(2024, "180")]);
  assert.deepEqual(segmentAnnualRevenuePoints(gapRows).map((segment) => segment.map((row) => row.fiscal_year)),
    [[2021, 2022], [2024]], "missing fiscal years split the line series");

  const malformed = normalizeAnnualRevenuePoints([
    point(2025, "not-a-number"), point(2026, "200", { currency: "EUR" }),
    point(2027, "300", { observation_type: "projected" }),
    point(2028, "400", { period_end: "invalid" }),
  ]);
  assert.deepEqual(malformed, [], "malformed, non-USD, and forecast observations are excluded");
  assert.deepEqual(normalizeAnnualRevenuePoints([point(2025, "100"), point(2025, "101")]), [],
    "ambiguous duplicate fiscal years fail closed");

  const render = async (props) => act(async () => root.render(React.createElement(RevenueHistoryChart, props)));
  await render({ annualPoints: rows, theme: "dark" });
  assert.match(container.textContent, /Annual Revenue History.*3 certified annual observations, FY2023 to FY2025/s);
  assert.equal(container.querySelector(".revenue-history-chart") !== null, true);
  await render({ annualPoints: rows, theme: "light" });
  assert.match(container.textContent, /Reported and certified-derived fiscal-year revenue only/);
  await render({ annualPoints: gapRows, theme: "dark" });
  assert.match(container.textContent, /Missing fiscal years are shown as breaks; no values are interpolated/);
  await render({ annualPoints: [], theme: "light" });
  assert.match(container.textContent, /Annual revenue history is unavailable/);
  assert.equal(container.querySelector(".revenue-history-chart"), null);

  for (const file of ["RevenueHistoryChart.jsx", "ResearchPerformanceChart.jsx",
    "MarketHistoryCharts.jsx", "TradingChart.jsx"]) {
    const source = await fs.readFile(new URL(`../src/components/${file}`, import.meta.url), "utf8");
    assert.match(source, /attributionLogo:\s*true/,
      `${file} must explicitly preserve TradingView attribution`);
  }

  console.log("Annual revenue history chart data integrity and UI-state tests passed.");
} finally {
  await act(async () => root.unmount());
  await vite.close();
  window.happyDOM.abort();
}

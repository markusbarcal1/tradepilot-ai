import assert from "node:assert/strict";
import fs from "node:fs/promises";
import React, { act } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { Window } from "happy-dom";
import { createServer } from "vite";
import { outlookFixtures } from "./outlook-fixtures.mjs";
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
  for (const text of ["67%", "83%", "+1.3%", "+1.9 pp", "-1.8 pp", "Sector sample"]) assert.ok(primary().includes(text));
  assert.doesNotMatch(primary(), /independent events|contributions|qualifying events|industry-wide breadth/);
  assert.equal(container.querySelectorAll('a[href="https://finance.yahoo.com/quote/XLK/"]').length, 1);
  assert.equal(container.querySelector("a").rel, "noopener noreferrer");
  const methodology = container.querySelector(".outlook-methodology");
  assert.equal(methodology.open, false);
  await act(async () => user.click(methodology.querySelector("summary")));
  assert.equal(methodology.open, true);
  assert.match(methodology.textContent, /independent events/);
  assert.match(methodology.textContent, /sector sample, not industry-wide breadth/);
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
  assert.equal(detail().querySelectorAll(".outlook-evidence-row").length, 0);
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
  assert.match(detail().textContent, /Sector conditions are positive/);
  const lone = structuredClone(outlookFixtures.empty);
  lone.ticker = "NVDA";
  lone.categories.geopolitical = { ...lone.categories.geopolitical, evidence: [{ id: "geo", title: "Conditional export licensing", summary: "Approval is not guaranteed.", impact: 1,
    source: "Federal Register / BIS", source_url: "https://www.federalregister.gov/",
    exposure_links: [{ description: "Industry-level match only.", source_url: "https://finance.yahoo.com/quote/NVDA/profile/" }] }] };
  await mount({ data: lone }); await choose("Geopolitical");
  assert.match(detail().textContent, /Source observations below do not establish a category assessment/);
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
  const app = await fs.readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
  assert.ok(app.indexOf("<ValuationScorePanel") < app.indexOf("<OutlookPanel"));
  assert.match(app, /outlookRequestRef.current.controller\?\.abort\(\)/);
  assert.match(app, /outlookRequestRef.current.id !== requestId/);
  console.log("Outlook summary, selection, keyboard, evidence, provenance, availability and theme tests passed.");
} finally {
  await act(async () => root.unmount()); await vite.close(); window.happyDOM.abort();
}

import assert from "node:assert/strict";
import fs from "node:fs/promises";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const vite = await createServer({ server: { middlewareMode: true }, appType: "custom" });
try {
  const { default: OutlookPanel } = await vite.ssrLoadModule("/src/components/OutlookPanel.jsx");
  const render = (props) => renderToStaticMarkup(React.createElement(OutlookPanel, props));
  const data = {
    status: "partial", label: "Positive", value: 1, summary: "Fixture context.",
    metadata: { uses_placeholder_data: false }, available_categories: 2,
    categories: {
      company: { status: "available", label: "Positive", value: 1,
        summary: "Company fixture.", factors: [{ title: "Raised guidance", impact: "Positive", description: "Demo evidence.", evidence_ids: ["example"] }],
        evidence: [{ id: "example", raw_provider: "sec", source: "SEC", source_url: "https://www.sec.gov/Archives/example" }] },
      earnings: { status: "available", label: "Very Positive", value: 2 },
      geopolitical: { status: "not_material", label: null, value: null },
    },
  };
  const html = render({ data, embedded: true });
  for (const label of ["Company", "Earnings", "Industry", "Economic", "Market", "Geopolitical"]) {
    assert.ok(html.includes(`${label} Outlook`));
  }
  for (const text of ["Positive", "Very Positive", "Not Material", "Raised guidance", "Demo evidence."]) {
    assert.ok(html.includes(text));
  }
  assert.match(html, /2 of 6 Outlook categories available/);
  const industryHtml = render({ data: { ...data, available_categories: 3,
    categories: { ...data.categories, industry: { status: "available", label: "Positive",
      summary: "Two sector events support this assessment.",
      factors: [{ title: "Sector trend and relative strength", impact: "Positive",
        description: "Technology has outperformed SPY.", evidence_ids: ["sector"] },
        { title: "Sector peer breadth", impact: "Positive", description: "Broad strength; AAPL excluded.", evidence_ids: ["breadth"] }],
      evidence: [{ id: "sector", source: "Yahoo Finance sector market data", source_url: "https://finance.yahoo.com/quote/XLK/" },
        { id: "breadth", source: "Yahoo Finance sector market data", source_url: "https://finance.yahoo.com/quote/XLK/" }] } } } });
  for (const text of ["3 of 6 Outlook categories available", "Two sector events", "Sector peer breadth", "Technology has outperformed SPY", "Source: Yahoo Finance"]) {
    assert.ok(industryHtml.includes(text));
  }
  assert.match(industryHtml, /href="https:\/\/finance.yahoo.com\/quote\/XLK\/"/);
  assert.doesNotMatch(industryHtml, /<details[^>]* open|weighted contribution|\/100/);
  assert.match(html, /Source: SEC/);
  assert.match(html, /rel="noopener noreferrer"/);
  assert.doesNotMatch(html, /Intelligence not connected/);
  assert.doesNotMatch(html, /progressbar|\/100/);
  // Native details/summary supplies default collapsed, pointer and keyboard toggling.
  assert.match(html, /^<details[^>]*><summary/);
  assert.doesNotMatch(html, /<details[^>]* open/);
  assert.match(render({ loading: true }), /Loading Outlook/);
  assert.match(render({ error: "failed" }), /temporarily unavailable/);
  assert.match(render({}), /Outlook data is unavailable/);
  assert.match(render({ data: { status: "unavailable", summary: "Insufficient evidence." } }), /Insufficient evidence/);
  assert.match(render({ data: { status: "placeholder", summary: "Not connected.",
    metadata: { uses_placeholder_data: true }, categories: { company: { status: "insufficient_data" } } } }), /Preview.*Intelligence not connected/);
  assert.match(render({ data: { categories: { company: { status: "error" } } } }), /Temporarily unavailable/);
  const app = await fs.readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
  assert.ok(app.indexOf("<ValuationScorePanel") < app.indexOf("<OutlookPanel"));
  assert.match(app, /outlookRequestRef.current.controller\?\.abort\(\)/);
  assert.match(app, /outlookRequestRef.current.id !== requestId/);
  console.log("Outlook rendering, states, disclosure semantics, and integration tests passed.");
} finally {
  await vite.close();
}

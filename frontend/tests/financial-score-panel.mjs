import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const vite = await createServer({
  server: { middlewareMode: true },
  appType: "custom",
});

try {
  const { default: FinancialScorePanel } = await vite.ssrLoadModule(
    "/src/components/FinancialScorePanel.jsx"
  );
  const {
    getAnalysisErrorNotification,
    isValidAnalysisResponse,
  } = await vite.ssrLoadModule("/src/utils/analysisErrors.js");
  const { default: ToastContainer } = await vite.ssrLoadModule(
    "/src/components/ToastContainer.jsx"
  );
  const { default: ScoreBreakdown } = await vite.ssrLoadModule(
    "/src/components/ScoreBreakdown.jsx"
  );
  const { default: ScorePanel } = await vite.ssrLoadModule(
    "/src/components/ScorePanel.jsx"
  );
  const {
    getOrderValidationNotification,
    getTradeErrorNotification,
    getTradeSuccessNotification,
  } = await vite.ssrLoadModule("/src/utils/tradeNotifications.js");

  const render = (props) => renderToStaticMarkup(
    React.createElement(FinancialScorePanel, props)
  );

  assert.match(render({ data: null, loading: true, error: "" }), /Loading financial data/);
  assert.match(render({ data: null, loading: false, error: "failed" }), /temporarily unavailable/);
  assert.match(render({ data: null, loading: false, error: "" }), /has not been requested/);
  assert.match(render({
    loading: false,
    error: "",
    data: {
      status: "unavailable",
      score: null,
      message: "Financial statements are unavailable.",
      categories: {},
    },
  }), /Financial statements are unavailable/);
  assert.match(render({
    loading: false,
    error: "",
    data: {
      status: "available",
      score: 82,
      label: "Strong",
      coverage: { percentage: 88, confidence: "high" },
      categories: {
        profitability: { score: 25, max_score: 30 },
      },
    },
  }), /82.*100/);
  assert.match(render({
    loading: false,
    error: "",
    data: {
      status: "partial",
      score: 67,
      label: "Fair",
      coverage: { percentage: 62, confidence: "moderate" },
      categories: {
        growth: { score: 18, max_score: 25 },
      },
    },
  }), /Limited Data/);
  const enhancedMetricsMarkup = render({
    loading: false,
    error: "",
    data: {
      status: "partial",
      score: 76.4,
      label: "Strong",
      version: "1.1",
      coverage: { percentage: 84, confidence: "high" },
      categories: {
        profitability: {
          score: 24,
          max_score: 30,
          details: [
            {
              key: "roic", label: "Return on Invested Capital",
              value: 0.184, formatted_value: "18.4%", score: 7.4,
              max_score: 8, status: "excellent", availability: "available",
            },
            {
              key: "return_on_equity", label: "Return on Equity",
              value: null, formatted_value: "N/A", score: null,
              max_score: 5, status: "unavailable", availability: "unavailable",
            },
          ],
        },
      },
    },
  });
  assert.match(enhancedMetricsMarkup, /Return on Invested Capital/);
  assert.match(enhancedMetricsMarkup, /18.4%/);
  assert.match(enhancedMetricsMarkup, /Return on Equity/);
  assert.match(enhancedMetricsMarkup, /N\/A/);
  assert.match(render({
    loading: false,
    error: "",
    data: { status: "available", score: 50 },
  }), /unexpected response/);

  assert.equal(isValidAnalysisResponse({
    ticker: "AAPL",
    chart_data: [],
    technical_score: { score: 80 },
    trade_quality_score: { score: 70 },
  }), true);
  assert.equal(isValidAnalysisResponse({ ticker: "FORD" }), false);
  const invalidTicker = getAnalysisErrorNotification(
    { response: { status: 400 } },
    "ford"
  );
  assert.equal(invalidTicker.type, "warning");
  assert.equal(invalidTicker.title, "Invalid Ticker");
  assert.match(invalidTicker.message, /Ticker "FORD" was not found/);
  assert.equal(
    getAnalysisErrorNotification({ code: "ECONNABORTED" }, "MSFT").title,
    "Analysis Timed Out"
  );
  assert.equal(
    getAnalysisErrorNotification({ request: {} }, "NVDA").title,
    "Backend Unavailable"
  );
  assert.equal(
    getAnalysisErrorNotification({ response: { status: 500 } }, "META").title,
    "Analysis Unavailable"
  );

  const toastMarkup = renderToStaticMarkup(React.createElement(ToastContainer, {
    onDismiss: () => {},
    toasts: [
      { id: 1, type: "success", title: "Trade Executed", message: "Bought AAPL.", phase: "visible" },
      { id: 2, type: "info", title: "Scanner Complete", message: "25 found.", phase: "visible" },
      { id: 3, type: "warning", title: "Invalid Ticker", message: "Not found.", phase: "visible" },
      { id: 4, type: "error", title: "Backend Unavailable", message: "Offline.", phase: "visible" },
    ],
  }));
  assert.equal((toastMarkup.match(/role="alert"/g) || []).length, 4);
  assert.match(toastMarkup, /aria-live="assertive"/);
  assert.match(toastMarkup, /Dismiss Invalid Ticker notification/);

  const scoreComponents = {
    trend: {
      score: 14,
      max_score: 40,
      details: [{
        key: "price_above_sma_20",
        label: "Price Above 20 SMA",
        formatted_value: "Yes",
        score: 14,
        max_score: 14,
        status: "bullish",
        explanation: "Price supports the short-term trend.",
        availability: "available",
      }],
    },
  };
  const breakdownMarkup = renderToStaticMarkup(React.createElement(ScoreBreakdown, {
    scoreLabel: "Technical Score",
    version: "2.0",
    components: scoreComponents,
  }));
  assert.match(breakdownMarkup, /role="progressbar"/);
  assert.doesNotMatch(breakdownMarkup, /score-chevron/);
  assert.doesNotMatch(breakdownMarkup, /aria-expanded/);

  const scorePanelMarkup = renderToStaticMarkup(React.createElement(ScorePanel, {
    title: "Technical Score",
    scoreData: {
      score: 14,
      grade: "Bearish",
      version: "2.0",
      components: scoreComponents,
    },
    embedded: true,
  }));
  assert.match(scorePanelMarkup, /aria-expanded="false"/);
  assert.match(scorePanelMarkup, /Detailed metrics/);
  assert.match(scorePanelMarkup, /Contribution:.*14.*14/);

  assert.deepEqual(
    getTradeSuccessNotification({
      position: { shares: 1 },
      trade: { symbol: "aapl", side: "BUY", shares: 1, price: 332.56 },
    }),
    {
      type: "success",
      title: "Trade Executed",
      message: "Bought 1 share of AAPL at $332.56.",
      duration: 4000,
    }
  );
  assert.equal(
    getTradeSuccessNotification({
      position: { shares: 5 },
      trade: { symbol: "aapl", side: "BUY", shares: 10, price: 332.56 },
    }).message,
    "Bought 10 shares of AAPL at $332.56."
  );
  assert.equal(
    getTradeSuccessNotification({
      position: { shares: 5 },
      trade: { symbol: "aapl", side: "SELL", shares: 2, price: 338.2 },
    }).message,
    "Sold 2 shares of AAPL at $338.20."
  );
  const closedPosition = getTradeSuccessNotification({
    position: null,
    trade: { symbol: "aapl", side: "SELL", shares: 5, price: 338.2 },
  });
  assert.equal(closedPosition.title, "Position Closed");
  assert.equal(closedPosition.message, "Closed 5 shares of AAPL at $338.20.");
  assert.equal(
    getOrderValidationNotification({
      symbol: "AAPL", side: "buy", shares: 0, price: 100,
    }).message,
    "Enter a share quantity greater than zero."
  );
  assert.equal(
    getOrderValidationNotification({
      symbol: "AAPL", side: "buy", shares: 1, price: null,
    }).message,
    "No valid market price is available for AAPL."
  );
  assert.equal(
    getTradeErrorNotification(
      { response: { data: { detail: "Insufficient cash balance for this paper trade" } } },
      { symbol: "AAPL", shares: 10 }
    ).message,
    "Insufficient cash to buy 10 shares of AAPL."
  );
  assert.equal(
    getTradeErrorNotification(
      { response: { data: { detail: "Not enough shares available for this paper trade" } } },
      { symbol: "AAPL", shares: 10 }
    ).message,
    "You do not own enough AAPL shares to complete this sale."
  );
  assert.equal(
    getTradeErrorNotification({ request: {} }, { symbol: "AAPL", shares: 1 }).message,
    "The trading server could not be reached."
  );
  assert.equal(
    getTradeSuccessNotification({ trade: { symbol: "AAPL" } }),
    null
  );

  console.log("Frontend state and toast rendering tests passed.");
} finally {
  await vite.close();
}

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
    default: ValuationScorePanel,
    IntrinsicValueContent,
    ValuationExpandedContent,
  } = await vite.ssrLoadModule(
    "/src/components/ValuationScorePanel.jsx"
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
  const renderValuation = (props) => renderToStaticMarkup(
    React.createElement(ValuationScorePanel, props)
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
      sector: "Technology",
      sector_profile: "technology",
      sector_profile_label: "Technology",
      used_default_profile: false,
      coverage: { percentage: 84, confidence: "high" },
      categories: {
        profitability: {
          score: 24,
          max_score: 30,
          normalization_note: "Category score normalized using 3 of 4 supported metrics. 2 additional metrics are excluded for this sector profile.",
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
            {
              key: "gross_margin", label: "Gross Margin",
              value: null, formatted_value: "N/A", score: null,
              max_score: 0, status: "unsupported_for_sector",
              availability: "unsupported_for_sector",
              reason: "Not used for the Technology sector profile",
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
  assert.match(enhancedMetricsMarkup, /Scoring Profile: Technology/);
  assert.match(enhancedMetricsMarkup, /Unsupported For Sector/);
  assert.match(enhancedMetricsMarkup, /Excluded from score/);
  assert.match(enhancedMetricsMarkup, /3 of 4 supported metrics/);
  assert.match(enhancedMetricsMarkup, /2 additional metrics are excluded/);
  assert.doesNotMatch(enhancedMetricsMarkup, /3 of 4 available metrics/);
  const defaultProfileMarkup = render({
    loading: false,
    error: "",
    data: {
      status: "available",
      score: 60,
      label: "Fair",
      sector_profile: "default",
      sector_profile_label: "General Company",
      used_default_profile: true,
      coverage: { percentage: 100, confidence: "high" },
      categories: {
        profitability: {
          score: 18,
          max_score: 30,
          details: [{
            key: "roic", label: "Return on Invested Capital",
            formatted_value: "12.0%", score: 5.6, max_score: 8,
            status: "strong", availability: "available",
          }],
        },
      },
    },
  });
  assert.match(defaultProfileMarkup, /Scoring Profile: General Company \(default\)/);
  assert.match(render({
    loading: false,
    error: "",
    data: { status: "available", score: 50 },
  }), /unexpected response/);

  assert.match(
    renderValuation({ data: null, loading: true, error: "" }),
    /Loading valuation data/
  );
  assert.match(
    renderValuation({ data: null, loading: false, error: "failed" }),
    /temporarily unavailable/
  );
  assert.match(renderValuation({
    loading: false,
    error: "",
    data: {
      status: "unsupported",
      score: null,
      message: "Relative company valuation is not supported for this instrument.",
    },
  }), /not supported for this instrument/);
  assert.doesNotMatch(renderValuation({
    loading: false,
    error: "",
    data: { status: "unsupported", score: null, message: "Unsupported" },
  }), /role="progressbar"[^>]*aria-label="Valuation Score"/);

  const valuationMarkup = renderValuation({
    loading: false,
    error: "",
    data: {
      status: "fairly_valued",
      status_label: "Fairly Valued",
      availability: "partial",
      score: 64.8,
      scoring_version: "2A.1",
      sector_profile_label: "Technology",
      used_default_profile: false,
      current_price: 212.45,
      currency: "USD",
      coverage: { percentage: 82 },
      categories: {
        relative_valuation: {
          score: 62.4,
          max_score: 100,
          details: [
            {
              key: "forward_pe", label: "Forward P/E",
              value: 23.4, formatted_value: "23.40×",
              score: 14.7, max_score: 20,
              status: "good", availability: "available",
              explanation: "Measures expected earnings valuation.",
            },
            {
              key: "trailing_pe", label: "Trailing P/E",
              value: null, raw_value: -18.2, formatted_value: "N/M",
              score: null, max_score: 12,
              status: "not_meaningful", availability: "not_meaningful",
              reason: "Trailing earnings are negative",
            },
            {
              key: "price_to_book", label: "Price / Book",
              value: null, formatted_value: "N/A",
              score: null, max_score: 0,
              status: "unsupported_for_sector",
              availability: "unsupported_for_sector",
              reason: "Excluded from the Technology valuation profile",
            },
          ],
        },
      },
      intrinsic_value: {
        status: "available",
        score: 67.2,
        score_label: "Fair",
        version: "2B.2",
        fair_value_low: 142,
        fair_value_mid: 151,
        fair_value_high: 160,
        confidence: "moderate",
        price_difference_label: "Discount to Midpoint",
        price_difference_percentage: 0.1325,
        comparison_label: "Below Estimated Fair Value",
        coverage: { weighted_coverage: 0.75 },
        models: [{
          model: "discounted_cash_flow", label: "Discounted Cash Flow",
          status: "available", fair_value_low: 138, fair_value_mid: 149,
          fair_value_high: 161, confidence: "moderate",
        }],
      },
    },
  });
  assert.match(valuationMarkup, /Valuation Score/);
  assert.match(valuationMarkup, /Fairly Valued/);
  assert.match(valuationMarkup, /64.8.*100/);
  assert.doesNotMatch(valuationMarkup, /valuation-score-progress/);
  assert.match(valuationMarkup, /aria-label="Relative Valuation"/);
  assert.match(valuationMarkup, /aria-label="Intrinsic Value"/);
  assert.match(valuationMarkup, /style="width:62.4%"/);
  assert.match(valuationMarkup, /style="width:67.2%"/);
  assert.match(valuationMarkup, /Current Price:.*\$212.45/);
  assert.match(valuationMarkup, /Coverage: 82%/);
  assert.match(valuationMarkup, /aria-expanded="false"/);
  assert.match(valuationMarkup, /Intrinsic Value/);
  assert.match(valuationMarkup, /Relative Valuation/);
  assert.match(valuationMarkup, /Intrinsic Value.*67.2.*100/);
  assert.match(valuationMarkup, /Coverage: 82% · Current Price:.*\$212.45/);
  assert.match(valuationMarkup, /aria-hidden="true"/);
  assert.doesNotMatch(valuationMarkup, /valuation-subsection-toggle/);
  assert.doesNotMatch(valuationMarkup, /valuation-subsection-chevron/);

  const intrinsicFixture = {
    status: "available", score: 67.2, fair_value_low: 142, fair_value_mid: 151,
    fair_value_high: 160, current_price: 131, discount_to_midpoint: 0.1325,
    price_difference_label: "Discount to Midpoint",
    price_difference_percentage: 0.1325,
    confidence: "moderate", comparison_label: "Below Estimated Fair Value",
    coverage: { weighted_coverage: 0.75 },
    models: [
      { model: "discounted_cash_flow", label: "Discounted Cash Flow", status: "available", fair_value_low: 138, fair_value_mid: 149, fair_value_high: 161, confidence: "moderate" },
      { model: "earnings_power", label: "Earnings Power", status: "available", fair_value_low: 130, fair_value_mid: 145, fair_value_high: 160, confidence: "high" },
      { model: "historical_multiple_reversion", label: "Historical Multiple Reversion", status: "unavailable", reason: "History unavailable" },
      { model: "owner_earnings", label: "Owner Earnings", status: "unsupported_for_sector", reason: "Not supported" },
    ],
  };
  const expandedValuation = renderToStaticMarkup(React.createElement(
    ValuationExpandedContent,
    {
      categories: {
        relative_valuation: {
          score: 62.4, max_score: 100,
          details: [{
            key: "forward_pe", label: "Forward P/E", formatted_value: "23.40×",
            score: 14.7, max_score: 20, status: "good", availability: "available",
          }],
        },
      },
      titleId: "valuation-title", profileLabel: "Technology",
      usedDefaultProfile: false, intrinsic: intrinsicFixture, currency: "USD",
    }
  ));
  assert.match(expandedValuation, /Relative Valuation/);
  assert.match(expandedValuation, /Forward P\/E/);
  assert.match(expandedValuation, /23.40×/);
  assert.match(expandedValuation, /Contribution:.*14.7.*20/);
  assert.match(expandedValuation, /Scoring Profile: Technology/);
  assert.match(expandedValuation, /Intrinsic Value/);
  assert.match(expandedValuation, /Estimated Fair Value/);
  assert.match(expandedValuation, /\$142\.00.*\$160\.00/);
  assert.match(expandedValuation, /Midpoint/);
  assert.match(expandedValuation, /Current Price/);
  assert.match(expandedValuation, /Discount to Midpoint/);
  assert.match(expandedValuation, /Confidence/);
  assert.match(expandedValuation, /Model Coverage/);
  assert.match(expandedValuation, /Status/);
  assert.match(expandedValuation, /Below Estimated Fair Value/);
  assert.match(expandedValuation, /Discounted Cash Flow/);
  assert.match(expandedValuation, /Earnings Power/);
  assert.match(expandedValuation, /Historical Multiple Reversion/);
  assert.match(expandedValuation, /Owner Earnings/);
  assert.match(expandedValuation, /Unavailable/);
  assert.match(expandedValuation, /Unsupported/);
  assert.doesNotMatch(expandedValuation, /<button/);
  assert.doesNotMatch(expandedValuation, /aria-expanded/);
  assert.doesNotMatch(expandedValuation, /valuation-subsection-chevron/);

  const premiumMarkup = renderToStaticMarkup(React.createElement(
    IntrinsicValueContent,
    {
      intrinsic: {
        ...intrinsicFixture,
        price_difference_label: "Premium to Midpoint",
        price_difference_percentage: 1.47,
      },
      currency: "USD",
    }
  ));
  assert.match(premiumMarkup, /Premium to Midpoint/);
  assert.match(premiumMarkup, /147.0%/);
  assert.doesNotMatch(premiumMarkup, /-147.0%/);

  const unavailableIntrinsic = renderToStaticMarkup(React.createElement(
    IntrinsicValueContent,
    { intrinsic: { status: "unavailable", message: "Intrinsic value could not be calculated.", models: [] }, currency: "USD" }
  ));
  assert.match(unavailableIntrinsic, /could not be calculated/);

  const unavailableIntrinsicCard = renderValuation({
    loading: false, error: "",
    data: {
      status: "fairly_valued", status_label: "Fairly Valued",
      availability: "available", score: 62.4, scoring_version: "2A.1",
      coverage: { percentage: 100 }, current_price: 100, currency: "USD",
      categories: { relative_valuation: { score: 62.4, max_score: 100, details: [] } },
      intrinsic_value: {
        status: "unavailable", score: null, version: "2B.2",
        message: "Intrinsic value could not be calculated.",
        coverage: { weighted_coverage: 0 }, models: [],
      },
    },
  });
  assert.match(unavailableIntrinsicCard, /Intrinsic Value/);
  assert.match(unavailableIntrinsicCard, /N\/A.*100/);
  assert.match(unavailableIntrinsicCard, /Intrinsic Value score unavailable/);

  assert.match(renderValuation({
    symbol: "MSFT", loading: true, error: "",
    data: { ...JSON.parse(JSON.stringify({
      status: "fairly_valued", availability: "partial", score: 62.4,
      coverage: { percentage: 88 }, categories: {}, symbol: "AAPL",
    })) },
  }), /Loading valuation data/);

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

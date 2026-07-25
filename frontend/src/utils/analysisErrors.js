export function isValidAnalysisResponse(data) {
  return Boolean(
    data
    && typeof data === "object"
    && !Array.isArray(data)
    && typeof data.ticker === "string"
    && data.ticker.trim()
    && Array.isArray(data.chart_data)
    && data.technical_score
    && data.trade_quality_score
  );
}

export function getAnalysisErrorNotification(error, ticker) {
  const symbol = String(ticker || "").trim().toUpperCase();

  if (error?.code === "MALFORMED_ANALYSIS_RESPONSE") {
    return {
      type: "error",
      title: "Unexpected Response",
      message: "The server returned an unexpected analysis response. The current dashboard was preserved.",
    };
  }
  if (error?.code === "ECONNABORTED" || error?.code === "ETIMEDOUT") {
    return {
      type: "warning",
      title: "Analysis Timed Out",
      message: `Analysis for "${symbol}" timed out. Please try again.`,
    };
  }

  const status = error?.response?.status;
  if (status === 400 || status === 404) {
    return {
      type: "warning",
      title: "Invalid Ticker",
      message: `Ticker "${symbol}" was not found.\nPlease verify the symbol and try again.`,
    };
  }
  if (!error?.response) {
    return {
      type: "error",
      title: "Backend Unavailable",
      message: "Could not reach the TradePilot backend. The current dashboard was preserved.",
    };
  }
  if (status >= 500) {
    return {
      type: "error",
      title: "Analysis Unavailable",
      message: "The analysis provider encountered an error. Please try again.",
    };
  }
  return {
    type: "error",
    title: "Analysis Failed",
    message: `Unable to analyze ticker "${symbol}". Please try again.`,
  };
}

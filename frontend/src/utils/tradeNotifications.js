function formatQuantity(value) {
  return Number(value).toLocaleString("en-US", {
    maximumFractionDigits: 4,
  });
}

function formatPrice(value) {
  return Number(value).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function shareLabel(quantity) {
  return Number(quantity) === 1 ? "share" : "shares";
}

export function getOrderValidationNotification({ symbol, side, shares, price }) {
  const cleanSymbol = String(symbol || "").trim().toUpperCase();
  const numericShares = Number(shares);
  const numericPrice = Number(price);

  if (side !== "buy" && side !== "sell") {
    return {
      type: "warning",
      title: "Invalid Order",
      message: "Select Buy or Sell before submitting the order.",
      duration: 5000,
    };
  }
  if (!Number.isFinite(numericShares) || numericShares <= 0) {
    return {
      type: "warning",
      title: "Invalid Order",
      message: "Enter a share quantity greater than zero.",
      duration: 5000,
    };
  }
  if (!cleanSymbol || !Number.isFinite(numericPrice) || numericPrice <= 0) {
    return {
      type: "warning",
      title: "Invalid Order",
      message: `No valid market price is available${cleanSymbol ? ` for ${cleanSymbol}` : ""}.`,
      duration: 5000,
    };
  }
  return null;
}

export function getTradeSuccessNotification(data) {
  const trade = data?.trade;
  const symbol = typeof trade?.symbol === "string"
    ? trade.symbol.trim().toUpperCase()
    : "";
  const side = typeof trade?.side === "string"
    ? trade.side.trim().toUpperCase()
    : "";
  const quantity = Number(trade?.shares);
  const price = Number(trade?.price);

  if (
    !symbol
    || (side !== "BUY" && side !== "SELL")
    || !Number.isFinite(quantity)
    || quantity <= 0
    || !Number.isFinite(price)
    || price <= 0
  ) {
    return null;
  }

  const closedPosition = side === "SELL" && data?.position === null;
  const verb = closedPosition ? "Closed" : side === "BUY" ? "Bought" : "Sold";

  return {
    type: "success",
    title: closedPosition ? "Position Closed" : "Trade Executed",
    message: `${verb} ${formatQuantity(quantity)} ${shareLabel(quantity)} of ${symbol} at ${formatPrice(price)}.`,
    duration: 4000,
  };
}

export function getTradeErrorNotification(error, order) {
  const symbol = String(order?.symbol || "").trim().toUpperCase();
  const quantity = Number(order?.shares);
  const quantityText = Number.isFinite(quantity) && quantity > 0
    ? `${formatQuantity(quantity)} ${shareLabel(quantity)}`
    : "the requested shares";
  const detail = error?.response?.data?.detail;
  const safeDetail = typeof detail === "string"
    ? detail
    : typeof detail?.message === "string"
      ? detail.message
      : "";
  const normalizedDetail = safeDetail.toLowerCase();

  let message;
  if (normalizedDetail.includes("insufficient cash")) {
    message = `Insufficient cash to buy ${quantityText} of ${symbol}.`;
  } else if (
    normalizedDetail.includes("not enough shares")
    || normalizedDetail.includes("insufficient shares")
  ) {
    message = `You do not own enough ${symbol} shares to complete this sale.`;
  } else if (
    normalizedDetail.includes("market price")
    || normalizedDetail.includes("price data")
  ) {
    message = "Market data is temporarily unavailable.";
  } else if (error?.code === "ECONNABORTED" || error?.code === "ETIMEDOUT") {
    message = "The trade request timed out. Please try again.";
  } else if (!error?.response) {
    message = "The trading server could not be reached.";
  } else {
    message = "The order could not be completed.";
  }

  return {
    type: "error",
    title: "Trade Failed",
    message,
    duration: 6000,
  };
}

import { useMemo, useState } from "react";
import { paperBuy, paperSell } from "../api/paperTrading";

function formatCurrency(value) {
  if (!Number.isFinite(value)) return "N/A";

  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  });
}

function QuickTradePanel({
  symbol,
  currentPrice,
  priceChange,
  priceChangePercent,
  onTradeExecuted,
}) {
  const [side, setSide] = useState("buy");
  const [shares, setShares] = useState(1);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("");

  const cleanSymbol = symbol?.trim().toUpperCase() || "";
  const numericShares = Number(shares);
  const numericPrice = Number(currentPrice);
  const totalValue = useMemo(
    () => numericShares * numericPrice,
    [numericShares, numericPrice]
  );
  const hasPriceChange =
    Number.isFinite(Number(priceChange)) &&
    Number.isFinite(Number(priceChangePercent));
  const priceChangeClass = Number(priceChange) >= 0 ? "positive" : "negative";
  const canSubmit =
    cleanSymbol &&
    Number.isFinite(numericPrice) &&
    numericPrice > 0 &&
    Number.isFinite(numericShares) &&
    numericShares > 0 &&
    !loading;

  const updateShares = (nextShares) => {
    const value = Number(nextShares);

    if (!Number.isFinite(value)) {
      setShares("");
      return;
    }

    setShares(Math.max(0, value));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!canSubmit) return;

    setLoading(true);
    setMessage("");
    setMessageType("");

    try {
      const tradeRequest = side === "buy" ? paperBuy : paperSell;
      await tradeRequest(cleanSymbol, numericShares, numericPrice);

      setMessage(
        `${side === "buy" ? "Bought" : "Sold"} ${numericShares} ${cleanSymbol}`
      );
      setMessageType("success");
      onTradeExecuted?.();
    } catch (error) {
      const detail = error.response?.data?.detail;
      setMessage(detail || "Trade could not be executed.");
      setMessageType("error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="panel-box quick-trade-panel" onSubmit={handleSubmit}>
      <div className="panel-header">
        <h3>Quick Trade</h3>
        <span>Paper</span>
      </div>

      <div className="trade-toggle" aria-label="Trade side">
        <button
          type="button"
          className={side === "buy" ? "active" : ""}
          onClick={() => setSide("buy")}
        >
          Buy
        </button>
        <button
          type="button"
          className={side === "sell" ? "active sell" : "sell"}
          onClick={() => setSide("sell")}
        >
          Sell
        </button>
      </div>

      <div className="quick-trade-row">
        <span>Current Price</span>
        <strong>
          {formatCurrency(numericPrice)}
          {hasPriceChange && (
            <em className={priceChangeClass}>
              {" "}
              ({Number(priceChange) >= 0 ? "+" : ""}
              {Number(priceChange).toFixed(2)}{" "}
              {Number(priceChangePercent) >= 0 ? "+" : ""}
              {Number(priceChangePercent).toFixed(2)}%)
            </em>
          )}
        </strong>
      </div>

      <label className="share-control">
        <span>Shares</span>
        <div>
          <button
            type="button"
            onClick={() => updateShares((numericShares || 0) - 1)}
            disabled={loading || numericShares <= 0}
          >
            -
          </button>
          <input
            type="number"
            min="0"
            step="1"
            value={shares}
            onChange={(event) => updateShares(event.target.value)}
          />
          <button
            type="button"
            onClick={() => updateShares((numericShares || 0) + 1)}
            disabled={loading}
          >
            +
          </button>
        </div>
      </label>

      <div className="quick-trade-row total-row">
        <span>Total Value</span>
        <strong>{formatCurrency(totalValue)}</strong>
      </div>

      <button
        type="submit"
        className={`trade-submit ${side}`}
        disabled={!canSubmit}
      >
        {loading
          ? "Executing..."
          : `${side === "buy" ? "Buy" : "Sell"} ${numericShares || 0} ${
              cleanSymbol || "SYMBOL"
            }`}
      </button>

      {message && (
        <p className={`trade-message ${messageType}`}>
          {message}
        </p>
      )}

      <p className="trade-note">
        <span>i</span>
        Orders are executed at current market price.
      </p>
    </form>
  );
}

export default QuickTradePanel;

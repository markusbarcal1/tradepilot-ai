import { useMemo, useRef, useState } from "react";
import { paperBuy, paperSell } from "../api/paperTrading";
import useToast from "../hooks/useToast";
import {
  getOrderValidationNotification,
  getTradeErrorNotification,
  getTradeSuccessNotification,
} from "../utils/tradeNotifications";

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
  const { showToast } = useToast();
  const submittingRef = useRef(false);
  const [side, setSide] = useState("buy");
  const [shares, setShares] = useState(1);
  const [loading, setLoading] = useState(false);

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

    if (submittingRef.current) return;

    const order = {
      symbol: cleanSymbol,
      side,
      shares: numericShares,
      price: numericPrice,
    };
    const validationNotification = getOrderValidationNotification(order);
    if (validationNotification) {
      showToast(validationNotification);
      return;
    }

    submittingRef.current = true;
    setLoading(true);

    try {
      const tradeRequest = side === "buy" ? paperBuy : paperSell;
      const response = await tradeRequest(cleanSymbol, numericShares, numericPrice);
      const successNotification = getTradeSuccessNotification(response.data);

      if (!successNotification) {
        const malformedResponseError = new Error("Malformed trade response");
        malformedResponseError.code = "MALFORMED_TRADE_RESPONSE";
        throw malformedResponseError;
      }

      showToast(successNotification);
      try {
        onTradeExecuted?.();
      } catch (refreshError) {
        console.error("Trade succeeded, but portfolio refresh could not start:", refreshError);
      }
    } catch (error) {
      showToast(getTradeErrorNotification(error, order));
    } finally {
      submittingRef.current = false;
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
        disabled={loading}
      >
        {loading
          ? "Executing..."
          : `${side === "buy" ? "Buy" : "Sell"} ${numericShares || 0} ${
              cleanSymbol || "SYMBOL"
            }`}
      </button>

      <p className="trade-note">
        <span>i</span>
        Orders are executed at current market price.
      </p>
    </form>
  );
}

export default QuickTradePanel;

import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
});

export function isRequestCanceled(error) {
  return axios.isCancel(error);
}

export function analyzeTicker(symbol, period, interval, options = {}) {
  return api.get(`/analyze/${symbol}`, {
    params: {
      period,
      interval,
    },
    signal: options.signal,
  });
}

export function analyzeTickers(symbols, period, interval, options = {}) {
  return api.post(
    "/analyze/batch",
    {
      symbols,
      period,
      interval,
    },
    {
      signal: options.signal,
    }
  );
}

export function validateTicker(symbol, options = {}) {
  return api.get(`/validate/${symbol}`, {
    signal: options.signal,
  });
}

export function scanMarket(period, interval, limit = 10, options = {}) {
  return api.get("/scan", {
    params: {
      period,
      interval,
      limit,
      universe: options.universe,
      max_symbols: options.maxSymbols,
    },
    signal: options.signal,
  });
}

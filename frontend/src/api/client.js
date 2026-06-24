import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
});

export function analyzeTicker(symbol, period, interval) {
  return api.get(`/analyze/${symbol}`, {
    params: {
      period,
      interval,
    },
  });
}

export function validateTicker(symbol) {
  return api.get(`/validate/${symbol}`);
}

export function scanMarket(period, interval, limit = 10) {
  return api.get("/scan", {
    params: {
      period,
      interval,
      limit,
    },
  });
}

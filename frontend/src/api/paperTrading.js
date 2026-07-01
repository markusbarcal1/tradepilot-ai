import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
});

export function getPaperAccount() {
  return api.get("/paper/account");
}

export function getPaperPositions() {
  return api.get("/paper/positions");
}

export function getPaperPortfolio() {
  return api.get("/paper/portfolio");
}

export function getPaperTrades() {
  return api.get("/paper/trades");
}

export function paperBuy(symbol, shares, price) {
  return api.post("/paper/buy", {
    symbol,
    shares,
    price,
  });
}

export function paperSell(symbol, shares, price) {
  return api.post("/paper/sell", {
    symbol,
    shares,
    price,
  });
}

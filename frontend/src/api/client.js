import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
});

export function isRequestCanceled(error) {
  return axios.isCancel(error) || error?.name === "AbortError";
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

function buildScanParams(period, interval, limit, options) {
  const params = new URLSearchParams();

  params.set("period", period);
  params.set("interval", interval);
  params.set("limit", String(limit));

  if (options.universe) {
    params.set("universe", options.universe);
  }

  if (Number.isFinite(options.maxSymbols)) {
    params.set("max_symbols", String(options.maxSymbols));
  }

  return params;
}

function parseStreamEvent(rawEvent) {
  const lines = rawEvent.split("\n");
  let event = "message";
  const dataLines = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }

  return {
    event,
    data: dataLines.length ? JSON.parse(dataLines.join("\n")) : null,
  };
}

export async function streamScanMarket(
  period,
  interval,
  limit = 10,
  options = {},
  onEvent = () => {}
) {
  const params = buildScanParams(period, interval, limit, options);
  const response = await fetch(`${API_BASE_URL}/scan/stream?${params}`, {
    signal: options.signal,
  });

  if (!response.ok) {
    throw new Error(`Scanner stream failed with status ${response.status}`);
  }

  if (!response.body) {
    throw new Error("Scanner stream is not readable");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalData = null;

  while (true) {
    const { value, done } = await reader.read();

    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    let boundaryIndex = buffer.indexOf("\n\n");
    while (boundaryIndex !== -1) {
      const rawEvent = buffer.slice(0, boundaryIndex).trim();
      buffer = buffer.slice(boundaryIndex + 2);

      if (rawEvent) {
        const streamEvent = parseStreamEvent(rawEvent);
        onEvent(streamEvent);

        if (streamEvent.event === "complete") {
          finalData = streamEvent.data;
        }
      }

      boundaryIndex = buffer.indexOf("\n\n");
    }
  }

  if (!finalData) {
    throw new Error("Scanner stream ended before returning results");
  }

  return finalData;
}

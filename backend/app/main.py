import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.services.analyzer import analyze_ticker, analyze_tickers
from app.services.financial_analysis import analyze_financials
from app.services.market_data import MarketDataError, get_price_history
from app.services.scanner import scan_market, stream_scan_market
from app.paper_trading import init_paper_trading_db, router as paper_trading_router


class BatchAnalyzeRequest(BaseModel):
    symbols: list[str]
    period: str = "1y"
    interval: str = "1d"

app = FastAPI(title="TradePilot AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_paper_trading_db()


app.include_router(paper_trading_router)


@app.get("/")
def root():
    return {"message": "TradePilot AI backend is running"}


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/validate/{ticker}")
def validate_ticker(ticker: str):
    try:
        get_price_history(ticker.strip().upper(), period="5d", interval="1d")
        return {"valid": True, "status": "valid"}
    except MarketDataError as exc:
        # Provider availability is not ticker validity. Returning 503 prevents
        # callers from permanently presenting valid symbols as invalid.
        raise HTTPException(
            status_code=404 if getattr(exc, "invalid_ticker", False) else 503,
            detail={
                "code": exc.category,
                "message": str(exc),
                "retryable": exc.retryable,
            },
        ) from exc

@app.get("/analyze/{ticker}")
def analyze(ticker: str, period: str = "max", interval: str = "1d"):
    try:
        return analyze_ticker(ticker, period, interval)
    except MarketDataError as e:
        raise HTTPException(
            status_code=404 if getattr(e, "invalid_ticker", False) else 503,
            detail={"code": e.category, "message": str(e), "retryable": e.retryable},
        ) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/financial-analysis/{ticker}")
def financial_analysis(ticker: str):
    return analyze_financials(ticker)

@app.post("/analyze/batch")
def batch_analyze(request: BatchAnalyzeRequest):
    if not request.symbols:
        raise HTTPException(status_code=400, detail="At least one symbol is required")

    return analyze_tickers(request.symbols, request.period, request.interval)
    
def _parse_eligibility_payload(payload: str | None):
    if not payload:
        return None

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None


@app.get("/scan")
def scan(
    period: str = "1y",
    interval: str = "1d",
    limit: int = 10,
    universe: str = "sp500",
    max_symbols: int | None = None,
    audit: bool = False,
    max_workers: int | None = None,
    eligibility: str | None = None,
):
    try:
        return scan_market(period, interval, limit, universe, max_symbols, audit=audit, max_workers=max_workers, eligibility=_parse_eligibility_payload(eligibility))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/scan/stream")
def scan_stream(
    period: str = "1y",
    interval: str = "1d",
    limit: int = 10,
    universe: str = "sp500",
    max_symbols: int | None = None,
    audit: bool = False,
    max_workers: int | None = None,
    eligibility: str | None = None,
):
    def format_stream_message(message):
        return (
            f"event: {message['event']}\n"
            f"data: {json.dumps(message['data'])}\n\n"
        )

    try:
        stream = stream_scan_market(period, interval, limit, universe, max_symbols, audit=audit, max_workers=max_workers, eligibility=_parse_eligibility_payload(eligibility))
        first_message = next(stream)

        def event_stream():
            yield format_stream_message(first_message)

            for message in stream:
                yield format_stream_message(message)

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    

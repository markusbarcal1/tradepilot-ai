from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.services.analyzer import analyze_ticker, analyze_tickers
from app.services.scanner import scan_market
from app.paper_trading import init_paper_trading_db, router as paper_trading_router
import yfinance as yf


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
        stock = yf.Ticker(ticker.upper())
        history = stock.history(period="5d")

        return {
            "valid": not history.empty
        }

    except Exception:
        return {
            "valid": False
        }

@app.get("/analyze/{ticker}")
def analyze(ticker: str, period: str = "max", interval: str = "1d"):
    try:
        return analyze_ticker(ticker, period, interval)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/analyze/batch")
def batch_analyze(request: BatchAnalyzeRequest):
    if not request.symbols:
        raise HTTPException(status_code=400, detail="At least one symbol is required")

    return analyze_tickers(request.symbols, request.period, request.interval)
    
@app.get("/scan")
def scan(
    period: str = "1y",
    interval: str = "1d",
    limit: int = 10,
    universe: str = "test",
    max_symbols: int = 25,
):
    try:
        return scan_market(period, interval, limit, universe, max_symbols)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    

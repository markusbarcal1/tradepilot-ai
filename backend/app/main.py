from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.services.analyzer import analyze_ticker

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


@app.get("/")
def root():
    return {"message": "TradePilot AI backend is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/analyze/{ticker}")
def analyze(ticker: str, period: str = "max", interval: str = "1d"):
    try:
        return analyze_ticker(ticker, period, interval)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
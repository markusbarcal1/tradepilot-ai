import json

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field, JsonValue

from app.auth import CurrentUser, get_current_user
from app.db import session_scope
from app.paper_trading import normalize_symbol
from app.repositories.preferences import PreferencesRepository
from app.repositories.watchlist import WatchlistRepository


MAX_SCANNER_PREFERENCES_BYTES = 16_384
router = APIRouter(tags=["user data"])


class WatchlistRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)


@router.get("/watchlist")
def read_watchlist(current_user: CurrentUser = Depends(get_current_user)):
    with session_scope() as session:
        symbols = WatchlistRepository(session).list_symbols(current_user.user_id)
        return {"symbols": symbols}


@router.post("/watchlist")
def add_watchlist_symbol(
    request: WatchlistRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    symbol = normalize_symbol(request.symbol)
    with session_scope() as session:
        repository = WatchlistRepository(session)
        repository.add(current_user.user_id, symbol)
        return {"symbols": repository.list_symbols(current_user.user_id)}


@router.delete("/watchlist/{symbol}")
def remove_watchlist_symbol(
    symbol: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    normalized = normalize_symbol(symbol)
    with session_scope() as session:
        repository = WatchlistRepository(session)
        repository.remove(current_user.user_id, normalized)
        return {"symbols": repository.list_symbols(current_user.user_id)}


@router.get("/preferences/scanner")
def read_scanner_preferences(
    current_user: CurrentUser = Depends(get_current_user),
):
    with session_scope() as session:
        return PreferencesRepository(session).get(current_user.user_id)


@router.put("/preferences/scanner")
def update_scanner_preferences(
    preferences: dict[str, JsonValue] = Body(...),
    current_user: CurrentUser = Depends(get_current_user),
):
    serialized = json.dumps(preferences, separators=(",", ":"))
    if len(serialized.encode("utf-8")) > MAX_SCANNER_PREFERENCES_BYTES:
        raise HTTPException(status_code=413, detail="Scanner preferences are too large")
    with session_scope() as session:
        PreferencesRepository(session).upsert(current_user.user_id, preferences)
        return preferences

"""Outlook-only single-flight history reuse; chart/scanner behavior is unchanged."""
from app.services.market_data import get_price_history
from .transport import Cache


def get_adjusted_outlook_history(symbol, period="6mo", interval="1d"):
    """Yahoo prices adjusted for splits and distributions; not a total-return index."""
    return get_price_history(symbol, period, interval, auto_adjust=True)


class OutlookHistory:
    def __init__(self, settings, loader=None):
        self.loader = loader or get_adjusted_outlook_history
        self.ttl = settings.outlook_market_cache_ttl
        self.cache = Cache(settings.outlook_failure_cache_ttl, capacity=128)

    def __call__(self, symbol, period="6mo", interval="1d"):
        return self.cache.get((symbol, period, interval),
                              lambda: self.loader(symbol, period, interval), self.ttl)

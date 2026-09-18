"""Process-local provider instances and caches, configured once per backend process."""
from functools import lru_cache

from app.config import settings
from .sec import SecEvidenceProvider
from .fred import FredEvidenceProvider
from .market import MarketEvidenceProvider
from .industry import IndustryEvidenceProvider
from .history import OutlookHistory


@lru_cache(maxsize=1)
def configured_providers():
    history = OutlookHistory(settings)
    return [SecEvidenceProvider(settings), FredEvidenceProvider(settings),
            MarketEvidenceProvider(settings, history=history), IndustryEvidenceProvider(settings, history=history)]

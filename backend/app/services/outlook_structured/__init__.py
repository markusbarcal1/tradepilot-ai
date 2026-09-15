"""Process-local provider instances and caches, configured once per backend process."""
from functools import lru_cache

from app.config import settings
from .sec import SecEvidenceProvider
from .fred import FredEvidenceProvider
from .market import MarketEvidenceProvider


@lru_cache(maxsize=1)
def configured_providers():
    return [SecEvidenceProvider(settings), FredEvidenceProvider(settings), MarketEvidenceProvider(settings)]

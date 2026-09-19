"""Process-local provider instances and caches, configured once per backend process."""
from functools import lru_cache

from app.config import settings
from .sec import SecEvidenceProvider
from .fred import FredEvidenceProvider
from .market import MarketEvidenceProvider
from .industry import IndustryEvidenceProvider
from .history import OutlookHistory
from .geopolitical import GeopoliticalEvidenceProvider


@lru_cache(maxsize=1)
def configured_providers():
    from app.services.outlook_events import FomcEventProvider, MacroEventProvider
    history = OutlookHistory(settings)
    industry = IndustryEvidenceProvider(settings, history=history)
    return [SecEvidenceProvider(settings), FredEvidenceProvider(settings),
            MarketEvidenceProvider(settings, history=history), industry,
            GeopoliticalEvidenceProvider(settings, metadata=industry.metadata,
                                         classification_cache=industry.classifications),
            FomcEventProvider(settings, metadata=industry.metadata, classification_cache=industry.classifications),
            MacroEventProvider(settings, metadata=industry.metadata, classification_cache=industry.classifications)]

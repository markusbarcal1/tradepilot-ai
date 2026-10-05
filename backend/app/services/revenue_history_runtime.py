"""Process-lifetime owner for default-off revenue-history Analyze integration."""
from functools import lru_cache

from app.config import settings
from app.services.outlook_structured.revenue_filing_document import RevenueFilingDocumentRetriever
from app.services.outlook_structured.revenue_history_snapshot import RevenueHistorySnapshotService
from app.services.outlook_structured.sec_history import SecHistoricalFinancialProvider


@lru_cache(maxsize=1)
def get_revenue_history_snapshot_service():
    """Construct once so historical/document/snapshot caches and single-flights persist."""
    historical = SecHistoricalFinancialProvider(settings,
        enabled=settings.outlook_historical_revenue_enabled)
    documents = RevenueFilingDocumentRetriever(
        user_agent=settings.outlook_sec_user_agent,
        timeout=settings.outlook_http_timeout,
        success_ttl=settings.outlook_sec_history_cache_ttl,
        failure_ttl=settings.outlook_failure_cache_ttl,
        request_interval=settings.outlook_sec_request_interval)
    return RevenueHistorySnapshotService(settings,
        acquire_history=historical.get_acquisition,
        retrieve_documents=documents.retrieve)

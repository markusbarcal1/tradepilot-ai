"""Unregistered direct-history-first revenue snapshot orchestration."""
from concurrent.futures import Future
import hashlib, json, re
from threading import RLock
from app.models.outlook_revenue_filing_selection import RevenueFilingQuarterAnchor, RevenueFilingSelectionRequest
from app.models.outlook_revenue_history_snapshot import RevenueHistoricalAcquisition, RevenueHistorySnapshotResult, RevenueSnapshotRequestAccounting
from .revenue_filing_selection import select_revenue_operand_filings
from .revenue_history_series import adapt_historical_revenue, assemble_revenue_historical_series
from .revenue_q4_derivation import derive_revenue_q4
from .revenue_q4_reconciliation import reconcile_revenue_q4
from .revenue_q4_runtime_input import build_revenue_q4_runtime_input
from .revenue_research import project_revenue_research
from app.models.outlook_revenue_research import RevenueResearchProjectionResult

SNAPSHOT_POLICY = "revenue-history-snapshot-1"
_QUARTERS = ("Q1", "Q2", "Q3", "Q4")
def _index(year, quarter): return year * 4 + _QUARTERS.index(quarter)

def projection_from_revenue_snapshot(result):
    """Map orchestration state to the existing projection contract; no financial logic."""
    if result.projection is not None:
        return result.projection
    if result.state == "conflict":
        return RevenueResearchProjectionResult(state="conflict", reasons=result.reasons or ("revenue_snapshot_conflict",))
    return RevenueResearchProjectionResult(state="unavailable",
        reasons=result.reasons or ("revenue_snapshot_unavailable",))

def identify_useful_q4_target(snapshot):
    """Choose the sole latest gap whose insertion yields a >=5-quarter identity run."""
    rows = [row for row in snapshot.observations if adapt_historical_revenue(row) is not None]
    grouped = {}
    for row in rows: grouped.setdefault((row.fiscal_year, row.fiscal_quarter), []).append(row)
    candidates = []
    for year in sorted({row.fiscal_year for row in rows}):
        keys = [(year, role) for role in ("Q1", "Q2", "Q3")]
        if any(len(grouped.get(key, ())) != 1 for key in keys) or grouped.get((year, "Q4")):
            continue
        q4 = _index(year, "Q4"); indices = {_index(*key) for key in grouped} | {q4}
        run = {q4}; cursor = q4 - 1
        while cursor in indices: run.add(cursor); cursor -= 1
        cursor = q4 + 1
        while cursor in indices: run.add(cursor); cursor += 1
        if len(run) >= 5: candidates.append((max(run), len(run), year))
    if not candidates: return "none", None
    score = max((latest, length) for latest, length, _ in candidates)
    years = [year for latest, length, year in candidates if (latest, length) == score]
    if len(years) != 1: return "ambiguous", None
    year = years[0]
    anchors = tuple(RevenueFilingQuarterAnchor(role=role,
        report_period_end=grouped[(year, role)][0].period_end) for role in ("Q1", "Q2", "Q3"))
    return "selected", RevenueFilingSelectionRequest(ticker=snapshot.ticker,
        issuer=snapshot.issuer, cik=snapshot.cik, target_fiscal_year=year, quarter_anchors=anchors)

def _fingerprint(acquisition, q4_enabled, **parts):
    observations = [{"id": row.observation_id, "fy": row.fiscal_year, "fq": row.fiscal_quarter,
        "start": row.period_start.isoformat(), "end": row.period_end.isoformat(),
        "value": str(row.normalized_value), "accession": row.accession}
        for row in acquisition.snapshot.observations if row.metric == "revenue"]
    content = {"policy": SNAPSHOT_POLICY, "historical": acquisition.evidence_fingerprint,
        "observations": observations, "q4_enabled": q4_enabled}
    for name, value in parts.items():
        if name == "retrieval" and value is not None:
            content[name] = [row.fingerprint for row in value.documents]
        elif name == "runtime" and value is not None: content[name] = value.evidence_fingerprint
        elif value is not None: content[name] = value.model_dump(mode="json")
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()

class RevenueHistorySnapshotService:
    """Compose reviewed policies; intentionally absent from production registration."""
    def __init__(self, settings, *, acquire_history, retrieve_documents,
            select_filings=select_revenue_operand_filings, build_runtime_input=build_revenue_q4_runtime_input,
            derive_q4=derive_revenue_q4, reconcile_q4=reconcile_revenue_q4,
            assemble_series=assemble_revenue_historical_series, project_research=project_revenue_research):
        self.settings, self.acquire_history = settings, acquire_history
        self.select_filings, self.retrieve_documents = select_filings, retrieve_documents
        self.build_runtime_input, self.derive_q4, self.reconcile_q4 = build_runtime_input, derive_q4, reconcile_q4
        self.assemble_series, self.project_research = assemble_series, project_research
        self._lock, self._flights = RLock(), {}

    def get_snapshot(self, ticker):
        symbol = str(ticker).strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.-]{0,15}", symbol): return self._empty(symbol, "invalid_ticker")
        with self._lock:
            future = self._flights.get(symbol); leader = future is None
            if leader: future = Future(); self._flights[symbol] = future
        if not leader: return future.result()
        try:
            result = self._compose(symbol); future.set_result(result); return result
        except Exception as exc:
            future.set_exception(exc); raise
        finally:
            with self._lock:
                if self._flights.get(symbol) is future: del self._flights[symbol]

    def _empty(self, ticker, reason):
        return RevenueHistorySnapshotResult(snapshot_policy=SNAPSHOT_POLICY, ticker=ticker,
            state="unavailable", reasons=(reason,), q4_skip_reason=reason,
            request_accounting=RevenueSnapshotRequestAccounting())

    def _accounting(self, acquisition, documents=None):
        logical = acquisition.logical_requests; attempts = acquisition.http_attempts
        document_attempts = documents.http_attempts_charged if documents else 0
        return RevenueSnapshotRequestAccounting(acquisition_cache_state=acquisition.cache_state,
            historical_logical_requests=logical,
            historical_http_attempts=attempts, document_accounting=documents,
            total_sec_http_attempts=attempts + document_attempts)

    def _compose(self, ticker):
        if not self.settings.outlook_historical_revenue_enabled: return self._empty(ticker, "feature_disabled")
        if (not re.search(r"\S+@\S+\.\S+", self.settings.outlook_sec_user_agent)
                or self.settings.outlook_http_attempts != 1): return self._empty(ticker, "sec_configuration_invalid")
        try: acquisition = self.acquire_history(ticker)
        except Exception: return self._empty(ticker, "historical_acquisition_unavailable")
        if not isinstance(acquisition, RevenueHistoricalAcquisition): return self._empty(ticker, "historical_acquisition_unavailable")
        historical = acquisition.snapshot
        adapted = tuple(filter(None, (adapt_historical_revenue(row) for row in historical.observations)))
        series = self.assemble_series(adapted); projection = self.project_research(series)
        accounting = self._accounting(acquisition)
        if projection.state == "available" and series.research_eligible:
            return RevenueHistorySnapshotResult(snapshot_policy=SNAPSHOT_POLICY, ticker=ticker,
                state="available", historical_evidence_fingerprint=acquisition.evidence_fingerprint,
                q4_skip_reason="direct_history_eligible", series=series, projection=projection,
                evidence_fingerprint=_fingerprint(acquisition, self.settings.outlook_historical_revenue_q4_derivation_enabled,
                    series=series, projection=projection), request_accounting=accounting)
        if not self.settings.outlook_historical_revenue_q4_derivation_enabled:
            return RevenueHistorySnapshotResult(snapshot_policy=SNAPSHOT_POLICY, ticker=ticker,
                state="conflict" if projection.state == "conflict" else "insufficient_data",
                reasons=("q4_derivation_disabled", *projection.reasons),
                historical_evidence_fingerprint=acquisition.evidence_fingerprint,
                q4_skip_reason="q4_derivation_disabled", series=series, projection=projection,
                request_accounting=accounting)
        target_state, request = identify_useful_q4_target(historical)
        if target_state != "selected":
            reason = "ambiguous_q4_repair_target" if target_state == "ambiguous" else "no_useful_q4_gap"
            return RevenueHistorySnapshotResult(snapshot_policy=SNAPSHOT_POLICY, ticker=ticker,
                state="insufficient_data", reasons=(reason,), historical_evidence_fingerprint=acquisition.evidence_fingerprint,
                q4_considered=True, q4_skip_reason=reason, series=series, projection=projection,
                request_accounting=accounting)
        if acquisition.submissions is None:
            return RevenueHistorySnapshotResult(snapshot_policy=SNAPSHOT_POLICY, ticker=ticker,
                state="unavailable", reasons=("submissions_metadata_unavailable",),
                historical_evidence_fingerprint=acquisition.evidence_fingerprint, q4_considered=True,
                q4_attempted=True, target_fiscal_year=request.target_fiscal_year, series=series,
                projection=projection, request_accounting=accounting)
        selection = self.select_filings(request, acquisition.submissions)
        if selection.state != "selected": return self._failure(ticker, acquisition, accounting, series, projection,
            "conflict" if selection.state in {"ambiguous", "conflict"} else "insufficient_data",
            "filing_selection_failed", request, selection=selection)
        retrieval = self.retrieve_documents(selection); accounting = self._accounting(acquisition, retrieval.request_accounting)
        if retrieval.state != "available": return self._failure(ticker, acquisition, accounting, series, projection,
            "conflict" if retrieval.state == "conflict" else "insufficient_data", "document_retrieval_failed",
            request, selection=selection, retrieval=retrieval)
        runtime = self.build_runtime_input(selection, retrieval)
        if runtime.state != "ready": return self._failure(ticker, acquisition, accounting, series, projection,
            "conflict" if runtime.state == "conflict" else "insufficient_data", "runtime_input_failed",
            request, selection=selection, retrieval=retrieval, runtime_input=runtime)
        derivation = self.derive_q4(runtime.derivation_input)
        if derivation.state != "derived": return self._failure(ticker, acquisition, accounting, series, projection,
            "conflict" if derivation.state == "conflict" else "insufficient_data", "derivation_failed",
            request, selection=selection, retrieval=retrieval, runtime_input=runtime, derivation=derivation)
        reconciliation = self.reconcile_q4(direct=None, derived=derivation.observation)
        if reconciliation.state != "available": return self._failure(ticker, acquisition, accounting, series, projection,
            "conflict" if reconciliation.state == "conflict" else "insufficient_data", "reconciliation_failed",
            request, selection=selection, retrieval=retrieval, runtime_input=runtime,
            derivation=derivation, reconciliation=reconciliation)
        final_series = self.assemble_series(adapted, reconciled_q4=reconciliation)
        final_projection = self.project_research(final_series)
        state = "available" if final_projection.state == "available" else "conflict" if final_projection.state == "conflict" else "insufficient_data"
        fingerprint = _fingerprint(acquisition, True, selection=selection, retrieval=retrieval,
            runtime=runtime, derivation=derivation, reconciliation=reconciliation,
            series=final_series, projection=final_projection) if state == "available" else None
        return RevenueHistorySnapshotResult(snapshot_policy=SNAPSHOT_POLICY, ticker=ticker, state=state,
            reasons=() if state == "available" else ("final_projection_unavailable",),
            historical_evidence_fingerprint=acquisition.evidence_fingerprint, q4_considered=True,
            q4_attempted=True, target_fiscal_year=request.target_fiscal_year, selection=selection,
            retrieval=retrieval, runtime_input=runtime, derivation=derivation,
            reconciliation=reconciliation, series=final_series, projection=final_projection,
            evidence_fingerprint=fingerprint, request_accounting=accounting)

    def _failure(self, ticker, acquisition, accounting, series, projection, state, reason, request, **stages):
        return RevenueHistorySnapshotResult(snapshot_policy=SNAPSHOT_POLICY, ticker=ticker, state=state,
            reasons=(reason,), historical_evidence_fingerprint=acquisition.evidence_fingerprint,
            q4_considered=True, q4_attempted=True, target_fiscal_year=request.target_fiscal_year,
            series=series, projection=projection, request_accounting=accounting, **stages)

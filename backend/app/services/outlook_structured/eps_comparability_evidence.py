"""Deterministic, bounded certification of retrospective EPS adjustment language."""
from dataclasses import dataclass
import re
from urllib.parse import urlsplit

from app.models.outlook_financial_history import AnnualEpsComparabilityEvidence
from .documents import parse_filing


POLICY_VERSION = "sec-filing-explicit-retrospective-per-share-1"
MAX_DOCUMENT_REQUESTS = 2
MAX_EXTRACTED_TEXT_CHARS = 1_000_000
_NUMBER = r"(?:one|two|three|four|five|six|seven|eight|nine|ten|twenty|\d+)"
_ACTION = re.compile(rf"\b({_NUMBER})[ -]for[ -]({_NUMBER})\s+(reverse\s+)?stock split\b", re.I)
_RETROSPECTIVE = re.compile(r"\b(?:retroactively|retrospectively)\s+adjusted\b", re.I)
_PER_SHARE = re.compile(r"\bper[ -]share\s+amounts?\b", re.I)
SAFE_REASON_MAP = {
    "retrospective_adjustment_statement_missing": "missing_adjustment_statement",
    "retrospective_adjustment_statement_ambiguous": "ambiguous_adjustment_statement",
    "url_policy_rejected": "invalid_document_binding",
    "document_text_limit_exceeded": "document_oversized",
    "unsupported_document_encoding": "document_invalid",
    "unsupported_corporate_actions": "unsupported_corporate_action",
    "eps_document_request_budget_exceeded": "request_budget_exhausted",
}


def _safe_reason(reason):
    return SAFE_REASON_MAP.get(reason, "document_unavailable")


@dataclass(frozen=True)
class EpsComparabilityEvidenceResult:
    evidence: tuple[AnnualEpsComparabilityEvidence, ...] = ()
    logical_documents: int = 0
    http_attempts: int = 0
    cache_hits: int = 0
    failures: int = 0
    reasons: tuple[str, ...] = ()


def _primary_document(source_url):
    path = urlsplit(source_url).path
    return path.rsplit("/", 1)[-1] if "/" in path else ""


def _certify_document(row, body):
    try:
        html = body.decode("utf-8")
    except UnicodeDecodeError:
        return None, "unsupported_document_encoding"
    text = parse_filing(html).text
    if not text or len(text) > MAX_EXTRACTED_TEXT_CHARS:
        return None, "document_text_limit_exceeded"
    normalized = re.sub(r"\s+", " ", text)
    matches = []
    sentences = [match.group(0) for match in re.finditer(r"[^.!?]+[.!?]?", normalized)
        if match.group(0).strip()]
    for index, sentence in enumerate(sentences):
        if not _RETROSPECTIVE.search(sentence):
            continue
        window = " ".join(sentences[max(0, index - 1):index + 1])
        if not _PER_SHARE.search(window):
            continue
        actions = {(match[1].lower(), match[2].lower(), bool(match[3]))
            for match in _ACTION.finditer(window)}
        if actions:
            matches.append(actions)
    distinct = {tuple(sorted(actions)) for actions in matches}
    if not distinct:
        return None, "retrospective_adjustment_statement_missing"
    if len(distinct) != 1:
        return None, "retrospective_adjustment_statement_ambiguous"
    actions = set(next(iter(distinct)))
    if len(actions) > 4:
        return None, "unsupported_corporate_actions"
    directions = {"reverse_split" if reverse else "split" for _, _, reverse in actions}
    direction = next(iter(directions)) if len(actions) == 1 else "multiple_actions"
    identities = tuple(sorted(f"{left}-for-{right}-{'reverse-' if reverse else ''}stock-split"
        for left, right, reverse in actions))
    return AnnualEpsComparabilityEvidence(accession=row.accession,
        adjustment_direction=direction, action_identities=identities,
        explicitly_retrospective_per_share=True, source_url=row.source_url), None


class EpsComparabilityEvidenceService:
    def __init__(self, retrieve_bound, *, max_requests=MAX_DOCUMENT_REQUESTS):
        if not 0 <= max_requests <= MAX_DOCUMENT_REQUESTS:
            raise ValueError("eps_document_request_budget_invalid")
        self.retrieve_bound, self.max_requests = retrieve_bound, max_requests

    def certify(self, snapshot):
        retained_years = {row.fiscal_year for row in snapshot.annual_eps_observations}
        originals = {}
        for row in snapshot.annual_eps_source_observations:
            if row.fiscal_year in retained_years and row.disclosure_type == "original_period":
                originals.setdefault(row.fiscal_year, set()).add(row.exact_eps)
        candidates = []
        for row in snapshot.annual_eps_source_observations:
            if (row.fiscal_year in retained_years and row.disclosure_type == "later_comparative" and
                    row.exact_eps not in originals.get(row.fiscal_year, set())):
                candidates.append(row)
        unique = {}
        for row in sorted(candidates, key=lambda item: (item.filing_date, item.accession), reverse=True):
            unique.setdefault((row.accession, row.source_url), row)
        rows = list(unique.values())
        if len(rows) > self.max_requests:
            return EpsComparabilityEvidenceResult(logical_documents=len(rows), failures=1,
                reasons=("request_budget_exhausted",))
        evidence, attempts, hits, failures, reasons = [], 0, 0, 0, []
        for row in rows:
            result = self.retrieve_bound(cik=row.cik, accession=row.accession,
                primary_document=_primary_document(row.source_url), source_url=row.source_url)
            attempts += result.http_attempts_charged
            hits += result.cache_state == "success_hit"
            if result.state != "available":
                failures += 1; reasons.append(_safe_reason(result.reason)); continue
            certified, reason = _certify_document(row, result.body)
            if certified is None:
                failures += 1; reasons.append(_safe_reason(reason)); continue
            evidence.append(certified)
        return EpsComparabilityEvidenceResult(tuple(evidence), len(rows), attempts, hits,
            failures, tuple(sorted(set(reasons))))

"""Audit-only Phase 6A.3A live Outlook corpus runner; no production mutations."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from app.config import settings
from app.services.outlook import analyze_outlook
from app.services.outlook_ai import (OpenAIOutlookIntelligenceProvider, build_context_packet,
    PROMPT_VERSION, SCHEMA_VERSION, clear_intelligence_cache, generate_intelligence)

TICKERS = ("AAPL", "NVDA", "MSFT", "GOOGL", "JPM", "XOM", "LLY", "BA",
           "WMT", "TSLA", "PLTR", "AMD", "META", "KO", "CAT", "ABTC")
OUTPUT = Path(__file__).resolve().parents[3] / "docs" / "outlook-phase6a3a-live-audit.json"


def _counts(packet):
    facts = Counter(f.category for f in packet.facts)
    directional = Counter(f.category for f in packet.facts if f.directionality in {"positive", "negative", "mixed"})
    informational = Counter(f.category for f in packet.facts if f.directionality == "informational")
    return {key: {"total": facts[key], "directional": directional[key], "informational": informational[key]}
            for key in ("company", "earnings", "industry", "economic", "market", "geopolitical")}


def _industry(outlook):
    rows = outlook.categories["industry"].evidence
    details = {}
    for row in rows:
        if row.raw_provider == "industry":
            details.update({key: value for key, value in row.source_details.items()
                            if value is not None})
    keys = ("raw_sector", "raw_industry", "normalized_industry", "classification_quality",
            "taxonomy_version", "benchmark_symbol", "benchmark_type", "relative_return_21",
            "relative_return_63", "breadth_state", "valid_peer_count", "fallback_reason",
            "industry_health_state", "relative_performance_state")
    return {key: details.get(key) for key in keys}


def _earnings(outlook, packet):
    evidence = outlook.categories["earnings"].evidence
    facts = [f for f in packet.facts if f.category == "earnings"]
    return {
        "released_evidence": any(not f.upcoming for f in facts),
        "upcoming_event": any(f.upcoming for f in facts),
        "expectation_available": any(f.values.get("expectation_status") == "available" for f in facts),
        "expectation_origins": sorted({str(f.values.get("expectation_origin")) for f in facts
                                       if f.values.get("expectation_origin")}),
        "actual_vs_expectation": any(f.values.get("surprise_status") not in {None, "unavailable"} for f in facts),
        "directionality": sorted({f.directionality for f in facts}),
        "evidence_types": sorted({row.event_type.value for row in evidence}),
    }


def _company(outlook, packet):
    evidence = outlook.categories["company"].evidence
    facts = [f for f in packet.facts if f.category == "company"]
    return {"supported_events": [row.event_type.value for row in evidence if row.scoring_eligible],
            "directional": sum(f.directionality in {"positive", "negative"} for f in facts),
            "informational": sum(f.directionality == "informational" for f in facts),
            "excluded_context_count": packet.diagnostics.omitted_reasons.get("sec_metadata_only", 0)}


def _category_rows(outlook, packet, response):
    by_category = {key: [f for f in packet.facts if f.category == key]
                   for key, _ in response.categories.items()}
    result = {}
    for key, ai in response.categories.items():
        deterministic = outlook.categories[key]
        result[key] = {"deterministic_status": deterministic.status, "ai_rating": ai.rating.value,
            "summary": ai.summary, "supporting_fact_count": len(ai.supporting_fact_ids),
            "key_point_count": len(ai.key_points), "limitation_count": len(ai.limitations),
            "supporting_fact_ids": list(ai.supporting_fact_ids),
            "available_fact_ids": [f.fact_id for f in by_category[key]]}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--tickers", nargs="+", choices=TICKERS, default=list(TICKERS),
                        help="Explicit bounded subset; defaults to the Phase 6A.3A universe")
    args = parser.parse_args()
    if not settings.outlook_llm_enabled or settings.outlook_llm_provider != "openai":
        parser.error("Configured OpenAI Outlook generation is not enabled")
    key = settings.openai_api_key.get_secret_value()
    if not key:
        parser.error("OPENAI_API_KEY is not configured")
    provider = OpenAIOutlookIntelligenceProvider(api_key=key, model=settings.outlook_llm_model,
                                                  timeout=settings.outlook_llm_timeout)
    clear_intelligence_cache()
    artifact = {"audit": {"phase": "6A.3A", "started_at": datetime.now(timezone.utc).isoformat(),
        "tickers": list(args.tickers), "model": settings.outlook_llm_model,
        "prompt_version": PROMPT_VERSION, "schema_version": SCHEMA_VERSION,
        "cache_ttl_seconds": settings.outlook_llm_cache_ttl}, "results": []}
    for ticker in args.tickers:
        row = {"ticker": ticker, "attempts": 0, "retries": 0}
        try:
            outlook = analyze_outlook(ticker)
            packet = build_context_packet(outlook)
            errors = []
            generated = None
            for attempt in range(2):
                row["attempts"] += 1
                generated = generate_intelligence(packet, provider, diagnostic_error_sink=errors.append)
                if generated.status == "available":
                    break
                if attempt == 0:
                    row["retries"] += 1
            row.update({"provider_status": dict(outlook.metadata.provider_status),
                "context_fingerprint": generated.diagnostics.context_fingerprint,
                "context_fact_count": len(packet.facts), "fact_counts": _counts(packet),
                "upcoming_event_count": len(packet.upcoming_events),
                "upcoming_events": [event.model_dump(mode="json") for event in packet.upcoming_events],
                "industry": _industry(outlook), "earnings": _earnings(outlook, packet),
                "company": _company(outlook, packet),
                "economic_fact_types": [f.fact_type for f in packet.facts if f.category == "economic"],
                "geopolitical_facts": [{"fact_id": f.fact_id, "directionality": f.directionality,
                    "statement": f.statement} for f in packet.facts if f.category == "geopolitical"],
                "generation_status": generated.status, "diagnostics": generated.diagnostics.model_dump(mode="json"),
                "provider_errors": errors})
            if generated.response:
                response = generated.response
                events = {event.event_id: event for event in packet.upcoming_events}
                row.update({"overall": response.overall.model_dump(mode="json"),
                    "categories": _category_rows(outlook, packet, response),
                    "what_to_watch": [{**item.model_dump(mode="json"),
                        "resolved_title": events[item.event_id].title,
                        "resolved_date": events[item.event_id].date.isoformat() if events[item.event_id].date else None}
                        for item in response.what_to_watch], "grounding": "pass"})
            else:
                row["grounding"] = "unavailable"
            if ticker == "AAPL" and generated.status == "available":
                repeat = generate_intelligence(packet, provider)
                row["cache_repeat"] = repeat.diagnostics.model_dump(mode="json")
        except Exception as exc:
            row.update(generation_status="audit_error", grounding="unavailable",
                       audit_error={"type": type(exc).__name__, "message": str(exc)[:300]})
        artifact["results"].append(row)
        print(f"{ticker}: {row.get('generation_status')} attempts={row['attempts']}", flush=True)
    artifact["audit"]["completed_at"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Inspect the isolated Phase 6A grounded AI Outlook prototype."""
import argparse
import json

from app.config import settings
from app.services.outlook import analyze_outlook
from app.services.outlook_ai import (MockOutlookIntelligenceProvider,
    OpenAIOutlookIntelligenceProvider, build_context_packet, context_fingerprint,
    generate_intelligence)


def _pretty(result, packet, *, resolve_facts=False):
    response = result.response
    print(packet.ticker)
    facts = {fact.fact_id: fact for fact in packet.facts}
    upcoming = {event.event_id: event for event in packet.upcoming_events}
    print("Overall:", response.overall.rating.value.replace("_", " ").title())
    print(response.overall.summary)
    for name, category in response.categories.items():
        print(f"\n{name.upper()} — {category.rating.value.replace('_', ' ').title()}")
        print(category.summary)
        for point in category.key_points:
            print(f"- {point.text}")
        if category.supporting_fact_ids:
            print("Facts used:", ", ".join(category.supporting_fact_ids))
        if resolve_facts:
            selected = dict.fromkeys((*category.supporting_fact_ids,
                *(fact_id for point in category.key_points for fact_id in point.supporting_fact_ids)))
            for fact_id in selected:
                fact = facts.get(fact_id)
                if fact:
                    print(f"  {fact_id}: {fact.statement}")
                    print(f"   directionality: {fact.directionality} ({fact.directionality_reason})")
                    print(f"   materiality: {fact.materiality}")
                    if fact.values:
                        print("   values:", json.dumps(fact.values, sort_keys=True))
    if response.what_to_watch:
        print("\nWHAT TO WATCH")
        for index, item in enumerate(response.what_to_watch, 1):
            event = upcoming[item.event_id]
            print(f"{index}. {event.date or 'Date unavailable'} — {event.title}")
            print(f"   {item.reason}")
            print(f"   Event ID: {item.event_id}")
    print("\nDIAGNOSTICS")
    for key, value in result.diagnostics.model_dump(mode="json").items():
        print(f"{key}: {value}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--context-only", action="store_true", help="Print context without an LLM call (default)")
    mode.add_argument("--generate", action="store_true", help="Explicitly request configured provider generation")
    mode.add_argument("--mock", action="store_true", help="Generate deterministic no-cost pipeline output")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--resolve-facts", action="store_true",
        help="Resolve selected opaque fact IDs to sanitized context facts")
    args = parser.parse_args()
    packet = build_context_packet(analyze_outlook(args.ticker))
    if not args.generate and not args.mock:
        print(json.dumps({**packet.model_dump(mode="json"),
            "context_fingerprint": context_fingerprint(packet)}, indent=2))
        return 0
    if args.generate:
        if not settings.outlook_llm_enabled:
            parser.error("OUTLOOK_LLM_ENABLED is false")
        if settings.outlook_llm_provider != "openai":
            parser.error("Unsupported OUTLOOK_LLM_PROVIDER")
        key = settings.openai_api_key.get_secret_value()
        if not key:
            parser.error("OPENAI_API_KEY is not configured")
        provider = OpenAIOutlookIntelligenceProvider(api_key=key,
            model=settings.outlook_llm_model, timeout=settings.outlook_llm_timeout)
    else:
        provider = MockOutlookIntelligenceProvider()
    provider_errors = []
    result = generate_intelligence(packet, provider,
        diagnostic_error_sink=provider_errors.append if args.generate else None)
    if args.json:
        payload = result.model_dump(mode="json")
        if provider_errors:
            payload["provider_error"] = provider_errors[-1]
        print(json.dumps(payload, indent=2))
    elif result.response:
        _pretty(result, packet, resolve_facts=args.resolve_facts)
    else:
        print(result.model_dump_json(indent=2))
    if provider_errors and not args.json:
        print("\nSANITIZED PROVIDER ERROR (local CLI diagnostic)")
        print(json.dumps(provider_errors[-1], indent=2))
    return 0 if result.status == "available" else 2


if __name__ == "__main__":
    raise SystemExit(main())

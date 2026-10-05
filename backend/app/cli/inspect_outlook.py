"""Operator-only read-only inspection of configured Outlook providers."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json

from app.services.outlook import analyze_outlook
from app.services.outlook_diagnostics import inspect_snapshot, format_availability
from app.services.outlook_reporting import evidence_reporting_diagnostics, format_reporting


def sec_diagnostics(result):
    evidence = [item for category in result.categories.values() for item in category.evidence if item.raw_provider == "sec"]
    filings = {item.raw_provider_id: item.source_details.get("sec_diagnostics", {}) for item in evidence}
    outcomes = Counter(details.get("exhibit_status", "not_attempted") for details in filings.values())
    return {
        "filing_observations": len(filings), "selected_filings": sum(d.get("selected", False) for d in filings.values()),
        **{key: sum(d.get(key, 0) for d in filings.values()) for key in
           ("metadata_documents", "item_documents", "exhibit_documents", "interpreted_candidates")},
        "exhibits_attempted": sum(outcomes[key] for key in ("retrieved", "failed", "unsupported_content")),
        "exhibits_retrieved": outcomes["retrieved"] + outcomes["unsupported_content"],
        "exhibits_failed": outcomes["failed"], "exhibits_not_selected": outcomes["not_selected"],
        "supported_events": sum(result.categories[key].evidence_count or 0 for key in ("company", "earnings")),
        "provenance_only_evidence": sum(not item.scoring_eligible for item in evidence),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker")
    parser.add_argument("--json", action="store_true", help="Include normalized evidence/provenance")
    parser.add_argument("--offline-case", help="Inspect a frozen case without configured providers or network")
    parser.add_argument("--replay", help="Replay name for --offline-case; default is the last declared replay")
    args = parser.parse_args()
    industry_diagnostics = {}
    geopolitical_diagnostics = {}
    if args.offline_case:
        from app.cli.evaluate_outlook import DEFAULT_CORPUS
        from app.models.outlook_evaluation import EvaluationCorpus
        from app.services.outlook_evaluation import replay, replay_documents
        from app.services.outlook_reporting import reporting_diagnostics
        packages = [p for path in (DEFAULT_CORPUS, DEFAULT_CORPUS.with_name("reporting-v1.json"))
            for p in EvaluationCorpus.model_validate_json(path.read_text(encoding="utf-8")).packages
            if p.id == args.offline_case and p.context.ticker.upper() == args.ticker.upper()]
        if len(packages) != 1:
            parser.error("No unique offline case for that ticker")
        package = packages[0]
        points = [p for p in package.replays if p.name == args.replay] if args.replay else [package.replays[-1]]
        if not points:
            parser.error("Unknown replay name")
        assessed_at = points[0].assessment_at
        result = replay(package, assessed_at)[2]
        reporting = reporting_diagnostics(replay_documents(package, assessed_at)[0], now=assessed_at,
            relationships=package.relationships, gaps=package.reporting_gaps)
    else:
        if args.replay:
            parser.error("--replay requires --offline-case")
        result = analyze_outlook(args.ticker)
        from app.services.outlook_structured import configured_providers
        for provider in configured_providers():
            if provider.name == "industry":
                try:
                    industry_diagnostics = {key: value for key, value in provider.inspect(args.ticker).items()
                                            if key != "evidence"}
                except Exception:
                    industry_diagnostics = {"status": "temporarily_unavailable"}
            if provider.name == "geopolitical":
                try:
                    geopolitical_diagnostics = {key: value for key, value in provider.inspect(args.ticker).items()
                                                if key != "evidence"}
                except Exception:
                    geopolitical_diagnostics = {"status": "temporarily_unavailable"}
        assessed_at = datetime.now(timezone.utc)
        reporting = evidence_reporting_diagnostics(
            [e for category in result.categories.values() for e in category.evidence], now=assessed_at)
    result, diagnostics = inspect_snapshot(result, now=assessed_at)
    if args.json:
        print(json.dumps({**result.model_dump(mode="json"), "assessment_at": assessed_at.isoformat(),
                          "availability_diagnostics": diagnostics, "reporting_diagnostics": reporting,
                          "industry_diagnostics": industry_diagnostics,
                          "geopolitical_diagnostics": geopolitical_diagnostics}, indent=2))
    else:
        print(f"{result.ticker}: {result.label.value if result.label else result.status}")
        print(f"{result.available_categories} of 6 categories available")
        print(f"Assessed at {assessed_at.isoformat()}; raw support excludes decay; effective support includes decay")
        for provider, state in result.metadata.provider_status.items():
            print(f"Provider {provider}: {state}")
        sec_evidence = [item for category in result.categories.values() for item in category.evidence
                        if item.raw_provider == "sec"]
        stats = sec_diagnostics(result)
        print(f"SEC filing observations: {stats['filing_observations']}; selected for text: {stats['selected_filings']}")
        print(f"SEC SourceDocuments: metadata-only={stats['metadata_documents']}; filing items={stats['item_documents']}; earnings exhibits={stats['exhibit_documents']}")
        print(f"SEC exhibit outcomes (fetched or cached): attempted={stats['exhibits_attempted']}; retrieved={stats['exhibits_retrieved']}; failed={stats['exhibits_failed']}; not selected={stats['exhibits_not_selected']}")
        print(f"SEC interpreted candidates: {stats['interpreted_candidates']}; supported events: {stats['supported_events']}; provenance-only evidence: {stats['provenance_only_evidence']}")
        retrieval = {item.raw_provider_id: item.source_details.get("document_retrieval", "unknown") for item in sec_evidence}
        print("SEC document retrieval: " + ", ".join(f"{state}={count}" for state, count in sorted(Counter(retrieval.values()).items())))
        for item in sec_evidence:
            details = item.source_details
            selection = details.get("sec_diagnostics", {})
            print("SEC candidate: " + json.dumps({
                "accession": item.raw_provider_id, "form": details.get("form"),
                "items": details.get("items", []), "retrieval": details.get("document_retrieval"),
                "selected": selection.get("selected"),
                "selection_reason": selection.get("selection_reason"),
                "company_candidate_families": selection.get("company_candidate_families", []),
                "company_interpretation": details.get("company_interpretation"),
                "interpretation_reason": details.get("interpretation_reason"),
                "normalized_event_type": item.event_type if item.scoring_eligible else None,
            }, sort_keys=True))
        print(format_reporting(reporting))
        if geopolitical_diagnostics:
            print("Geopolitical diagnostics: " + json.dumps(geopolitical_diagnostics))
        print(f"Geopolitical supported events: {result.categories['geopolitical'].evidence_count or 0}")
        for item in result.categories["geopolitical"].evidence:
            print(f"Geopolitical evidence: {item.summary}")
        industry = result.categories["industry"]
        if industry_diagnostics:
            print("Industry diagnostics: " + json.dumps(industry_diagnostics))
        print(f"Industry supported events: {industry.evidence_count or 0}")
        for item in industry.evidence:
            details = item.source_details
            print(f"Industry classification: {details.get('raw_sector')} / {details.get('raw_industry')} -> "
                  f"{details.get('normalized_industry') or 'unmapped'} ({details.get('classification_quality')}; "
                  f"taxonomy {details.get('taxonomy_version')})")
            print(f"Industry benchmark: {details.get('benchmark_symbol')} ({details.get('benchmark_type')}); "
                  f"fallback={details.get('fallback_reason') or 'none'}")
            if "relative_performance_state" in details:
                print("Industry relative performance: " + json.dumps({key: details.get(key) for key in (
                    "company_return_21", "company_return_63", "benchmark_return_21", "benchmark_return_63",
                    "relative_return_21", "relative_return_63", "relative_performance_state")}))
            if "peer_sample" in details:
                print(f"Industry peer coverage: {details.get('valid_peer_count')}/{details.get('configured_peer_count')}; "
                      f"breadth={details.get('breadth_state')}; sample: {', '.join(details['peer_sample'])}")
            print(f"Industry evidence: {item.summary}")
        for name, category in result.categories.items():
            label = category.label.value if category.label else category.status
            print(f"{name} label: {label}")
            print(format_availability(name, diagnostics[name]))
            intelligence = result.category_intelligence[name]
            selected = (*intelligence.positive_drivers, *intelligence.negative_drivers,
                        *intelligence.neutral_mixed_drivers)
            print("  Decision drivers: " + (", ".join(
                f"{row.direction}:{row.label}" for row in selected) or "none"))
            print(f"  Omitted lower-priority drivers: {intelligence.omitted_driver_count}")
            print("  Important metrics: " + (", ".join(
                f"{row.label}={row.actual or 'unavailable'}"
                + (f" expected={row.expected}" if row.expected else "")
                + (f" result={row.indicator} {row.result or ''}" if row.indicator else " comparison=unavailable")
                for row in intelligence.important_metrics) or "none"))
            print(f"  Latest material event: {intelligence.latest_material_event or 'none'}")
            print(f"  Next material event: {intelligence.next_material_event or 'none'}")
            print(f"  Evidence sufficiency: {intelligence.evidence_sufficiency}")
            print(f"  Sources retained: {len(intelligence.sources)}")
            if name == "earnings":
                print(f"  Beat probability: {intelligence.beat_probability if intelligence.beat_probability is not None else 'unavailable'}")
                print(f"  Implied move: {intelligence.implied_move if intelligence.implied_move is not None else 'unavailable'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

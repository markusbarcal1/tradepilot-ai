"""Operator-only read-only inspection of configured Outlook providers."""
import argparse
from collections import Counter

from app.services.outlook import analyze_outlook


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
    args = parser.parse_args()
    result = analyze_outlook(args.ticker)
    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(f"{result.ticker}: {result.label.value if result.label else result.status}")
        print(f"{result.available_categories} of 6 categories available")
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
        for name, category in result.categories.items():
            label = category.label.value if category.label else category.status
            print(f"{name}: {label}; {category.evidence_count or 0} supported events, {len(category.evidence)} source observations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

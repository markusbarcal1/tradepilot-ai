"""Read-only Event Intelligence diagnostics; shares official event data across tickers."""
import argparse
import json

from app.services.outlook_structured import configured_providers
from app.services.outlook_events import merge_intelligence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tickers", nargs="+")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    providers = [p for p in configured_providers() if getattr(p, "event_intelligence_provider", False)]
    reports = []
    for ticker in args.tickers:
        snapshots = [(provider.name, provider.inspect(ticker)) for provider in providers]
        intelligence = merge_intelligence([s["intelligence"] for _, s in snapshots])
        reports.append({"ticker": ticker.upper(), **intelligence.model_dump(mode="json"),
            "diagnostics": {name: s["diagnostics"] for name, s in snapshots},
            "outlook_evidence": [e.model_dump(mode="json") for _, s in snapshots for e in s["evidence"]]})
    if args.json:
        print(json.dumps(reports, indent=2))
    else:
        for report in reports:
            print(f"{report['ticker']} Event Intelligence: {report['status']}")
            for section in ("upcoming", "recent"):
                for item in report[section]:
                    event = item["event"]
                    print(f"  {section}: {event['event_id']} / {event['status']}")
                    for field in ("scheduled_date", "scheduled_at", "announced_at", "effective_date", "effective_at",
                                  "reference_period", "release_type", "underlying_event_id", "measurements", "revisions",
                                  "previous_value", "expected_value", "actual_value", "change", "expectation_status", "surprise"):
                        print(f"    {field}: {event[field]}")
                    print(f"    exposure: {item['exposure']}")
                    print(f"    expectation: {event['expectation']}")
                    print(f"    directional evidence: {item['directional_evidence']}")
            print("  Diagnostics: " + json.dumps(report["diagnostics"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

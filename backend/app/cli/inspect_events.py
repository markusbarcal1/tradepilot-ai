"""Read-only Event Intelligence diagnostics; shares global FOMC data across tickers."""
import argparse
import json

from app.services.outlook_structured import configured_providers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tickers", nargs="+")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    provider = next(p for p in configured_providers() if p.name == "fomc")
    reports = []
    for ticker in args.tickers:
        snapshot = provider.inspect(ticker)
        reports.append({"ticker": ticker.upper(), **snapshot["intelligence"].model_dump(mode="json"),
            "diagnostics": snapshot["diagnostics"],
            "outlook_evidence": [e.model_dump(mode="json") for e in snapshot["evidence"]]})
    if args.json:
        print(json.dumps(reports, indent=2))
    else:
        for report in reports:
            print(f"{report['ticker']} Event Intelligence / FOMC: {report['status']}")
            for section in ("upcoming", "recent"):
                for item in report[section]:
                    event = item["event"]
                    print(f"  {section}: {event['event_id']} / {event['status']}")
                    for field in ("scheduled_date", "scheduled_at", "announced_at", "effective_date", "effective_at",
                                  "previous_value", "expected_value", "actual_value", "change", "expectation_status", "surprise"):
                        print(f"    {field}: {event[field]}")
                    print(f"    exposure: {item['exposure']}")
                    print(f"    expectation: {event['expectation']}")
                    print(f"    directional evidence: {item['directional_evidence']}")
            print("  Diagnostics: " + json.dumps(report["diagnostics"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

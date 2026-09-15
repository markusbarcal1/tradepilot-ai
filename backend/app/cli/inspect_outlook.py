"""Operator-only read-only inspection of configured Outlook providers."""
import argparse

from app.services.outlook import analyze_outlook


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
        for name, category in result.categories.items():
            label = category.label.value if category.label else category.status
            print(f"{name}: {label}; {category.evidence_count or 0} supported events, {len(category.evidence)} source observations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

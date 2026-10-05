"""Run the versioned Outlook corpus offline; failed expectations exit nonzero."""
import argparse
from collections import Counter
import json
from pathlib import Path

from app.models.outlook_evaluation import EvaluationCorpus
from app.services.outlook_evaluation import evaluate_package
from app.services.outlook_diagnostics import format_availability
from app.services.outlook_reporting import format_reporting

DEFAULT_CORPUS = Path(__file__).resolve().parents[1] / "evaluation" / "outlook" / "v1.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, help="One corpus file; default runs original and reporting-identity corpora")
    parser.add_argument("--case", help="Evaluate one package ID")
    parser.add_argument("--json", action="store_true", help="Full structured report to stdout")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    paths = [args.corpus] if args.corpus else [DEFAULT_CORPUS, DEFAULT_CORPUS.with_name("reporting-v1.json")]
    corpora = [EvaluationCorpus.model_validate_json(path.read_text(encoding="utf-8")) for path in paths]
    packages = [p for corpus in corpora for p in corpus.packages if args.case is None or p.id == args.case]
    if not packages:
        parser.error("No matching cases")
    results = [evaluate_package(p) for p in packages]
    checks = [c for p in results for r in p["replays"] for c in r["checks"]]
    failures = Counter(c["kind"] for c in checks if not c["passed"])
    identified = [p for p in results if any(r["reporting_diagnostics"]["distinct_periods"] for r in p["replays"])]
    report = {"schema_version": "1.0", "corpus_version": ", ".join(c.corpus_version for c in corpora),
              "reporting_identity_packages": len(identified),
              "primary_source_reporting_packages": sum("primary_source_facts" in p["tags"] for p in identified),
              "cases": len(results), "replays": sum(len(p["replays"]) for p in results),
              "passes": sum(c["passed"] for c in checks), "failures": sum(failures.values()),
              "pass_kinds": dict(Counter(c["kind"] for c in checks if c["passed"])),
              "failure_kinds": dict(failures), "results": results}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Corpus {report['corpus_version']}: {report['cases']} cases, {report['replays']} historical replays")
        print(f"Checks: {report['passes']} passed, {report['failures']} failed; mismatches: {dict(failures)}")
        print(f"Reliable reporting identity: {len(identified)} packages; {report['primary_source_reporting_packages']} primary-source reporting packages")
        for p in results:
            for r in p["replays"]:
                failed = [c["name"] for c in r["checks"] if not c["passed"]]
                if args.verbose or failed:
                    states = ', '.join(f"{k}={v['status']}/{v['events']}/{v['support']:.6f}" for k,v in r['categories'].items() if v['events'] or v['status']=='available')
                    print(f"{p['id']} / {r['name']}: {r['overall_status']} {r['overall_label']}; {states}; failures={failed}")
                    for key, row in r["availability_diagnostics"].items():
                        print(format_availability(key, row))
                    print(format_reporting(r["reporting_diagnostics"]))
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

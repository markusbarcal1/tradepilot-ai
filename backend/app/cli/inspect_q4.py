"""Offline-only diagnostic for direct Q4 source fixtures."""
import argparse
import json
from pathlib import Path

from app.models.outlook_q4 import DirectQ4Document
from app.services.outlook_structured.q4_direct import qualify_direct_q4


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inspect offline direct-Q4 documents")
    parser.add_argument("--fixture", required=True, type=Path,
        help="Local JSON containing selected document metadata and inline content")
    args = parser.parse_args(argv)
    payload = json.loads(args.fixture.read_text(encoding="utf-8"))
    result = qualify_direct_q4([DirectQ4Document.model_validate(row)
        for row in payload.get("documents", [])])
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

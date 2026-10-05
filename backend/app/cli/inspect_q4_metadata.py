"""Isolated metadata-only Q4 discovery diagnostic; offline unless explicitly gated."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from app.config import REPOSITORY_ROOT, settings
from app.services.outlook_structured.q4_certification import (
    FixtureTransport, METADATA_ACKNOWLEDGMENT, MetadataOnlyDiscoveryRunner,
    StrictSecTransport, validate_metadata_live_gate,
)


def _output_path(directory):
    root = (REPOSITORY_ROOT / "docs" / "diagnostics").resolve()
    target = directory.resolve()
    if target != root and root not in target.parents:
        raise ValueError("output_directory_must_be_within_docs_diagnostics")
    target.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = target / f"phase6b5c2a5h-metadata-discovery-v2-{stamp}.json"
    if path.exists():
        raise FileExistsError(path)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Two-request SEC Q4 metadata discovery diagnostic")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixture", type=Path, help="Offline submissions-response fixture")
    mode.add_argument("--live", action="store_true", help="Explicitly enable two bounded SEC requests")
    parser.add_argument("--acknowledge", default="")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    path = _output_path(args.output_dir)
    if args.fixture:
        payload = json.loads(args.fixture.read_text(encoding="utf-8"))
        transport = FixtureTransport(payload.get("responses", {}))
        user_agent = "TradePilot offline fixture test@example.invalid"
    else:
        validate_metadata_live_gate(live=args.live, acknowledgment=args.acknowledge,
            user_agent=settings.outlook_sec_user_agent)
        if settings.outlook_http_attempts != 1 or settings.outlook_http_timeout != 5 or settings.outlook_sec_request_interval < 1:
            raise ValueError("unsafe_sec_transport_configuration")
        transport = StrictSecTransport(settings.outlook_sec_request_interval)
        user_agent = settings.outlook_sec_user_agent
    result = MetadataOnlyDiscoveryRunner(transport, user_agent=user_agent,
        http_attempts=1, follow_redirects=False, timeout=5,
        max_bytes=settings.outlook_sec_q4_document_max_bytes).run()
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

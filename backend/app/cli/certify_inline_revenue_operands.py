"""Operator-only inline-revenue certification support commands."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from app.config import REPOSITORY_ROOT, settings
from app.services.outlook_structured.inline_revenue_manifest_metadata import (
    MetadataManifestCompletionRunner, validate_live_gate as validate_metadata_live_gate,
)
from app.services.outlook_structured.inline_revenue_document_certification import (
    EightDocumentCertificationRunner, EXPECTED_FINGERPRINT, load_reviewed_manifest,
    validate_live_gate as validate_document_live_gate,
)
from app.services.outlook_structured.q4_certification import FixtureTransport, StrictSecTransport


def _output_path(value):
    root = (REPOSITORY_ROOT / "docs" / "diagnostics").resolve()
    path = value.resolve()
    if path.parent != root:
        raise ValueError("output_must_be_within_docs_diagnostics")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inline-revenue certification support")
    commands = parser.add_subparsers(dest="command", required=True)
    metadata = commands.add_parser("metadata", help="Complete two pinned annual filing dates")
    mode = metadata.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixture", type=Path)
    mode.add_argument("--live", action="store_true")
    metadata.add_argument("--acknowledge", default="")
    metadata.add_argument("--ack-max-attempts", type=int, required=True)
    metadata.add_argument("--targets", required=True)
    metadata.add_argument("--output", required=True, type=Path)
    documents = commands.add_parser("documents", help="Certify eight reviewed primary documents")
    document_mode = documents.add_mutually_exclusive_group(required=True)
    document_mode.add_argument("--fixture", type=Path)
    document_mode.add_argument("--live", action="store_true")
    documents.add_argument("--manifest", required=True, type=Path)
    documents.add_argument("--expected-fingerprint", required=True)
    documents.add_argument("--acknowledge", default="")
    documents.add_argument("--ack-max-attempts", type=int, required=True)
    documents.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    output = _output_path(args.output)
    if args.command == "documents":
        if args.ack_max_attempts != 8 or args.expected_fingerprint != EXPECTED_FINGERPRINT:
            raise ValueError("manifest_fingerprint_mismatch")
        manifest_payload = json.loads(args.manifest.read_text(encoding="utf-8"))
        manifest = load_reviewed_manifest(manifest_payload,
            expected_fingerprint=args.expected_fingerprint)
        if args.fixture:
            payload = json.loads(args.fixture.read_text(encoding="utf-8"))
            transport = FixtureTransport(payload.get("responses", {}))
            user_agent = "TradePilot offline fixture operator@example.invalid"
        else:
            validate_document_live_gate(live=args.live, acknowledgment=args.acknowledge,
                user_agent=settings.outlook_sec_user_agent)
            if (settings.outlook_http_attempts != 1 or settings.outlook_http_timeout != 5
                    or settings.outlook_sec_request_interval < 1):
                raise ValueError("unsafe_sec_transport_configuration")
            transport = StrictSecTransport(settings.outlook_sec_request_interval)
            user_agent = settings.outlook_sec_user_agent
        result = EightDocumentCertificationRunner(transport, manifest,
            user_agent=user_agent, timeout=5, http_attempts=1,
            follow_redirects=False).run()
    else:
        if args.ack_max_attempts != 2 or args.targets != "AAPL-FY2025,NVDA-FY2026":
            raise ValueError("manifest_integrity_failure")
        if args.fixture:
            payload = json.loads(args.fixture.read_text(encoding="utf-8"))
            transport = FixtureTransport(payload.get("responses", {}))
            user_agent = "TradePilot offline fixture operator@example.invalid"
        else:
            validate_metadata_live_gate(live=args.live, acknowledgment=args.acknowledge,
                user_agent=settings.outlook_sec_user_agent)
            if (settings.outlook_http_attempts != 1 or settings.outlook_http_timeout != 5
                    or settings.outlook_sec_request_interval < 1):
                raise ValueError("unsafe_sec_transport_configuration")
            transport = StrictSecTransport(settings.outlook_sec_request_interval)
            user_agent = settings.outlook_sec_user_agent
        result = MetadataManifestCompletionRunner(transport, user_agent=user_agent,
            timeout=5, http_attempts=1, follow_redirects=False).run()
    result["artifact_created_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

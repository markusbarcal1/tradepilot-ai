"""Reporting identity invariants; source metadata never changes financial assessment."""
from datetime import datetime, timedelta, timezone
import socket

import pytest

from app.cli.evaluate_outlook import DEFAULT_CORPUS
from app.models.outlook_document import SourceDocument
from app.models.outlook_evaluation import EvaluationCorpus, Relationship, ReportingGap
from app.models.outlook_evidence import CompanyContext
from app.models.outlook_reporting import ReportingPeriodIdentity, ReportingRevision, consecutive
from app.services.outlook_evaluation import replay, replay_documents, financial_snapshot, same_snapshot, evaluate_package
from app.services.outlook_evidence import assess_evidence
from app.services.outlook_interpreter import DeterministicOutlookInterpreter
from app.services.outlook_reporting import (
    resolve_reporting_identity, inline_reporting_identity, reporting_diagnostics, format_reporting,
    evidence_reporting_diagnostics,
)

NOW = datetime(2025, 8, 1, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Reporting tests must remain offline")
    monkeypatch.setattr(socket.socket, "connect", forbidden)


def document(**changes):
    return SourceDocument.model_validate(dict(id="arbitrary", ticker="NVDA", title="Quarterly report",
        extracted_text="Issuer announced results for second quarter fiscal 2026.\nIssuer reported second quarter ended July 27, 2025.",
        source_name="Primary test source", source_type="company_release", source_url="https://example.com/result",
        provider="fixture", provider_document_id="document", source_quality="primary_authoritative",
        published_at=NOW, observed_at=NOW, metadata={"document_kind": "earnings_release"}) | changes)


def period(year=2026, quarter="Q2", **changes):
    return ReportingPeriodIdentity(ticker="NVDA", fiscal_year=year, fiscal_period=quarter, **changes)


def dei(year="2026", quarter="Q2", end="2025-07-27", context="c"):
    return "".join(f'<ix:nonNumeric name="dei:{name}" contextRef="{context}">{value}</ix:nonNumeric>'
        for name, value in (("DocumentFiscalYearFocus", year), ("DocumentFiscalPeriodFocus", quarter), ("DocumentPeriodEndDate", end)))


def test_explicit_noncalendar_fiscal_year_and_four_clocks():
    doc = document(metadata={"filing_date": "2025-08-02"}, observed_at=NOW+timedelta(days=110))
    identity = resolve_reporting_identity(doc)
    assert identity.periods == (period(period_end="2025-07-27"),)
    row = reporting_diagnostics([doc], now=doc.observed_at)["sources"][0]
    assert row["publication_lag_days"] == {"NVDA:FY2026:Q2": 5}
    assert row["filing_date"] == "2025-08-02"
    assert doc.published_at == NOW


@pytest.mark.parametrize("month", range(1, 13))
def test_no_period_from_month_calendar_ticker_or_ids(month):
    doc = document(id="NVDA:FY2027:Q3", provider_document_id="Q3", title="Quarterly financial results",
        extracted_text="Quarterly revenue increased.", published_at=NOW.replace(month=month),
        observed_at=NOW.replace(month=month), metadata={"reporting_period": "Q3 FY2027"})
    assert resolve_reporting_identity(doc).status == "unknown"


def test_source_and_evidence_ids_do_not_determine_period():
    left = document()
    right = left.model_copy(update={"id": "Q1-FY2000", "provider_document_id": "different"})
    assert resolve_reporting_identity(left).periods == resolve_reporting_identity(right).periods


@pytest.mark.parametrize("left,right,expected", [
    (period(2026,"Q1"),period(),True), (period(2026,"Q2"),period(2026,"Q3"),True),
    (period(2026,"Q3"),period(2026,"Q4"),True), (period(2026,"Q4"),period(2027,"Q1"),True),
    (period(2026,"Q1"),period(2026,"Q3"),False), (period(2026,"Q3"),period(2026,"FY"),None),
    (None,period(),None), (period(),period(),False),
])
def test_consecutive(left, right, expected):
    assert consecutive(left,right) is expected


def test_missing_period_explicit_and_causes_not_inferred():
    q1 = document(id="one", extracted_text="Issuer announced first quarter fiscal 2026 results.")
    q3 = document(id="three", extracted_text="Issuer announced third quarter fiscal 2026 results.")
    gap = ReportingGap(period="NVDA:FY2026:Q2", cause="retrieval_gap", known_at=NOW, basis="Synthetic source-fetch failure")
    result = reporting_diagnostics([q1,q3], now=NOW, gaps=(gap,))
    assert result["consecutive"] is False
    assert result["immediately_previous_quarter"] is None
    assert result["expected_previous_quarter"] == "NVDA:FY2026:Q2"
    assert result["missing_periods"] == [{"period":"NVDA:FY2026:Q2","cause":"undetermined_missing_report_or_retrieval_gap"}]
    assert result["declared_gaps"][0]["cause"] == "retrieval_gap"
    assert reporting_diagnostics([q1,q3], now=NOW-timedelta(seconds=1), gaps=(gap,))["declared_gaps"] == []


def test_same_period_documents_and_amendment_do_not_add_period():
    original = document()
    amended = document(id="amended", observed_at=NOW+timedelta(days=5), metadata={"form":"10-Q/A"})
    identity = inline_reporting_identity(amended, dei())
    amended = amended.model_copy(update={"reporting_identity": identity})
    relation = Relationship(original=original.id, subsequent=amended.id, kind="amendment",
        reporting_period="FY2026 Q2", note="Explicit synthetic amendment link")
    before = reporting_diagnostics([original,amended],now=NOW,relationships=(relation,))
    after = reporting_diagnostics([original,amended],now=NOW+timedelta(days=5),relationships=(relation,))
    assert before["relationships"] == []
    assert after["distinct_periods"] == 1
    assert len(after["sources"]) == 2
    assert after["relationships"][0]["kind"] == "amendment"
    assert identity.revision.original_accession is None


def test_structured_precedence_and_8k_event_date_not_period_end():
    doc = document(metadata={"form":"10-Q"}, extracted_text="Issuer announced first quarter fiscal 2020 results.")
    identity = inline_reporting_identity(doc, dei())
    assert resolve_reporting_identity(doc.model_copy(update={"reporting_identity":identity})).periods[0].fiscal_period == "Q2"
    assert inline_reporting_identity(document(metadata={"form":"8-K"}), dei()).status == "unknown"


@pytest.mark.parametrize("html", [dei()+dei(quarter="Q3"), dei()+dei(quarter="Q3",context="other")])
def test_structured_conflicts_fail_closed(html):
    assert inline_reporting_identity(document(metadata={"form":"10-Q"}),html).status == "conflict"


def test_structured_form_scope_mismatch_fails_closed():
    assert inline_reporting_identity(document(metadata={"form":"10-Q"}),dei(quarter="FY")).reason == "structured_period_form_conflict"
    assert inline_reporting_identity(document(metadata={"form":"10-K"}),dei()).reason == "structured_period_form_conflict"


def test_structured_cannot_join_different_contexts():
    html = dei().replace('contextRef="c">Q2', 'contextRef="other">Q2')
    assert inline_reporting_identity(document(metadata={"form":"10-Q"}),html).status == "unknown"


def test_missing_structured_context_and_invalid_year_fail_closed():
    assert inline_reporting_identity(document(metadata={"form":"10-Q"}),dei(context="")).status == "unknown"
    assert resolve_reporting_identity(document(extracted_text="Issuer announced first quarter fiscal 2500 results.")).status == "unknown"


def test_corrected_period_changes_inventory_only_when_observable():
    original=document(id="original",extracted_text="Issuer announced first quarter fiscal 2026 results.")
    correction=document(id="correction",observed_at=NOW+timedelta(days=1))
    relation=Relationship(original=original.id,subsequent=correction.id,kind="correction",reporting_period="FY2026 Q2",note="Explicit synthetic period correction")
    before=reporting_diagnostics([original,correction],now=NOW,relationships=(relation,))
    after=reporting_diagnostics([original,correction],now=correction.observed_at,relationships=(relation,))
    assert before["current_known_quarter"] == "NVDA:FY2026:Q1"
    assert after["current_known_quarter"] == "NVDA:FY2026:Q2"
    assert after["distinct_periods"] == 1
    assert len(after["sources"]) == 2


def test_explicit_source_revision_link_retained_without_external_relationship():
    original=document(id="original",metadata={"accession":"known-original"},extracted_text="Issuer announced first quarter fiscal 2026 results.")
    correction=document(id="correction")
    identity=resolve_reporting_identity(correction).model_copy(update={"revision":ReportingRevision(
        kind="correction",original_accession="known-original",basis="Synthetic explicit source correction link")})
    correction=correction.model_copy(update={"reporting_identity":identity})
    result=reporting_diagnostics([original,correction],now=NOW)
    assert result["distinct_periods"] == 1
    assert result["relationships"][0]["original"] == "original"


def test_future_period_end_and_secondary_source_fail_closed():
    assert inline_reporting_identity(document(metadata={"form":"10-Q"}),dei(end="2025-09-30")).status == "unknown"
    assert resolve_reporting_identity(document(source_quality="secondary_reporting")).status == "unknown"


def test_guidance_never_inherits_results_period():
    doc = document(extracted_text=document().extracted_text + "\nThe company raised its full-year revenue guidance.")
    records = DeterministicOutlookInterpreter().interpret("NVDA",[doc],CompanyContext(ticker="NVDA"))
    assert records and records[0].event_type == "guidance_raise"
    assert "reporting_identity" not in records[0].source_details
    forecast_only = document(title="Outlook",extracted_text="The company expects second quarter fiscal 2026 results to improve.")
    assert resolve_reporting_identity(forecast_only).status == "unknown"


def test_q4_and_annual_are_separate_and_fact_scope_fails_closed():
    doc = document(title="Issuer reports fourth quarter and fiscal year 2024 results", extracted_text="Revenue increased 10% year over year.")
    identity = resolve_reporting_identity(doc)
    assert {p.fiscal_period for p in identity.periods} == {"Q4","FY"}
    records = DeterministicOutlookInterpreter().interpret("NVDA",[doc],CompanyContext(ticker="NVDA"))
    assert records[0].source_details["reporting_identity"]["reason"] == "annual_and_quarterly_fact_scope_ambiguous"
    annual = document(metadata={"form":"10-K"})
    assert inline_reporting_identity(annual,dei(quarter="FY")).periods[0].fiscal_period == "FY"


def test_53_week_year_has_no_fixed_duration_assumption():
    # Apple FY2023 Q1 had 14 weeks; explicit dates need not be three calendar months.
    p = ReportingPeriodIdentity(ticker="AAPL",fiscal_year=2023,fiscal_period="Q1",
        period_start="2022-09-25",period_end="2022-12-31")
    assert (p.period_end-p.period_start).days+1 == 98
    assert consecutive(p,ReportingPeriodIdentity(ticker="AAPL",fiscal_year=2023,fiscal_period="Q2",period_end="2023-04-01"))


def test_late_observation_and_out_of_order_documents():
    late = document(observed_at=NOW+timedelta(days=110))
    assert reporting_diagnostics([late],now=NOW)["distinct_periods"] == 0
    assert reporting_diagnostics([late],now=late.observed_at)["current_known_quarter"] == "NVDA:FY2026:Q2"
    prior = document(id="late-prior",extracted_text="Issuer announced first quarter fiscal 2026 results.",
        published_at=NOW+timedelta(days=120),observed_at=NOW+timedelta(days=120))
    result=reporting_diagnostics([late,prior],now=prior.observed_at)
    assert result["current_known_quarter"] == "NVDA:FY2026:Q2"
    assert result == reporting_diagnostics([prior,late],now=prior.observed_at)


def test_conflicting_dates_not_silently_merged():
    first=document()
    second=document(id="two",extracted_text=document().extracted_text.replace("July 27","July 26"))
    result=reporting_diagnostics([first,second],now=NOW)
    assert result["conflicting_periods"] == ["NVDA:FY2026:Q2"]
    assert result["distinct_periods"] == 0


def test_reporting_metadata_leaves_entire_original_corpus_financially_unchanged():
    corpus=EvaluationCorpus.model_validate_json(DEFAULT_CORPUS.read_text(encoding="utf-8"))
    for package in corpus.packages:
        for point in package.replays:
            records, contributions, response, _=replay(package,point.assessment_at)
            stripped=[r.model_copy(update={"source_details":{k:v for k,v in r.source_details.items() if k != "reporting_identity"}}) for r in records]
            categories, stripped_contributions=assess_evidence(package.context.ticker,stripped,now=point.assessment_at)
            assert same_snapshot(financial_snapshot(response.categories,contributions),financial_snapshot(categories,stripped_contributions))


def test_real_source_reporting_corpus_and_future_visibility():
    path=DEFAULT_CORPUS.with_name("reporting-v1.json")
    corpus=EvaluationCorpus.model_validate_json(path.read_text(encoding="utf-8"))
    for package in corpus.packages:
        report=evaluate_package(package)
        assert all(c["passed"] for r in report["replays"] for c in r["checks"]), package.id
        earliest=min(d.document.observed_at for d in package.sources)
        assert replay_documents(package,earliest-timedelta(seconds=1))[0] == []
        assert replay(package,earliest-timedelta(seconds=1))[0] == []


def test_evidence_and_cli_diagnostics():
    doc=document(extracted_text=document().extracted_text+"\nRevenue increased 10% year over year.")
    records=DeterministicOutlookInterpreter().interpret("NVDA",[doc],CompanyContext(ticker="NVDA"))
    result=evidence_reporting_diagnostics(records,now=NOW)
    assert result["current_known_quarter"] == "NVDA:FY2026:Q2"
    assert "FY2026 Q2 end=2025-07-27" in format_reporting(result)
    assert "published=" in format_reporting(result) and "observed=" in format_reporting(result)


@pytest.mark.parametrize("ticker", ["AAPL", "NVDA"])
def test_inspection_offline_without_provider(ticker, monkeypatch, capsys):
    import json
    from app.cli.inspect_outlook import main
    monkeypatch.setattr("sys.argv", ["inspect_outlook", ticker, "--offline-case", ticker.lower()+"_primary_reporting_sequence", "--json"])
    monkeypatch.setattr("app.cli.inspect_outlook.analyze_outlook", lambda *_: pytest.fail("Offline inspection called provider"))
    assert main() == 0
    result=json.loads(capsys.readouterr().out)
    assert result["reporting_diagnostics"]["current_known_quarter"].startswith(ticker+":FY2025:")
    assert "availability_diagnostics" in result

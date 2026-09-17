"""Synthetic, sanitized structures modeled on the diagnosed SEC layouts. No network."""
from datetime import timedelta

import pytest

from app.models.outlook_document import SourceDocument
from app.models.outlook_evidence import CompanyContext
from app.services.outlook import assess_providers
from app.services.outlook_evidence import assess_evidence, cluster_evidence
from app.services.outlook_interpreter import DeterministicOutlookInterpreter
from app.services.outlook_structured.documents import parse_filing, earnings_exhibit_url
from app.services.outlook_structured.sec import SecEvidenceProvider
from app.cli.inspect_outlook import sec_diagnostics
from tests.test_outlook_intelligence import document, interpret, DocumentClient
from tests.test_outlook_structured import settings, NOW

BASE = "https://www.sec.gov/Archives/edgar/data/1/123/report.htm"


def exhibit_row(hrefs):
    return '<table><tr><td>99.1</td><td>' + ''.join(
        f'<a href="{href}">part {index}</a>' for index, href in enumerate(hrefs)) + '</td></tr></table>'


def summary_table(current="71.5", prior="68.0", identity="GAAP", prior_header="Q2 FY26"):
    return f'''<table><tr><td colspan="18">{identity}</td></tr>
    <tr><td colspan="3">($ in millions, except earnings per share)</td>
    <td colspan="3">Q2 FY27</td><td colspan="3">Q1 FY27</td><td colspan="3">{prior_header}</td>
    <td colspan="3">Q/Q</td><td colspan="3">Y/Y</td></tr>
    <tr><td colspan="3">Gross margin</td><td colspan="2">{current}</td><td>%</td>
    <td colspan="2">70.0</td><td>%</td><td colspan="2">{prior}</td><td>%</td>
    <td colspan="3">1.5 pts</td><td colspan="3">3.5 pts</td></tr></table>'''


def table_evidence(html, prose=""):
    parsed = parse_filing(html)
    doc = SourceDocument.model_validate({**document(prose).model_dump(), "tables": parsed.tables})
    return DeterministicOutlookInterpreter().interpret("TEST", [doc], CompanyContext(ticker="TEST"))


def test_exhibit_anchors_resolve_one_distinct_validated_destination():
    links = parse_filing(exhibit_row(["release.htm"]*8 + ["./release.htm", BASE.replace("report.htm", "release.htm")])).links
    assert earnings_exhibit_url(BASE, links) == BASE.replace("report.htm", "release.htm")


@pytest.mark.parametrize("hrefs", [
    ["release.htm", "different.htm"],
    ["../elsewhere.htm"]*8,
    ["https://other.example/release.htm"]*8,
    ["//other.example/release.htm"],
    ["release.htm?redirect=other"], ["release.htm#fragment"], ["%2e%2e/release.htm"],
])
def test_exhibit_rejects_unsafe_or_ambiguous_destinations(hrefs):
    assert earnings_exhibit_url(BASE, parse_filing(exhibit_row(hrefs)).links) is None


def test_invalid_href_does_not_become_destination_and_992_stays_excluded():
    links = parse_filing(exhibit_row(["https://other.example/a.htm", "release.htm"])).links
    assert earnings_exhibit_url(BASE, links).endswith("release.htm")
    assert earnings_exhibit_url(BASE, [("commentary.htm", "99.2")]) is None


@pytest.mark.parametrize("text,metric,change", [
    ("The Company posted quarterly revenue of $110.5 billion, up 15 percent year over year.", "revenue", 15),
    ("Company reported revenue of $80.5 million, down 12% year over year.", "revenue", -12),
    ("Revenue was $80.5 billion, up 105% from a year ago.", "revenue", 105),
    ("Consolidated revenue of $80.5 billion, down 8% from a year ago.", "revenue", -8),
    ("•Revenue of $80.5 billion, up 105% from a year ago", "revenue", 105),
    ("•Record revenue of $80.5 billion, up 85% from a year ago", "revenue", 85),
    ("Diluted earnings per share was $2.03, up 28 percent year over year.", "diluted_eps", 28),
    ("Diluted EPS was $1.03, down 18% from a year ago.", "diluted_eps", -18),
    ("The Company reported diluted EPS of $1.03, down 18% year over year.", "diluted_eps", -18),
])
def test_reporting_language(text, metric, change):
    rows = interpret(text)
    assert len(rows) == 1
    assert rows[0].source_details["numeric"]["metric"] == metric
    assert rows[0].source_details["numeric"]["change_percent"] == change
    assert rows[0].summary == text


def test_qualified_eps_keeps_exact_context():
    text = "Diluted earnings per share was $2.03, up 28 percent year over year, and included a favorable impact of $0.12 from tariff refunds."
    row = interpret(text)[0]
    assert row.summary == row.source_details["evidence_basis"] == text
    assert "$0.12 from tariff refunds" in row.source_details["numeric"]["qualifier"]


@pytest.mark.parametrize("text", [
    "Shares were up 20% year over year.", "Up 20% from a year ago.",
    "The company was up 20% year over year.", "Revenue was strong, up 20%.",
    "Segment revenue was $10 million, up 20% year over year.",
    "Data Center revenue of $10 million, up 20% from a year ago.",
    "Revenue was $10 million, up 20% excluding acquisitions.",
    "Revenue was $10 million, up 20% year over year if demand improves.",
    "Revenue was $10 million, down 120% year over year.",
    "Diluted EPS was $-1.00, up 20% year over year.",
    "Revenue was $10 million, up 1,00% year over year.",
    "Revenue was $10 million, up 20% year over year, but this was not achieved.",
    "Revenue is expected to be $10 billion, plus or minus 2%.",
    "The company expects full-year revenue of $10 billion.",
])
def test_reject_ambiguous_reporting_and_new_forecasts(text):
    assert interpret(text) == []


@pytest.mark.parametrize("text,event", [
    ("The company raises its full-year outlook.", "guidance_raise"),
    ("The company lowers previously issued guidance.", "guidance_cut"),
    ("The company withdraws its prior guidance.", "guidance_withdrawal"),
])
def test_guidance_changes_still_need_explicit_change(text, event):
    assert interpret(text)[0].event_type == event


@pytest.mark.parametrize("current,prior,change", [("71.5", "68.0", 3.5), ("68.0", "71.5", -3.5)])
def test_gaap_colspan_alignment_and_percentage_points(current, prior, change):
    rows = table_evidence(summary_table(current, prior))
    assert len(rows) == 1 and rows[0].event_type == "margin_change"
    numeric = rows[0].source_details["numeric"]
    assert numeric["basis"] == "GAAP" and numeric["percentage_points"] == change
    assert numeric["current_period"] == "Q2 FY27" and numeric["prior_period"] == "Q2 FY26"
    assert "percentage points" in rows[0].summary


def test_gaap_preferred_without_mixing_non_gaap():
    rows = table_evidence(summary_table() + summary_table("50", "80", "Non-GAAP"))
    assert len(rows) == 1 and rows[0].impact == 1


@pytest.mark.parametrize("html", [
    summary_table(identity="Non-GAAP"), summary_table(identity="GAAP / Non-GAAP"),
    summary_table(prior_header="Q1 FY26"), summary_table(prior_header="Q2 FY27"),
    summary_table(current="101"), summary_table(current="ambiguous"),
    summary_table().replace("<td>%</td>", "<td></td>"),
    summary_table().replace('<td colspan="2">71.5', '<td colspan="4">71.5'),
    summary_table().replace('<td colspan="2">71.5', '<td rowspan="2" colspan="2">71.5'),
    summary_table().replace("</table>", ""),
    '<table><tr><td>' + summary_table() + '</td></tr></table>',
])
def test_table_ambiguity_rejected(html):
    assert table_evidence(html) == []


def test_malformed_table_does_not_discard_release_prose():
    parsed = parse_filing('<p>Revenue was $10 billion, up 20% year over year.</p><table><tr><td colspan>bad</td></tr></table>')
    assert parsed.tables == ()
    assert len(interpret(parsed.text.splitlines()[0])) == 1


def test_one_release_multiple_metrics_remain_one_event():
    rows = table_evidence(summary_table(), "Revenue was $10 billion, up 20% year over year.\nDiluted EPS was $2.00, up 25% year over year.")
    assert len(rows) == 3
    assert len(cluster_evidence(rows)) == 1
    categories, _ = assess_evidence("TEST", rows, now=NOW)
    assert categories["earnings"].evidence_count == 1 and categories["earnings"].status == "insufficient_data"
    # Conflicting factors are retained but cannot manufacture a directional vote.
    mixed = table_evidence(summary_table("60", "70"), "Revenue was $10 billion, up 20% year over year.")
    assert assess_evidence("TEST", mixed, now=NOW)[0]["earnings"].evidence_count == 0


def test_existing_expiration_preserved():
    rows = interpret("Revenue was $10 billion, up 20% year over year.")
    assert assess_evidence("TEST", rows, now=NOW+timedelta(days=138))[0]["earnings"].evidence_count == 0


def test_provider_to_diagnostics_with_multianchor_release_and_cache():
    class Client(DocumentClient):
        def get_text(self, url, **kwargs):
            self.text_calls.append(url)
            if url.endswith("release.htm"):
                return '<h1>Synthetic financial results</h1><p>Revenue was $10 billion, up 20% year over year.</p>' + summary_table()
            return '<p>Item 2.02 Results</p><p>Attached.</p><p>Item 9.01 Exhibits</p>' + exhibit_row(["release.htm"]*8)
    client = Client()
    provider = SecEvidenceProvider(settings(), client, lambda: NOW)
    first = assess_providers("AAPL", [provider], now=NOW)
    assert assess_providers("AAPL", [provider], now=NOW) == first
    stats = sec_diagnostics(first)
    assert len(client.text_calls) == 4
    assert stats["metadata_documents"] == 5 and stats["item_documents"] == stats["exhibit_documents"] == 2
    assert stats["selected_filings"] == stats["exhibits_attempted"] == stats["exhibits_retrieved"] == 2
    assert stats["exhibits_failed"] == 0 and stats["interpreted_candidates"] == 4
    assert stats["provenance_only_evidence"] == 5


def test_diagnostics_distinguish_failed_exhibit_from_successful_item():
    class Client(DocumentClient):
        def get_text(self, url, **kwargs):
            if url.endswith("release.htm"):
                raise TimeoutError("synthetic-secret")
            return super().get_text(url, **kwargs)
    result = assess_providers("AAPL", [SecEvidenceProvider(settings(), Client(), lambda: NOW)], now=NOW)
    stats = sec_diagnostics(result)
    assert stats["item_documents"] == 2 and stats["exhibit_documents"] == 0
    assert stats["exhibits_attempted"] == stats["exhibits_failed"] == 2 and stats["exhibits_retrieved"] == 0

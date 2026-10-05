"""Frozen primary-source Company-event fixtures; no provider or model calls."""
from datetime import timedelta

import pytest

from app.models.outlook_document import SourceDocument
from app.models.outlook_evidence import CompanyContext
from app.services.outlook_ai import build_context_packet
from app.services.outlook_evidence import cluster_evidence
from app.services.outlook_interpreter import DeterministicOutlookInterpreter
from app.services.outlook import assess_providers
from app.services.outlook_structured.sec import SecEvidenceProvider, select_document_candidates
from tests.test_outlook_structured import NOW, SecClient, settings


def company_document(item, text, *, accession="0000000000-26-000001", suffix=""):
    return SourceDocument(id=f"sec:TEST:{accession}:item:{item}{suffix}", ticker="TEST",
        title=f"Synthetic Item {item}", extracted_text=text, published_at=NOW-timedelta(hours=1),
        observed_at=NOW, source_name="SEC EDGAR", source_type="regulatory_filing",
        source_url=f"https://www.sec.gov/Archives/{accession.replace('-', '')}/report.htm",
        provider="sec", provider_document_id="report.htm", source_quality="primary_authoritative",
        metadata={"form": "8-K", "items": [item], "accession": accession,
                  "document_kind": "listing_item" if item == "3.01" else "company_item"})


def interpreted(item, text, **kwargs):
    doc = company_document(item, text, **kwargs)
    return DeterministicOutlookInterpreter().interpret("TEST", [doc], CompanyContext(ticker="TEST"))


@pytest.mark.parametrize("item,text,event,impact,materiality", [
    ("3.01", "The company received a notice from Nasdaq regarding noncompliance with listing rules.", "listing_noncompliance", -1, .9),
    ("3.01", "The company regained compliance with Nasdaq listing rules.", "listing_compliance", 1, .8),
    ("2.01", "The company completed the acquisition of Synthetic Target.", "acquisition", 0, .9),
    ("2.01", "The company completed the disposition of Synthetic Business.", "divestiture", 0, .9),
    ("3.02", "The company issued 1,000 shares of common stock.", "capital_raise", 0, .8),
    ("2.05", "The company approved a restructuring and workforce reduction.", "restructuring", 0, .85),
    ("1.01", "The company entered into a material definitive agreement.", "material_agreement", 0, .8),
    ("1.02", "The company terminated a material definitive agreement.", "material_agreement_termination", 0, .85),
])
def test_company_event_detection_direction_materiality_and_provenance(item, text, event, impact, materiality):
    rows = interpreted(item, text)
    assert len(rows) == 1
    row = rows[0]
    assert row.category == "company" and row.event_type == event
    assert row.impact == impact and row.materiality == materiality
    assert row.source_details["accession"] == "0000000000-26-000001"
    assert row.source_details["corporate_event_key"].startswith("TEST:")
    assert row.source_details["structured"]


@pytest.mark.parametrize("text,event,ratio", [
    ("The company will effect a ten-for-one stock split.", "stock_split", "10:1"),
    ("The company effected a one-for-ten reverse stock split.", "reverse_stock_split", "1:10"),
])
def test_split_ratio_is_deterministic_and_informational(text, event, ratio):
    row = interpreted("8.01", text)[0]
    assert row.event_type == event and row.impact == 0
    assert row.source_details["structured"]["ratio"] == ratio


def test_generic_item_801_does_not_imply_a_stock_split():
    assert interpreted("8.01", "The company announced a routine corporate update.") == []


@pytest.mark.parametrize("text,role,action,interim", [
    ("The company appointed Jane Doe as chief executive officer.", "CEO", "appointment", False),
    ("The chief executive officer resigned from the company.", "CEO", "departure", False),
    ("The company named Jane Doe interim CFO.", "CFO", "appointment", True),
])
def test_executive_change_requires_named_principal_role(text, role, action, interim):
    row = interpreted("5.02", text)[0]
    assert row.impact == 0 and row.materiality == .9
    assert row.source_details["structured"] == {"role": role, "action": action, "interim": interim}
    assert interpreted("5.02", "A director resigned from the board.") == []


@pytest.mark.parametrize("item,text", [
    ("1.01", "The company may enter into a material definitive agreement."),
    ("2.01", "The company is considering an acquisition."),
    ("3.02", "The company may issue securities."),
    ("5.02", "A director resigned from the board."),
])
def test_ambiguous_or_routine_company_item_is_not_interpreted(item, text):
    assert interpreted(item, text) == []


def test_amendment_and_duplicate_representations_cluster_by_semantic_event():
    text = "The company will effect a ten-for-one stock split."
    original = interpreted("8.01", text)[0]
    amendment_doc = company_document("8.01", text,
        accession="0000000000-26-000002", suffix=":amendment")
    amendment_doc = amendment_doc.model_copy(update={"metadata": {
        **amendment_doc.metadata, "form": "8-K/A"}})
    amendment = DeterministicOutlookInterpreter().interpret(
        "TEST", [amendment_doc], CompanyContext(ticker="TEST"))[0]
    assert original.id != amendment.id
    assert len(cluster_evidence([original, amendment])) == 1


class CompanyClient(SecClient):
    def __init__(self):
        super().__init__(["5.02", "2.02", "", "", ""])
        self.text_calls = []

    def get_text(self, url, **kwargs):
        self.text_calls.append(url)
        return ("<p>Item 5.02 Departure of Directors or Certain Officers</p>"
                "<p>The company appointed Jane Doe as chief executive officer.</p>"
                "<p>Item 9.01 Exhibits</p>")


def test_sec_provider_fetches_company_items_but_ordinary_ten_q_stays_provenance_only():
    rows = SecEvidenceProvider(settings(), CompanyClient(), lambda: NOW).get_evidence("AAPL")
    assert any(row.category == "company" and row.event_type == "management_change" and row.scoring_eligible for row in rows)
    ten_q = [row for row in rows if row.source_details["form"] == "10-Q"]
    assert ten_q and all(not row.scoring_eligible for row in ten_q)


def test_company_fact_flows_to_context_with_structured_values_and_priority():
    provider = SecEvidenceProvider(settings(), CompanyClient(), lambda: NOW)
    outlook = assess_providers("AAPL", [provider], now=NOW)
    packet = build_context_packet(outlook, generated_at=NOW)
    facts = [fact for fact in packet.facts if fact.category == "company"]
    assert facts and facts[0].fact_type == "management_change"
    assert facts[0].directionality == "informational"
    assert facts[0].values["event_role"] == "CEO"


class CurxLikeClient:
    """Authoritative-shaped SEC fixtures; no network access is possible."""
    accessions = [
        "0001493152-26-041900", "0001493152-26-041546",
        "0001493152-26-038764", "0001493152-26-021658",
    ]

    def __init__(self):
        self.text_calls = []

    def get(self, url, **kwargs):
        if "company_tickers" in url:
            return {"0": {"ticker": "CURX", "cik_str": 2025942}}
        return {"name": "Synthetic CURX-shaped issuer", "filings": {"recent": {
            "form": ["8-K"] * 4,
            "items": ["8.01", "8.01", "3.03,5.03,9.01", "8.01"],
            "accessionNumber": self.accessions,
            "filingDate": ["2026-09-10", "2026-09-04", "2026-08-17", "2026-05-07"],
            "acceptanceDateTime": ["2026-09-10T20:00:00Z", "2026-09-04T20:15:30Z",
                                   "2026-08-17T20:45:24Z", "2026-05-07T15:45:16Z"],
            "reportDate": [""] * 4,
            "primaryDocument": ["form8-k.htm"] * 4,
        }}}

    def get_text(self, url, **kwargs):
        self.text_calls.append(url)
        if "000149315226038764" in url:
            return ("<p>Item 3.03 Material Modification to Rights of Security Holders</p>"
                    "<p>The company amended the rights of its common stock.</p>"
                    "<p>Item 5.03 Amendments to Articles of Incorporation or Bylaws</p>"
                    "<p>The company effected a 1-for-20 reverse stock split.</p>"
                    "<p>Item 9.01 Financial Statements and Exhibits</p>")
        return ("<p>Item 8.01 Other Events</p><p>The company announced a routine corporate update.</p>"
                "<p>Item 9.01 Financial Statements and Exhibits</p>")


def test_curx_like_capital_structure_filing_gets_bounded_interpretation_opportunity():
    client = CurxLikeClient()
    rows = SecEvidenceProvider(settings(), client, lambda: NOW).get_evidence("CURX")
    split = [row for row in rows if row.event_type == "reverse_stock_split"]
    assert len(client.text_calls) == 2
    assert len(split) == 1
    assert split[0].raw_provider_id == "0001493152-26-038764"
    assert split[0].impact == 0 and split[0].materiality == .85
    assert split[0].source_details["structured"]["ratio"] == "1:20"
    assert split[0].source_details["source_document_id"].endswith(":item:5.03")
    selected = {row.raw_provider_id: row.source_details["sec_diagnostics"] for row in rows}
    assert selected["0001493152-26-038764"]["selection_reason"] == "company_priority"
    assert selected["0001493152-26-041900"]["selection_reason"] == "company_family_diversity"
    assert selected["0001493152-26-041546"]["selection_reason"] == "budget_not_selected"


def test_company_earnings_fairness_survives_company_family_priority():
    observations = SecEvidenceProvider(
        settings(outlook_sec_documents_enabled=False),
        SecClient(["8.01", "2.02", "1.03", "3.01", ""]), lambda: NOW)._observations("AAPL")
    selected, reasons = select_document_candidates(observations, 2)
    assert {"1.03", "2.02"} == {item.source_details["items"][0] for item in selected}
    assert set(reasons.values()) == {"company_priority", "earnings_priority"}


def test_same_company_family_does_not_displace_distinct_family():
    observations = SecEvidenceProvider(
        settings(outlook_sec_documents_enabled=False),
        SecClient(["8.01", "8.01", "5.02", "", ""]), lambda: NOW)._observations("AAPL")
    selected, reasons = select_document_candidates(observations, 2)
    assert {item.source_details["items"][0] for item in selected} == {"5.02", "8.01"}
    assert "company_family_diversity" in reasons.values()

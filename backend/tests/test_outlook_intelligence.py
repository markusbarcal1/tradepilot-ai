"""Synthetic fixtures only: no production fixture provider, network or paid services."""
from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.models.outlook_document import SourceDocument
from app.models.outlook_evidence import CompanyContext, OutlookEvidence
from app.models.outlook_taxonomy import EvidenceImpact
from app.services.outlook import assess_providers
from app.services.outlook_evidence import assess_evidence, cluster_evidence, weigh_cluster
from app.services.outlook_interpreter import DeterministicOutlookInterpreter, sec_observation_document
from app.services.outlook_providers import NewsSourceProvider, OutlookInterpreter
from app.services.outlook_structured.documents import earnings_exhibit_url, item_text, parse_filing
from app.services.outlook_structured.sec import SecEvidenceProvider
from app.services.outlook_structured.transport import JsonClient, ProviderUnavailable
from tests.test_outlook_structured import NOW, SecClient, settings, providers


def document(text="", **updates):
    return SourceDocument.model_validate(dict(id="synthetic:release", ticker="TEST", title="Synthetic earnings release",
        extracted_text=text, published_at=NOW-timedelta(hours=1), observed_at=NOW,
        source_name="Synthetic issuer", source_type="company_release", source_url="https://example.com/release",
        provider="fixture", provider_document_id="synthetic-release",
        source_quality="primary_authoritative", metadata={"document_kind": "earnings_release"}, **updates))


def interpret(text):
    interpreter: OutlookInterpreter = DeterministicOutlookInterpreter()
    return interpreter.interpret("TEST", [document(text)], CompanyContext(ticker="TEST", company_name="Example Inc."))


@pytest.mark.parametrize("text,event,impact", [
    ("The company raises full-year revenue guidance.", "guidance_raise", 1),
    ("We lowered full-year outlook.", "guidance_cut", -1),
    ("The company withdraws previously issued guidance.", "guidance_withdrawal", -1),
    ("Revenue increased 24% year over year.", "earnings_result", 1),
    ("Revenue decreased 12.5% year-over-year.", "earnings_result", -1),
    ("Diluted EPS increased 8% year over year.", "earnings_result", 1),
    ("Gross margin expanded from 40% to 42.5% year over year.", "margin_change", 1),
    ("Operating margin decreased from 20% to 15% compared with the prior-year period.", "margin_change", -1),
])
def test_explicit_synthetic_earnings(text, event, impact):
    rows = interpret(text)
    assert len(rows) == 1
    row = rows[0]
    assert row.event_type == event and row.impact == impact and row.category == "earnings"
    assert row.summary == row.source_details["evidence_basis"] == text
    assert row.source_details["source_document_id"] == "synthetic:release"
    assert row.source_url == document().source_url
    assert 0 < row.confidence < 1 and 0 < row.materiality < 1


@pytest.mark.parametrize("text", [
    "Strong growth and weak decline.", "Shares soar as investors cheer.",
    "The company may raise full-year revenue guidance.",
    "The company did not raise full-year revenue guidance.",
    "The company raises full-year revenue guidance if demand improves.",
    "The company raises full-year revenue guidance from $10 to $5.",
    "The company raises capital.", "The company acquired a competitor.",
    "The chief executive departed.", "The company signed a material contract.",
    "The company terminated a material contract.", "Revenue growth was strong.",
    "Revenue increased 24%.", "Segment revenue increased 24% year over year.",
    "Revenue increased 24% year over year excluding acquisitions.",
    "Revenue decreased 120% year over year.", "Revenue increased -5% year over year.",
    "Revenue increased 1,00% year over year.", "Revenue increased 0% year over year.",
    "Revenue increased 1001% year over year.", "Revenue increased NaN% year over year.",
    "Gross margin increased from 50% to 40% year over year.",
    "Gross margin decreased from 40% to 50% year over year.",
    "Gross margin increased from 99% to 101% year over year.",
    "Gross margin increased from 40% to 45%.",
    "Last year the company raised full-year guidance.",
    "Analysts say the company raises full-year guidance.",
])
def test_ambiguity_rejected(text):
    assert interpret(text) == []


def test_numeric_extraction():
    assert interpret("Revenue increased 24.5% year over year.")[0].source_details["numeric"]["change_percent"] == 24.5
    assert interpret("Revenue decreased 12% year over year.")[0].source_details["numeric"]["change_percent"] == -12
    assert interpret("Gross margin expanded from 40% to 42.5% year over year.")[0].source_details["numeric"]["percentage_points"] == 2.5
    assert interpret("Revenue increased 1,000% year over year.")
    tiny = interpret("Revenue increased 0.01% year over year.")
    assert tiny[0].materiality < .1
    assert assess_evidence("TEST", tiny, now=NOW)[0]["earnings"].evidence_count == 0


@pytest.mark.parametrize("text,impact", [
    ("The company raises full-year revenue guidance from $10-$12 billion to $11-$13 billion.", 1),
    ("The company lowers full-year revenue guidance from $10-$12 billion to $8-$9 billion.", -1),
    ("Revenue increased from $5 million to $6 million year over year.", 1),
    ("Revenue decreased from $6 billion to $5 billion year over year.", -1),
])
def test_explicit_comparable_levels(text, impact):
    row = interpret(text)[0]
    assert row.impact == impact and row.source_details["numeric"]


@pytest.mark.parametrize("text", [
    "The company raises full-year revenue guidance from $10-$12 billion to $9-$11 billion.",
    "The company raises full-year revenue guidance from $10-$12 billion to $9-$13 billion.",
    "The company raises full-year revenue guidance from $10-$12 million to $11-$13 billion.",
    "Revenue increased from $5 million to $4 million year over year.",
    "Revenue increased from $0 million to $4 million year over year.",
    "Revenue increased from $5 million to $6 billion year over year.",
])
def test_incomparable_or_contradictory_levels(text):
    assert interpret(text) == []


@pytest.mark.parametrize("field,value", [("ticker", " "), ("source_url", "file:///tmp/x"),
    ("observed_at", NOW-timedelta(days=2)), ("published_at", NOW.replace(tzinfo=None)),
    ("extracted_text", "x"*60001), ("source_quality", "trusted")],
    ids=["blank-ticker", "unsafe-url", "time-order", "naive-time", "oversized-text", "invalid-quality"])
def test_source_document_validation(field, value):
    payload = document().model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        SourceDocument.model_validate(payload)


@pytest.mark.parametrize("field,value", [("impact", 3), ("confidence", 1.01), ("materiality", -1),
    ("event_type", "guidance_up"), ("category", "company")])
def test_evidence_validation(field, value):
    payload = interpret("The company raises full-year guidance.")[0].model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        OutlookEvidence.model_validate(payload)


@pytest.mark.parametrize("item,event,impact", [("1.05", "cybersecurity_event", -1),
    ("2.06", "material_impairment", -1), ("1.03", "restructuring", -2)])
def test_sec_item_direction_and_provenance(item, event, impact):
    provider = SecEvidenceProvider(settings(), SecClient([item]*5), lambda: NOW)
    rows = provider.get_evidence("AAPL")
    assert rows[0].event_type == event and rows[0].impact == impact
    assert rows[0].source_details["accession"] == "0000320193-26-000000"
    assert rows[0].source_quality == "primary_authoritative"
    assert rows[0].source_details["source_document_id"].startswith("sec:AAPL:")
    observation = provider._observations("AAPL")[0]
    doc = sec_observation_document(observation)
    assert doc.extracted_text == "" and doc.source_url == observation.source_url
    assert doc.provider_document_id == observation.raw_provider_id


@pytest.mark.parametrize("item", ["1.01", "1.02", "2.01", "2.02", "2.05", "3.01", "3.02", "5.02", "7.01", "8.01", ""])
def test_non_directional_metadata(item):
    rows = SecEvidenceProvider(settings(), SecClient([item]*5), lambda: NOW).get_evidence("AAPL")
    assert all(not row.scoring_eligible and row.impact == 0 for row in rows)


class DocumentClient(SecClient):
    """Official-shaped SEC responses with unmistakably synthetic prose."""
    def __init__(self, broken=False):
        super().__init__(["2.02", "2.02", "3.01", "", ""])
        self.text_calls, self.broken = [], broken

    def get_text(self, url, **kwargs):
        self.text_calls.append(url)
        if self.broken:
            raise TimeoutError("synthetic-secret")
        if url.endswith("release.htm"):
            return "<h1>Synthetic financial results</h1><p>The company raises full-year revenue guidance.</p><p>Revenue increased 24% year over year.</p>"
        return '<p>Item 2.02 Results of Operations</p><p>See earnings release.</p><p>Item 9.01 Exhibits</p><a href="release.htm">99.1</a>'


def test_sec_documents_earnings_activation_cache_and_budget():
    client = DocumentClient()
    provider = SecEvidenceProvider(settings(), client, lambda: NOW)
    first = provider.get_evidence("AAPL")
    assert provider.get_evidence("aapl") == first
    assert len(client.text_calls) == 4  # two filings, one primary + one exhibit each
    earnings = [row for row in first if row.category == "earnings"]
    assert len(earnings) == 4
    assert all(row.source_details["provider_document_id"] == "release.htm" for row in earnings)
    assert all(str(row.source_url).endswith("release.htm") for row in earnings)
    result = assess_providers("AAPL", [provider], now=NOW)
    assert result.categories["earnings"].status == "available"
    assert result.categories["earnings"].evidence_count == 2  # same-day repeated representations
    assert result.categories["industry"].status == result.categories["geopolitical"].status == "unavailable"


def test_document_failure_isolated_and_backed_off():
    client = DocumentClient(broken=True)
    provider = SecEvidenceProvider(settings(), client, lambda: NOW)
    active = providers()
    active[0] = provider
    for _ in range(2):
        result = assess_providers("AAPL", active, now=NOW)
        assert result.metadata.provider_status["sec"] == "available"
        assert result.categories["economic"].status == result.categories["market"].status == "available"
        assert result.categories["earnings"].evidence_count == 0
    assert len(client.text_calls) == 2


def test_documents_disabled_and_no_news_dependency():
    client = DocumentClient()
    result = SecEvidenceProvider(settings(outlook_sec_documents_enabled=False), client, lambda: NOW).get_evidence("AAPL")
    assert client.text_calls == [] and all(row.category == "company" for row in result)
    assert NewsSourceProvider.__dict__.get("get_ticker_news")


def test_per_document_interpreter_failure():
    class BrokenOne(DeterministicOutlookInterpreter):
        def _interpret_document(self, doc, context):
            if doc.id == "broken":
                raise RuntimeError("synthetic-secret")
            return super()._interpret_document(doc, context)
    good = document("The company raises full-year guidance.")
    assert len(BrokenOne().interpret("TEST", [good.model_copy(update={"id": "broken"}), good], CompanyContext(ticker="TEST"))) == 1
    class BrokenAll:
        def interpret(self, *args):
            raise RuntimeError("synthetic-secret")
    provider = SecEvidenceProvider(settings(), DocumentClient(), lambda: NOW, interpreter=BrokenAll())
    rows = provider.get_evidence("AAPL")
    assert len(rows) == 5 and all(not row.scoring_eligible for row in rows)


def test_ticker_source_and_context_isolation():
    doc = document("The company raises full-year guidance.")
    interpreter = DeterministicOutlookInterpreter()
    assert interpreter.interpret("OTHER", [doc], CompanyContext(ticker="OTHER")) == []
    assert interpreter.interpret("TEST", [doc], CompanyContext(ticker="OTHER")) == []
    assert interpreter.interpret("TEST", [doc.model_copy(update={"source_quality": "secondary_reporting"})], CompanyContext(ticker="TEST")) == []


def test_primary_wins_duplicate_secondary_conflict():
    primary = interpret("The company raises full-year guidance.")[0]
    secondary = primary.model_copy(update={"id": "news", "raw_provider": "news", "raw_provider_id": "news",
        "source_quality": "secondary_reporting", "confidence": 1, "impact": EvidenceImpact.NEGATIVE})
    clusters = cluster_evidence([primary, secondary])
    assert len(clusters) == 1
    weighted = weigh_cluster(clusters[0], NOW)
    assert weighted.representative == primary and weighted.contribution > 0
    conflicting_primary = secondary.model_copy(update={"source_quality": "primary_authoritative"})
    assert weigh_cluster((primary, conflicting_primary), NOW).exclusion == "conflicting_duplicate_interpretations"


def test_listing_notice_requires_explicit_adverse_text():
    doc = document().model_dump()
    doc.update(provider="sec", source_type="regulatory_filing", metadata={"form": "8-K", "items": ["3.01"], "document_kind": "listing_item"})
    interpreter = DeterministicOutlookInterpreter()
    for text, count in [("The company received a notice from Nasdaq regarding noncompliance with listing rules.", 1),
        ("The company transferred its listing to Nasdaq.", 0),
        ("The company may receive a notice from Nasdaq regarding noncompliance.", 0)]:
        rows = interpreter.interpret("TEST", [SourceDocument.model_validate({**doc, "extracted_text": text})], CompanyContext(ticker="TEST"))
        assert len(rows) == count


def test_filing_html_boundaries_and_safe_links():
    parsed = parse_filing('<script>Revenue increased 20% year over year.</script><p>Item 2.02 Results</p><p>Actual text.</p><p>Item 9.01 Other</p>')
    assert "Revenue" not in parsed.text
    assert "Actual text" in item_text(parsed.text, "2.02") and "Other" not in item_text(parsed.text, "2.02")
    assert item_text("Item 2.02 contents Item 2.02 real", "2.02") == ""
    base = "https://www.sec.gov/Archives/edgar/data/1/123/report.htm"
    for href in ("https://evil.example/x.htm", "../other.htm", "//evil.example/x.htm", "x.htm?secret=x", "%2e%2e/x.htm"):
        assert earnings_exhibit_url(base, [(href, "99.1")]) is None
    assert earnings_exhibit_url(base, [("release.htm", "99.1")]).endswith("/123/release.htm")
    assert earnings_exhibit_url(base, [("release.htm", "Press release")]) is None
    table = parse_filing('<table><tr><td>99.1</td><td><a href="release.htm">Press release issued by synthetic issuer</a></td></tr></table>')
    assert earnings_exhibit_url(base, table.links).endswith("/release.htm")


def test_text_transport_limit_and_identification(monkeypatch):
    from app.services.outlook_structured import transport
    calls = []
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, size):
            calls.append(size)
            return b"x" * size
    def open_response(request, timeout):
        assert request.headers["User-agent"] == "synthetic operator@example.com"
        assert timeout == 5
        return Response()
    monkeypatch.setattr(transport, "urlopen", open_response)
    monkeypatch.setattr(transport.SEC_GATE, "wait", lambda interval: None)
    with pytest.raises(ProviderUnavailable):
        JsonClient(settings()).get_text("https://www.sec.gov/test", provider="sec", user_agent="synthetic operator@example.com")
    assert calls == [1024*1024+1]


def test_exhibit_failure_preserves_inline_earnings_and_no_secrets(caplog):
    class Partial(DocumentClient):
        def get_text(self, url, **kwargs):
            if url.endswith("release.htm"):
                raise TimeoutError("synthetic-secret")
            return '<p>Item 2.02 Results</p><p>The company raises full-year guidance.</p><p>Item 9.01 Exhibits</p><a href="release.htm">99.1</a>'
    provider = SecEvidenceProvider(settings(), Partial(), lambda: NOW)
    assert any(row.category == "earnings" for row in provider.get_evidence("AAPL"))
    assert "synthetic-secret" not in caplog.text


def test_interpretations_cached_and_invalid_output_isolated():
    class Counting(DeterministicOutlookInterpreter):
        calls = 0
        def interpret(self, *args):
            self.calls += 1
            return super().interpret(*args)
    interpreter = Counting()
    provider = SecEvidenceProvider(settings(), DocumentClient(), lambda: NOW, interpreter=interpreter)
    first = provider.get_evidence("AAPL")
    count = interpreter.calls
    assert provider.get_evidence("AAPL") == first and interpreter.calls == count
    class WrongTicker:
        def interpret(self, *args):
            return interpret("The company raises full-year guidance.")
    rows = SecEvidenceProvider(settings(), DocumentClient(), lambda: NOW, interpreter=WrongTicker()).get_evidence("AAPL")
    assert all(row.ticker == "AAPL" and not row.scoring_eligible for row in rows)


def test_truncation_cannot_remove_qualifier():
    from app.services.outlook_structured.documents import bounded_text
    text = "Revenue increased 24% year over year excluding acquisitions."
    assert bounded_text(text, 38) == ""
    assert bounded_text("Heading\n" + text, 46) == "Heading"


def test_sec_multiple_adverse_items_are_independent():
    rows = SecEvidenceProvider(settings(), SecClient(["1.05,2.06"]*5), lambda: NOW).get_evidence("AAPL")
    categories, _ = assess_evidence("AAPL", rows, now=NOW)
    assert categories["company"].status == "available"
    assert {row.event_type.value for row in categories["company"].evidence if row.scoring_eligible} == {"cybersecurity_event", "material_impairment"}

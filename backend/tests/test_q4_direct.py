"""Offline direct Q4 source, qualification, reconciliation and retrieval tests."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
import json

import pytest

from app.config import Settings
from app.cli.inspect_q4 import main as inspect_q4_main
from app.models.outlook_q4 import DirectQ4Document
from app.services.outlook_structured.q4_direct import DirectQ4Provider, qualify_direct_q4
from app.services.outlook_structured.transport import ProviderUnavailable

NOW = datetime(2026, 2, 20, 20, tzinfo=timezone.utc)


def settings(**changes):
    return Settings(_env_file=None, environment="test", outlook_sec_q4_enabled=True,
        outlook_sec_user_agent="TradePilot test operator@example.com", **changes)


def xbrl(value="12500000", eps="1.25", *, start="2025-10-01", end="2025-12-31",
         dimensional=False, annual=False, explicit=True):
    start = "2025-01-01" if annual else start
    member = "<xbrldi:explicitMember>SegmentA</xbrldi:explicitMember>" if dimensional else ""
    heading = "Three Months Ended 2025-12-31" if explicit else "Results"
    return f'''<html><body>
      <dei:DocumentFiscalYearFocus>2025</dei:DocumentFiscalYearFocus>
      <dei:DocumentFiscalPeriodFocus>FY</dei:DocumentFiscalPeriodFocus>
      <dei:DocumentPeriodEndDate>2025-12-31</dei:DocumentPeriodEndDate>
      <dei:EntityRegistrantName>Synthetic Issuer</dei:EntityRegistrantName>
      <xbrli:context id="q4"><xbrli:entity><xbrli:identifier>1045810</xbrli:identifier>{member}</xbrli:entity>
        <xbrli:period><xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate></xbrli:period></xbrli:context>
      <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
      <xbrli:unit id="eps"><xbrli:measure>iso4217:USD/xbrli:shares</xbrli:measure></xbrli:unit>
      <table><tr><th>{heading}</th></tr>
      <tr><td>Revenue</td><td><ix:nonFraction name="us-gaap:Revenues" contextRef="q4" unitRef="usd" scale="0">{value}</ix:nonFraction></td></tr>
      <tr><td>Diluted EPS</td><td><ix:nonFraction name="us-gaap:EarningsPerShareDiluted" contextRef="q4" unitRef="eps" scale="0">{eps}</ix:nonFraction></td></tr></table>
    </body></html>'''


def release(revenue="12.5", eps="1.25", label="GAAP Diluted EPS", approximate=False):
    qualifier = "approximately " if approximate else ""
    return f'''<html><body><table>
      <tr><th>Fourth Quarter Ended 2025-10-01 to 2025-12-31</th></tr>
      <tr><td>Revenue (USD millions)</td><td>{qualifier}${revenue}</td></tr>
      <tr><td>{label} (USD/share)</td><td>${eps}</td></tr>
    </table></body></html>'''


def document(content, *, family="filing_xbrl", form=None, accession="0001045810-26-000010",
             document_id="annual.htm", filed=date(2026, 2, 20)):
    return DirectQ4Document(ticker="NVDA", issuer="Synthetic Issuer", cik="0001045810",
        fiscal_year=2025, accession=accession, form=form or ("10-K" if family == "filing_xbrl" else "8-K"),
        document_url=f"https://www.sec.gov/Archives/edgar/data/1045810/{accession.replace('-', '')}/{document_id}",
        document_id=document_id, filing_date=filed, publication_time=NOW,
        source_family=family, content=content)


def test_valid_xbrl_q4_revenue_and_diluted_eps_are_exact_and_provenanced():
    result = qualify_direct_q4([document(xbrl())])
    assert result.status == "available"
    assert {row.metric for row in result.observations} == {"revenue", "diluted_eps"}
    revenue = next(row for row in result.observations if row.metric == "revenue")
    assert revenue.normalized_value == 12_500_000 and revenue.period_start == date(2025, 10, 1)
    assert revenue.locator.startswith("xbrl-context:q4") and revenue.comparison_eligible


def test_plain_filing_xbrl_instance_fact_is_supported():
    instance = xbrl().replace(
        '<ix:nonFraction name="us-gaap:Revenues" contextRef="q4" unitRef="usd" scale="0">12500000</ix:nonFraction>',
        '<us-gaap:Revenues contextRef="q4" unitRef="usd" decimals="-3">12500000</us-gaap:Revenues>')
    result = qualify_direct_q4([document(instance)])
    revenue = next(row for row in result.observations if row.metric == "revenue")
    assert revenue.normalized_value == 12_500_000


@pytest.mark.parametrize("content,reason", [
    (xbrl(annual=True), "not_standalone_quarter"),
    (xbrl(explicit=False), "no_explicit_q4_table_identity"),
    (xbrl(dimensional=True), "dimensional_context"),
])
def test_xbrl_annual_missing_identity_and_dimensional_contexts_reject(content, reason):
    result = qualify_direct_q4([document(content)])
    assert result.observations == () and reason in result.rejection_reasons


def test_exact_release_table_accepts_gaap_values_and_rejects_adjusted_or_approximate():
    accepted = qualify_direct_q4([document(release(), family="earnings_release_table")])
    assert {row.metric for row in accepted.observations} == {"revenue", "diluted_eps"}
    rejected = qualify_direct_q4([document(release(label="Adjusted non-GAAP Diluted EPS", approximate=True),
        family="earnings_release_table")])
    assert "rounded_or_approximate_value" in rejected.rejection_reasons
    assert "non_gaap_or_adjusted_metric" in rejected.rejection_reasons


def test_matching_sources_corroborate_but_different_exact_values_conflict():
    filing = document(xbrl())
    matching = document(release(), family="earnings_release_table", accession="0001045810-26-000009", document_id="ex99.htm")
    result = qualify_direct_q4([filing, matching])
    assert {row.version_status for row in result.observations} == {"current", "corroborating"}
    conflicting = document(release(revenue="13.0"), family="earnings_release_table",
        accession="0001045810-26-000008", document_id="conflict.htm")
    result = qualify_direct_q4([filing, conflicting])
    revenue = [row for row in result.observations if row.metric == "revenue"]
    assert {row.version_status for row in revenue} == {"conflict"}
    assert not any(row.comparison_eligible for row in revenue)


def test_explicit_10k_amendment_supersedes_original_but_later_comparative_does_not():
    original = document(xbrl(), accession="0001045810-26-000010")
    amended = document(xbrl(value="12600000"), form="10-K/A", accession="0001045810-26-000011",
        filed=date(2026, 3, 1))
    result = qualify_direct_q4([original, amended])
    revenue = [row for row in result.observations if row.metric == "revenue"]
    assert {row.version_status for row in revenue} == {"current", "superseded"}
    later = document(xbrl(value="12700000"), accession="0001045810-27-000010",
        filed=date(2027, 2, 20))
    result = qualify_direct_q4([original, later])
    assert {row.version_status for row in result.observations if row.metric == "revenue"} == {"conflict"}


def test_53_week_quarter_and_incorrect_unit_or_concept_boundaries():
    result = qualify_direct_q4([document(xbrl(start="2025-09-25", end="2025-12-31"))])
    assert result.observations and result.observations[0].duration_days == 98
    unsupported = xbrl().replace("us-gaap:Revenues", "custom:Revenue")
    result = qualify_direct_q4([document(unsupported)])
    assert all(row.metric == "diluted_eps" for row in result.observations)


class TextClient:
    def __init__(self, text): self.text, self.calls = text, []
    def get_text(self, url, **kwargs): self.calls.append(url); return self.text


def test_retrieval_is_bounded_cached_disabled_by_default_and_unregistered():
    metadata = document("")
    disabled = DirectQ4Provider(Settings(_env_file=None, environment="test"), TextClient(xbrl()))
    with pytest.raises(ProviderUnavailable): disabled.retrieve_selected([metadata])
    client = TextClient(xbrl())
    provider = DirectQ4Provider(settings(outlook_sec_q4_request_budget=1), client)
    first = provider.retrieve_selected([metadata])
    second = provider.retrieve_selected([metadata])
    assert first.observations and second.observations and len(client.calls) == 1
    assert second.requests == 1 and second.cache_hits == 1
    from app.services.outlook import configured_providers
    assert all(item.name != "sec_direct_q4" for item in configured_providers())


def test_retrieval_budget_failure_preserves_an_already_accepted_document():
    first = document("")
    second = document("", accession="0001045810-26-000011", document_id="second.htm")
    client = TextClient(xbrl())
    provider = DirectQ4Provider(settings(outlook_sec_q4_request_budget=1), client)
    result = provider.retrieve_selected([first, second])
    assert result.observations and result.requests == 1 and len(client.calls) == 1


def test_document_cache_is_single_flight_for_concurrent_selected_retrieval():
    metadata = document("")
    client = TextClient(xbrl())
    provider = DirectQ4Provider(settings(), client)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: provider.retrieve_selected([metadata]), range(4)))
    assert all(result.observations for result in results)
    assert len(client.calls) == 1


def test_empty_or_wrong_unit_document_fails_closed():
    assert qualify_direct_q4([document("<html></html>")]).status == "unavailable"
    wrong = xbrl().replace("iso4217:USD</xbrli:measure>", "iso4217:EUR</xbrli:measure>", 1)
    result = qualify_direct_q4([document(wrong)])
    revenue = next(row for row in result.candidates if row.metric == "revenue")
    assert "incompatible_unit" in revenue.rejection_reasons


def test_offline_diagnostic_reports_source_locator_provenance_and_state(tmp_path, capsys):
    path = tmp_path / "q4.json"
    path.write_text(json.dumps({"documents": [document(xbrl()).model_dump(mode="json")] }), encoding="utf-8")
    assert inspect_q4_main(["--fixture", str(path)]) == 0
    output = capsys.readouterr().out
    assert '"source_family": "filing_xbrl"' in output
    assert '"locator": "xbrl-context:q4:fact:0"' in output
    assert '"comparison_eligible": true' in output

"""Offline differential audit of direct-q4-1 release-table layout assumptions.

These fixtures characterize current behavior. They are not issuer evidence and must
not be used to widen the parser's financial acceptance rules.
"""
from datetime import date, datetime, timezone

import pytest

from app.models.outlook_q4 import DirectQ4Document
from app.services.outlook_structured.q4_direct import qualify_direct_q4


NOW = datetime(2026, 2, 20, 20, tzinfo=timezone.utc)
PERIOD = "Fourth Quarter Ended 2025-10-01 to 2025-12-31"


def document(content: str, *, family: str = "earnings_release_table") -> DirectQ4Document:
    return DirectQ4Document(
        ticker="TEST",
        issuer="Synthetic Issuer",
        cik="0000000001",
        fiscal_year=2025,
        accession="0000000001-26-000001",
        form="8-K",
        document_url="https://www.sec.gov/Archives/edgar/data/1/000000000126000001/ex99.htm",
        document_id="ex99.htm",
        filing_date=date(2026, 2, 20),
        publication_time=NOW,
        source_family=family,
        content=content,
    )


def table(rows: str, *, heading: str = PERIOD, heading_inside: bool = True) -> str:
    outside = f"<h2>{heading}</h2>" if not heading_inside else ""
    header = f"<tr><th>{heading}</th></tr>" if heading_inside else ""
    return f"<html><body>{outside}<table>{header}{rows}</table></body></html>"


ROWS = (
    '<tr><td>Revenue (USD millions)</td><td>$12.5</td></tr>'
    '<tr><td>GAAP Diluted EPS (USD/share)</td><td>$1.25</td></tr>'
)


CASES = [
    # name, HTML, candidates, accepted metrics, rejection reasons
    ("canonical", table(ROWS), 2, {"revenue", "diluted_eps"}, set()),
    ("nested-inline", table('<tr><td><strong>Revenue</strong> (USD millions)</td><td><span>$12.5</span></td></tr>'), 1, {"revenue"}, set()),
    ("whitespace-fragmentation", table('<tr><td>\n Revenue\t (USD millions) </td><td> $12.5 </td></tr>'), 1, {"revenue"}, set()),
    ("split-label-inline", table('<tr><td>GAAP <span>Diluted</span> EPS (USD/share)</td><td>$1.25</td></tr>'), 1, {"diluted_eps"}, set()),
    ("split-value-inline", table('<tr><td>Revenue (USD millions)</td><td>$12<strong>.5</strong></td></tr>'), 1, {"revenue"}, set()),
    ("th-cells", table('<tr><th>Revenue (USD millions)</th><th>$12.5</th></tr>'), 1, {"revenue"}, set()),
    ("colspan-ignored", table('<tr><td colspan="3">Revenue (USD millions)</td><td>$12.5</td></tr>'), 1, {"revenue"}, set()),
    ("rowspan-ignored", table('<tr><td rowspan="2">Revenue (USD millions)</td><td>$12.5</td></tr><tr><td>prior</td></tr>'), 1, {"revenue"}, set()),
    ("multirow-period-header", table('<tr><td>Revenue (USD millions)</td><td>$12.5</td></tr>', heading="", heading_inside=False).replace('<table>', '<table><tr><th>Fourth Quarter Ended</th></tr><tr><th>2025-10-01 to 2025-12-31</th></tr>'), 0, set(), set()),
    ("metric-not-first-cell", table('<tr><td>Note</td><td>Revenue (USD millions)</td><td>$12.5</td></tr>'), 0, set(), set()),
    ("leading-blank-cell", table('<tr><td></td><td>Revenue (USD millions)</td><td>$12.5</td></tr>'), 0, set(), set()),
    ("presentation-wrapper", f'<html><body><table><tr><td>{table(ROWS)}</td></tr></table></body></html>', 2, {"revenue", "diluted_eps"}, set()),
    ("multiple-tables", '<table><tr><td>presentation</td></tr></table>' + table(ROWS), 2, {"revenue", "diluted_eps"}, set()),
    ("nearby-heading-outside", table(ROWS, heading_inside=False), 0, set(), set()),
    ("annual-and-quarter-columns", table('<tr><td>Revenue (USD millions)</td><td>$12.5</td><td>$48.0 annual</td></tr>'), 1, {"revenue"}, set()),
    ("current-and-prior-columns", table('<tr><td>Revenue (USD millions)</td><td>$12.5 current</td><td>$10.0 prior</td></tr>'), 1, {"revenue"}, set()),
    ("total-revenue-wording", table('<tr><td>Total revenue (USD millions)</td><td>$12.5</td></tr>'), 0, set(), set()),
    ("diluted-earnings-per-share-wording", table('<tr><td>GAAP Diluted earnings per share (USD/share)</td><td>$1.25</td></tr>'), 0, set(), set()),
    ("gaap-and-nongaap", table('<tr><td>GAAP Diluted EPS (USD/share)</td><td>$1.25</td></tr><tr><td>Non-GAAP Diluted EPS (USD/share)</td><td>$1.40</td></tr>'), 2, {"diluted_eps"}, {"non_gaap_or_adjusted_metric"}),
    ("basic-and-diluted", table('<tr><td>GAAP Basic EPS (USD/share)</td><td>$1.30</td></tr><tr><td>GAAP Diluted EPS (USD/share)</td><td>$1.25</td></tr>'), 1, {"diluted_eps"}, set()),
    ("parenthetical-units-in-heading", table('<tr><td>Revenue</td><td>$12.5</td></tr>', heading=PERIOD + " (USD millions)"), 1, set(), {"missing_exact_value_or_scale"}),
    ("units-in-separate-row", table('<tr><td>(USD millions)</td></tr><tr><td>Revenue</td><td>$12.5</td></tr>'), 1, set(), {"missing_exact_value_or_scale"}),
    ("comma-value", table('<tr><td>Revenue (USD thousands)</td><td>$12,500</td></tr>'), 1, {"revenue"}, set()),
    ("parenthesized-negative", table('<tr><td>GAAP Diluted EPS (USD/share)</td><td>($1.25)</td></tr>'), 1, {"diluted_eps"}, set()),
    ("footnote-superscript", table('<tr><td>Revenue<sup>1</sup> (USD millions)</td><td>$12.5</td></tr>'), 0, set(), set()),
    ("repeated-metric-rows", table('<tr><td>Revenue (USD millions)</td><td>$12.5</td></tr>' * 2), 2, {"revenue"}, set()),
    ("duplicated-financial-tables", table('<tr><td>Revenue (USD millions)</td><td>$12.5</td></tr>') * 2, 2, {"revenue"}, set()),
    ("nested-table-content", table('<tr><td>Revenue (USD millions)</td><td><table><tr><td>$12.5</td></tr></table></td></tr>'), 0, set(), set()),
    ("entities-and-nbsp", table('<tr><td>Revenue&nbsp;(USD millions)</td><td>&#36;12.5</td></tr>'), 1, {"revenue"}, set()),
    ("malformed-browser-tolerated", table('<tr><td>Revenue (USD millions)<td>$12.5</td></tr>'), 0, set(), set()),
    ("no-literal-table", f'<h2>{PERIOD}</h2><div>Revenue (USD millions) $12.5</div>', 0, set(), set()),
    ("financial-table-after-eight", '<table><tr><td>layout</td></tr></table>' * 8 + table('<tr><td>Revenue (USD millions)</td><td>$12.5</td></tr>'), 0, set(), set()),
    ("approximate-recognized-rejected", table('<tr><td>Revenue (USD millions)</td><td>approximately $12.5</td></tr>'), 1, set(), {"rounded_or_approximate_value"}),
]


@pytest.mark.parametrize(
    "name,html,candidate_count,accepted_metrics,rejections",
    CASES,
    ids=[case[0] for case in CASES],
)
def test_release_table_layout_differential(
    name, html, candidate_count, accepted_metrics, rejections
):
    """Freeze observed stage outcomes without asserting that limitations are desirable."""
    result = qualify_direct_q4([document(html)])
    assert len(result.candidates) == candidate_count, name
    assert {row.metric for row in result.observations} == accepted_metrics, name
    assert set(result.rejection_reasons) == rejections, name


def test_bound_fiscal_year_is_not_compared_with_release_table_period_end():
    """Expose the current fiscal-identity gap without accepting or correcting it."""
    html = table('<tr><td>Revenue (USD millions)</td><td>$12.5</td></tr>')
    mismatched = document(html).model_copy(update={"fiscal_year": 2030})
    result = qualify_direct_q4([mismatched])
    assert len(result.observations) == 1
    assert result.observations[0].fiscal_year == 2030
    assert result.observations[0].period_end == date(2025, 12, 31)

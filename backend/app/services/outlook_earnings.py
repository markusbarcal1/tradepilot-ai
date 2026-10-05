"""Small reporting-prose and GAAP summary-table recognizers, never generic sentiment."""
import re
from decimal import Decimal

NUMBER = r"(?:0|[1-9]\d{0,2}(?:,\d{3})+|[1-9]\d*)(?:\.\d+)?"
YEAR_COMPARISON = r"(?:year[- ]over[- ]year|from a year ago|compared (?:with|to) (?:the )?(?:same|prior)[- ]year period)"


def reporting_comparison(sentence, company_name, ticker):
    """Whole issuer-level assertion; keep its original qualified basis at the caller."""
    subject = rf"(?:(?:the )?company|we|{re.escape(company_name or ticker)})"
    metric = r"(?P<metric>(?:(?:consolidated|quarterly|total) )?revenues?|diluted earnings per share|diluted EPS|earnings per share|EPS)"
    match = re.fullmatch(
        rf"(?:{subject} (?:posted|reported) )?(?:record )?{metric} (?:was|were|of) "
        rf"\$(?P<value>{NUMBER})(?: (?P<unit>million|billion))?, "
        rf"(?P<direction>up|down) (?P<change>{NUMBER})(?:%| percent) {YEAR_COMPARISON}"
        r"(?P<qualifier>, (?:and )?(?:including|included) .{1,240})?[.]?",
        sentence.lstrip("• "), re.I)
    if not match:
        return None
    value = Decimal(match["value"].replace(",", ""))
    change = Decimal(match["change"].replace(",", ""))
    revenue = "revenue" in match["metric"].lower()
    if (revenue and not match["unit"]) or (not revenue and match["unit"]):
        return None
    if not 0 < value <= Decimal("1e12") or not 0 < change <= 1000:
        return None
    direction = 1 if match["direction"].lower() == "up" else -1
    if direction < 0 and change >= 100:
        return None  # Positive current value cannot follow a 100% decline.
    return {"metric": "revenue" if revenue else "diluted_eps" if "diluted" in match["metric"].lower() else "eps",
            "current_value": float(value), "unit": "USD_" + match["unit"].lower() if revenue else "USD_per_share",
            "change_percent": float(change)*direction, "comparison": "year_over_year",
            "qualifier": (match["qualifier"] or "").lstrip(", ")}


def _spans(row):
    column = 0
    result = []
    for cell in row:
        result.append((column, column+cell.colspan, cell.text))
        column += cell.colspan
    return result


def _cell_text(spans, start, end):
    # No cell may straddle a header boundary.
    if any(left < end and right > start and (left < start or right > end) for left, right, _ in spans):
        return None
    return " ".join(text for left, right, text in spans if left >= start and right <= end).strip()


def gaap_margin_comparisons(tables):
    """Only explicit GAAP tables with quarter/FY headers and aligned percentage cells."""
    result = []
    for table_index, table in enumerate(tables):
        labels = [" ".join(cell.text for cell in row).strip().casefold() for row in table.rows]
        if labels.count("gaap") != 1 or any("non-gaap" in label or "non gaap" in label for label in labels):
            continue
        candidates = []
        for index, row in enumerate(table.rows):
            periods = []
            for left, right, text in _spans(row):
                match = re.fullmatch(r"Q([1-4])\s+FY(\d{4}|\d{2})", text, re.I)
                if match:
                    year = int(match[2]) + (2000 if len(match[2]) == 2 else 0)
                    periods.append((int(match[1]), year, left, right, text))
            if len(periods) >= 2:
                candidates.append((index, periods))
        if len(candidates) != 1:
            continue
        index, periods = candidates[0]
        if labels.index("gaap") >= index or len({(p[0], p[1]) for p in periods}) != len(periods):
            continue
        current = periods[0]
        prior = [p for p in periods if p[0] == current[0] and p[1] == current[1]-1]
        if len(prior) != 1 or any((p[1], p[0]) > (current[1], current[0]) for p in periods[1:]):
            continue
        prior = prior[0]
        header_width = sum(cell.colspan for cell in table.rows[index])
        found = []
        for row in table.rows[index+1:]:
            spans = _spans(row)
            if not spans or spans[-1][1] != header_width:
                continue
            metric = _cell_text(spans, 0, current[2])
            if metric is None or metric.lower() not in ("gross margin", "operating margin"):
                continue
            values = [_cell_text(spans, period[2], period[3]) for period in (current, prior)]
            matches = [re.fullmatch(r"(\d{1,3}(?:\.\d+)?)\s*%", value or "") for value in values]
            if not all(matches):
                continue
            after, before = [Decimal(match[1]) for match in matches]
            if not (0 <= after <= 100 and 0 <= before <= 100) or after == before:
                continue
            found.append({"metric": metric.lower().replace(" ", "_"), "basis": "GAAP",
                "current_period": current[4], "prior_period": prior[4], "current_percent": float(after),
                "prior_percent": float(before), "percentage_points": float(after-before),
                "comparison": "year_over_year", "table_index": table_index})
        # Duplicate metric rows are not unambiguous comparisons.
        for factor in found:
            if sum(other["metric"] == factor["metric"] for other in found) == 1:
                result.append(factor)
    return result

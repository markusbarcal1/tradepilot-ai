"""Pure, bounded structure-only diagnostics for direct-Q4 release HTML."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from html.parser import HTMLParser
import re

from app.models.outlook_q4 import DirectQ4Document

from .documents import parse_filing
from .q4_direct import SimpleTables


DIAGNOSTIC_VERSION = "direct-q4-release-structure-diagnostic-1"
SCHEMA_VERSION = "1"
COUNT_CAP = 255
DIRECT_TABLE_CAP = 8

PERIOD = re.compile(
    r"Fourth Quarter Ended\s+\d{4}-\d{2}-\d{2}\s+to\s+\d{4}-\d{2}-\d{2}", re.I)
DATE_RANGE = re.compile(r"\d{4}-\d{2}-\d{2}\s+to\s+\d{4}-\d{2}-\d{2}", re.I)
NUMERIC_SHAPE = re.compile(r"^\s*\$?\(?[0-9][0-9,]*(?:\.[0-9]+)?\)?(?:\s*[%x])?\s*$", re.I)
ROW_UNIT = re.compile(r"USD\s+(?:ones|thousands|millions|billions)|USD/share", re.I)


def _cap(value: int) -> int:
    return min(COUNT_CAP, value)


@dataclass(frozen=True)
class Cell:
    text: str
    tag: str
    colspan: int
    rowspan: int
    fragments: int


@dataclass(frozen=True)
class Table:
    rows: tuple[tuple[Cell, ...], ...]
    complete: bool
    nested: bool
    malformed: bool


class StructureObserver(HTMLParser):
    """Retains transient bounded structure; callers only receive sanitized counters."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[Table] = []
        self.depth = 0
        self.rows = []
        self.row = None
        self.cell = None
        self.cell_tag = None
        self.colspan = self.rowspan = 1
        self.fragments = 0
        self.nested = self.malformed = False
        self.table_starts = self.row_starts = self.cell_starts = 0
        self.completed_rows = self.completed_cells = 0
        self.th = self.td = self.colspans = self.rowspans = self.nonunit_rowspans = 0
        self.empty = self.nonempty = self.inline_fragments = 0
        self.outside_parts = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "table":
            self.table_starts += 1
            self.depth += 1
            if self.depth == 1:
                self.rows, self.row, self.cell = [], None, None
                self.nested = self.malformed = False
            else:
                self.nested = True
            return
        if self.depth == 0:
            return
        if self.depth != 1:
            return
        if tag == "tr":
            self.row_starts += 1
            if self.row is not None:
                self.malformed = True
            self.row = []
        elif tag in ("td", "th"):
            self.cell_starts += 1
            self.th += tag == "th"
            self.td += tag == "td"
            if self.row is None or self.cell is not None:
                self.malformed = True
            values = dict(attrs)
            try:
                self.colspan = int(values.get("colspan", "1"))
                self.rowspan = int(values.get("rowspan", "1"))
            except (TypeError, ValueError):
                self.colspan = self.rowspan = 0
                self.malformed = True
            self.colspans += self.colspan != 1
            self.rowspans += self.rowspan != 1
            self.nonunit_rowspans += self.rowspan not in (0, 1)
            self.cell, self.cell_tag, self.fragments = [], tag, 0
        elif self.cell is not None:
            self.fragments += 1

    def handle_data(self, data):
        if self.depth == 0:
            self.outside_parts.append(data)
        elif self.depth == 1 and self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.depth == 1 and tag in ("td", "th"):
            if self.cell is None or self.row is None:
                self.malformed = True
            else:
                text = " ".join("".join(self.cell).split())
                self.row.append(Cell(text, self.cell_tag, self.colspan, self.rowspan,
                    self.fragments))
                self.completed_cells += 1
                self.empty += not bool(text)
                self.nonempty += bool(text)
                self.inline_fragments += self.fragments > 0
                self.cell = self.cell_tag = None
        elif self.depth == 1 and tag == "tr":
            if self.row is None or self.cell is not None:
                self.malformed = True
            else:
                self.rows.append(tuple(self.row))
                self.completed_rows += 1
                self.row = None
        if tag == "table" and self.depth:
            if self.depth == 1:
                complete = self.row is None and self.cell is None and not self.malformed
                self.tables.append(Table(tuple(self.rows), complete, self.nested,
                    self.malformed))
            self.depth -= 1


def _metric_category(text: str, first_cell: str) -> tuple[str | None, bool]:
    adjusted = bool(re.search(r"adjusted|non[- ]GAAP", text, re.I))
    if re.search(r"GAAP\s+Diluted\s+EPS", text, re.I):
        return ("adjusted_non_gaap_diluted_eps" if adjusted else "exact_gaap_diluted_eps"), True
    if re.search(r"GAAP\s+Diluted\s+earnings\s+per\s+share", text, re.I):
        return "normalized_gaap_diluted_eps", False
    if re.search(r"Basic\s+(?:EPS|earnings\s+per\s+share)", text, re.I):
        return "basic_eps", False
    if re.search(r"Diluted\s+(?:EPS|earnings\s+per\s+share)", text, re.I):
        return "diluted_eps_without_gaap", False
    if re.search(r"^Revenue\b", text, re.I):
        return "exact_revenue", True
    if re.search(r"^Total\s+revenue\b", text, re.I):
        return "total_revenue", False
    if re.search(r"^Consolidated\s+revenue\b", text, re.I):
        return "consolidated_revenue", False
    if re.search(r"^Record\s+revenue\b", text, re.I):
        return "record_revenue", False
    if re.search(r"^Revenue\w+", first_cell, re.I):
        return "revenue_inline_boundary_disrupted", False
    if re.search(r"\brevenue\b", text, re.I):
        return ("revenue_with_leading_structure" if not re.search(r"^Revenue\b", text, re.I)
                else "normalized_revenue"), False
    if re.search(r"diluted", text, re.I) and re.search(r"(?:EPS|earnings per share)", text, re.I):
        return "other_diluted_eps", False
    return None, False


METRIC_KEYS = ("exact_revenue", "normalized_revenue", "total_revenue",
    "consolidated_revenue", "record_revenue", "revenue_with_leading_structure",
    "revenue_inline_boundary_disrupted", "other_revenue", "exact_gaap_diluted_eps",
    "normalized_gaap_diluted_eps", "diluted_eps_without_gaap", "basic_eps",
    "adjusted_non_gaap_diluted_eps", "other_diluted_eps")


def diagnose_release_structure(document: DirectQ4Document) -> dict:
    """Return schema-1 categorical/count metadata; never return source strings."""
    observer = StructureObserver()
    parser_completed = True
    parser_error = "none"
    try:
        observer.feed(document.content)
        observer.close()
    except Exception:
        parser_completed, parser_error = False, "html_parser_failure"

    direct = SimpleTables()
    try:
        direct.feed(document.content)
        direct.close()
    except Exception:
        parser_completed, parser_error = False, "direct_table_parser_failure"
    phase3b = parse_filing(document.content)

    metrics = {key: 0 for key in METRIC_KEYS}
    exact_period = quarter = fourth = annual = date_ranges = 0
    tables_with_period_metric = tables_passing = exact_revenue = exact_eps = 0
    later_numeric = row_unit = candidate_attempts = 0
    unit_metric = unit_elsewhere = unit_heading = no_unit = 0
    one_value = multi_value = quarter_headers = annual_headers = current_prior = 0
    multirow_headers = colspan_headers = rowspan_involvement = ambiguous_columns = 0
    financial_beyond = False
    any_metric_table = any_period_table = False

    for index, rows in enumerate(direct.tables):
        flat = " | ".join(" | ".join(row) for row in rows)
        has_period = bool(PERIOD.search(flat))
        exact_period += has_period
        any_period_table |= has_period
        quarter += bool(re.search(r"\b(?:Q[1-4]|quarter)\b", flat, re.I))
        fourth += bool(re.search(r"\bfourth\s+quarter\b", flat, re.I))
        annual += bool(re.search(r"\b(?:annual|fiscal\s+year|FY\s*\d{2,4})\b", flat, re.I))
        date_ranges += bool(DATE_RANGE.search(flat))
        table_metric = False
        header_rows = 0
        for row in rows:
            text = " | ".join(row)
            first = row[0] if row else ""
            category, exact = _metric_category(text, first)
            if category:
                metrics[category] += 1
                table_metric = True
                any_metric_table = True
            headerish = bool(re.search(r"\b(?:quarter|annual|fiscal|FY|current|prior)\b", text, re.I))
            header_rows += headerish
            quarter_headers += bool(re.search(r"\b(?:Q[1-4]|quarter)\b", text, re.I))
            annual_headers += bool(re.search(r"\b(?:annual|fiscal\s+year|FY\s*\d{2,4})\b", text, re.I))
            current_prior += bool(re.search(r"\bcurrent\b", text, re.I) and re.search(r"\bprior\b", text, re.I))
            if exact and has_period and index < DIRECT_TABLE_CAP:
                candidate_attempts += 1
                exact_revenue += category == "exact_revenue"
                exact_eps += category in ("exact_gaap_diluted_eps", "adjusted_non_gaap_diluted_eps")
                numeric_cells = sum(bool(NUMERIC_SHAPE.match(cell)) for cell in row[1:])
                later_numeric += numeric_cells > 0
                has_unit = bool(ROW_UNIT.search(text))
                row_unit += has_unit
                unit_metric += has_unit
                no_unit += not has_unit
                one_value += numeric_cells == 1
                multi_value += numeric_cells > 1
                ambiguous_columns += numeric_cells > 1
            elif category and ROW_UNIT.search(flat):
                unit_elsewhere += 1
        tables_with_period_metric += has_period and table_metric
        tables_passing += has_period and index < DIRECT_TABLE_CAP
        multirow_headers += header_rows > 1
        financial_beyond |= index >= DIRECT_TABLE_CAP and has_period and table_metric

    for table in observer.tables:
        if table.rows and any(cell.colspan != 1 for cell in table.rows[0]):
            colspan_headers += 1
        rowspan_involvement += any(cell.rowspan != 1 for row in table.rows for cell in row)
        for row in table.rows:
            row_text = " | ".join(cell.text for cell in row)
            if ROW_UNIT.search(row_text) and not any(_metric_category(row_text, row[0].text if row else "")[0] for _ in (0,)):
                unit_heading += 1

    outside = " ".join(observer.outside_parts)
    outside_period = bool(PERIOD.search(outside) or re.search(r"\bfourth\s+quarter\b", outside, re.I))
    reasons = []
    if observer.table_starts == 0: reasons.append("no_literal_table")
    if observer.table_starts and not direct.tables: reasons.append("no_complete_table")
    if financial_beyond: reasons.append("financial_table_beyond_current_cap")
    if not any_period_table: reasons.append("no_in_table_period_pattern")
    if outside_period and not any_period_table: reasons.append("period_only_outside_table")
    exact_metric_total = exact_revenue + exact_eps
    normalized_total = sum(metrics[key] for key in METRIC_KEYS if key not in (
        "exact_revenue", "exact_gaap_diluted_eps", "adjusted_non_gaap_diluted_eps"))
    if not exact_metric_total: reasons.append("no_exact_metric_label")
    if not exact_metric_total and normalized_total: reasons.append("normalized_metric_label_only")
    if any_metric_table and any_period_table and not tables_with_period_metric:
        reasons.append("metric_period_separated")
    if candidate_attempts and not later_numeric: reasons.append("metric_without_later_numeric_shape")
    if candidate_attempts and not row_unit: reasons.append("metric_without_row_level_unit")
    if any(table.nested or table.malformed for table in observer.tables):
        reasons.append("nested_or_malformed_structure")
    if candidate_attempts: reasons.append("current_parser_candidate_exists")
    if not reasons: reasons.append("unresolved_structure")

    counts = {
        "table_starts": observer.table_starts,
        "complete_observer_tables": sum(table.complete for table in observer.tables),
        "direct_retained_tables": len(direct.tables),
        "direct_examined_tables": min(DIRECT_TABLE_CAP, len(direct.tables)),
        "tables_beyond_direct_cap": max(0, len(direct.tables) - DIRECT_TABLE_CAP),
        "phase3b_retained_tables": len(phase3b.tables),
        "nested_table_encounters": sum(table.nested for table in observer.tables),
        "malformed_table_encounters": sum(table.malformed for table in observer.tables),
        "rows_encountered": observer.row_starts,
        "completed_rows": observer.completed_rows,
        "cells_encountered": observer.cell_starts,
        "completed_cells": observer.completed_cells,
        "th_cells": observer.th, "td_cells": observer.td,
        "colspan_cells": observer.colspans, "rowspan_cells": observer.rowspans,
        "nonunit_rowspan_cells": observer.nonunit_rowspans,
        "empty_cells": observer.empty, "nonempty_cells": observer.nonempty,
        "inline_fragmented_cells": observer.inline_fragments,
        "tables_with_zero_rows": sum(not table.rows for table in observer.tables),
        "rows_with_zero_cells": sum(not row for table in observer.tables for row in table.rows),
    }
    raw_counts = {**counts, **metrics}
    saturated = any(value > COUNT_CAP for value in raw_counts.values())
    counts = {key: _cap(value) for key, value in counts.items()}
    metrics = {key: _cap(value) for key, value in metrics.items()}

    result = {
        "schema_version": SCHEMA_VERSION,
        "diagnostic": DIAGNOSTIC_VERSION,
        "content_classification": ("empty" if not document.content.strip() else
            "html_like" if re.search(r"<(?:html|body|table|div|p|span|h[1-6])\b", document.content, re.I)
            else "text_like"),
        "parser_completed": parser_completed,
        "parser_error_category": parser_error,
        "counts": counts,
        "counts_saturated": saturated,
        "count_cap": COUNT_CAP,
        "period_categories": {
            "exact_period_pattern_hits": _cap(exact_period),
            "quarter_language_hits": _cap(quarter),
            "fourth_quarter_language_hits": _cap(fourth),
            "annual_fiscal_year_language_hits": _cap(annual),
            "date_range_pattern_hits": _cap(date_ranges),
            "period_like_outside_table": outside_period,
            "tables_with_period_and_metric": _cap(tables_with_period_metric),
        },
        "metric_categories": metrics,
        "unit_categories": {"supported_unit_in_metric_row": _cap(unit_metric),
            "supported_unit_elsewhere_in_table": _cap(unit_elsewhere),
            "unit_in_heading_like_row": _cap(unit_heading),
            "metric_rows_without_supported_unit": _cap(no_unit)},
        "column_categories": {"one_value_like_column": _cap(one_value),
            "multiple_value_like_columns": _cap(multi_value),
            "quarter_header_rows": _cap(quarter_headers),
            "annual_header_rows": _cap(annual_headers),
            "current_prior_header_rows": _cap(current_prior),
            "multirow_header_tables": _cap(multirow_headers),
            "colspan_header_tables": _cap(colspan_headers),
            "rowspan_involvement": _cap(rowspan_involvement),
            "ambiguous_column_associations": _cap(ambiguous_columns)},
        "candidate_stages": {"tables_structurally_retained": _cap(len(direct.tables)),
            "tables_passing_current_period_gate": _cap(tables_passing),
            "exact_revenue_label_hits": _cap(exact_revenue),
            "exact_diluted_eps_label_hits": _cap(exact_eps),
            "metric_rows_with_later_numeric_shape": _cap(later_numeric),
            "metric_rows_with_supported_row_unit": _cap(row_unit),
            "candidate_assembly_attempts": _cap(candidate_attempts),
            "predicted_direct_q4_candidates": _cap(candidate_attempts)},
        "phase3b_comparison": {"phase3b_preserves_more_tables": len(phase3b.tables) > len(direct.tables),
            "phase3b_colspan_visible": any(cell.colspan != 1 for table in phase3b.tables for row in table.rows for cell in row),
            "phase3b_rejects_structure_direct_retains": len(phase3b.tables) < len(direct.tables)},
        "zero_candidate_reasons": tuple(dict.fromkeys(reasons)),
        "fiscal_target_reconciliation_performed": False,
    }
    return result


def diagnostic_payload(document: DirectQ4Document) -> dict:
    """Alias emphasizing that the returned mapping is the complete safe payload."""
    return diagnose_release_structure(document)

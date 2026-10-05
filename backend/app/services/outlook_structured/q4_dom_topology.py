"""Pure bounded DOM-topology observations; never financial association or evidence."""
from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
import re

from app.models.outlook_q4 import DirectQ4Document

from .q4_release_structure import DATE_RANGE, PERIOD, _metric_category


DIAGNOSTIC_VERSION = "direct-q4-dom-topology-diagnostic-1"
SCHEMA_VERSION = "1"
NODE_CAP = 512
PERIOD_NODE_CAP = 16
TABLE_START_CAP = 32
ELIGIBLE_TABLE_CAP = 16
TABLES_PER_SECTION_CAP = 4
PAIR_CAP = 64
SIBLING_DISTANCE_CAP = 8
ANCESTOR_DEPTH_CAP = 4
SECTION_DESCENDANT_CAP = 64
COUNT_CAP = 255

NODE_TYPES = {"h1", "h2", "h3", "h4", "h5", "h6", "caption", "p", "div", "span",
    "th", "td", "section", "article", "table"}
BLOCK_TYPES = {"h1", "h2", "h3", "h4", "h5", "h6", "caption", "p", "div", "section",
    "article", "table", "th", "td"}
HIDDEN_TAGS = {"script", "style", "ix:header"}


def _type(tag):
    return tag if tag in NODE_TYPES else "other_allowed_element" if tag in {
        "html", "body", "main", "header", "footer", "aside", "nav", "figure", "figcaption",
        "tbody", "thead", "tfoot", "tr", "ul", "ol", "li", "br", "a", "strong", "em",
        "b", "i", "sup", "small"} else "other_or_unrepresentable"


def _cap(value): return min(COUNT_CAP, value)


@dataclass
class Node:
    ordinal: int
    tag: str
    parent: int | None
    sibling: int
    hidden: bool
    role_heading: bool = False
    role_level: int | None = None
    element_id: str | None = None
    labelledby: str | None = None
    attrs_present: frozenset = frozenset()
    colspan_present: bool = False
    nonunit_rowspan: bool = False
    text_parts: list[str] = field(default_factory=list)
    children: list[int] = field(default_factory=list)
    closed: bool = False
    malformed: bool = False


class TopologyParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nodes: list[Node] = []
        self.stack: list[int] = []
        self.capped = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if len(self.nodes) >= NODE_CAP:
            self.capped = True
            return
        values = dict(attrs)
        parent = self.stack[-1] if self.stack else None
        sibling = len(self.nodes[parent].children) if parent is not None else sum(
            node.parent is None for node in self.nodes)
        hidden = tag in HIDDEN_TAGS or values.get("hidden") is not None or (
            parent is not None and self.nodes[parent].hidden)
        role_heading = str(values.get("role", "")).lower() == "heading"
        try: level = int(values.get("aria-level")) if values.get("aria-level") else None
        except (TypeError, ValueError): level = None
        try: rowspan = int(values.get("rowspan", "1"))
        except (TypeError, ValueError): rowspan = 0
        node = Node(len(self.nodes), tag, parent, sibling, hidden, role_heading,
            level if level and 1 <= level <= 6 else None, values.get("id"),
            values.get("aria-labelledby"), frozenset(values), "colspan" in values,
            "rowspan" in values and rowspan != 1)
        self.nodes.append(node)
        if parent is not None: self.nodes[parent].children.append(node.ordinal)
        if tag in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
                "meta", "param", "source", "track", "wbr"}:
            node.closed = True
        else:
            self.stack.append(node.ordinal)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack: self.nodes[self.stack.pop()].closed = True

    def handle_data(self, data):
        if not self.stack or self.nodes[self.stack[-1]].hidden: return
        for ordinal in self.stack:
            self.nodes[ordinal].text_parts.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if not self.stack: return
        match = next((index for index in range(len(self.stack)-1, -1, -1)
            if self.nodes[self.stack[index]].tag == tag), None)
        if match is None: return
        if match != len(self.stack)-1:
            for ordinal in self.stack[match+1:]: self.nodes[ordinal].malformed = True
        ordinal = self.stack[match]
        self.nodes[ordinal].closed = True
        del self.stack[match:]

    def close(self):
        super().close()
        for ordinal in self.stack: self.nodes[ordinal].malformed = True


def _text(node): return " ".join("".join(node.text_parts).split())


def _period_bits(text):
    bits = 0
    bits |= bool(PERIOD.search(text)) * 1
    bits |= bool(re.search(r"\bfourth\s+quarter\b", text, re.I)) * 2
    bits |= bool(re.search(r"\b(?:Q[1-4]|quarter)\b", text, re.I)) * 4
    bits |= bool(re.search(r"\b(?:annual|fiscal\s+year|FY\s*\d{2,4})\b", text, re.I)) * 8
    bits |= bool(DATE_RANGE.search(text)) * 16
    return bits


def _depth(nodes, node):
    depth, current = 0, node
    while current.parent is not None:
        depth += 1; current = nodes[current.parent]
    return depth


def _ancestors(nodes, node):
    result, current = [], node
    while current.parent is not None and len(result) < ANCESTOR_DEPTH_CAP:
        current = nodes[current.parent]; result.append(_type(current.tag))
    return result


def _section(nodes, node):
    current = node
    while current.parent is not None:
        current = nodes[current.parent]
        if current.tag in ("section", "article"): return current
    return None


def _semantic(node):
    if node.hidden: return "hidden_or_excluded"
    if node.tag in {f"h{i}" for i in range(1, 7)}: return "native_heading"
    if node.role_heading: return "explicit_role_heading"
    if node.tag == "caption": return "caption"
    if node.tag in ("th", "td"): return "table_internal"
    if node.tag in ("p", "div", "span", "section", "article"): return "ordinary_block"
    return "other"


def _significant(node, period_bits=0):
    if node.hidden: return "hidden_excluded"
    if node.tag == "table": return "table"
    if node.tag in ("section", "article"): return "section_boundary"
    if period_bits and _semantic(node) in ("native_heading", "explicit_role_heading", "caption"):
        return "eligible_heading_candidate"
    if period_bits: return "other_period_like_node"
    if node.tag in BLOCK_TYPES: return "ordinary_block"
    if node.malformed: return "malformed_unrepresentable"
    return "ordinary_block"


def _descendants(nodes, root):
    result, pending = [], list(root.children)
    while pending and len(result) <= SECTION_DESCENDANT_CAP:
        ordinal = pending.pop(0); result.append(nodes[ordinal]); pending[0:0] = nodes[ordinal].children
    return result


def _node_record(nodes, node, bits, tables):
    section = _section(nodes, node)
    nearest = None
    for table in tables:
        distance = abs(table.ordinal-node.ordinal)
        if nearest is None or distance < nearest[1]: nearest = (table.ordinal, distance)
    return {"ordinal": node.ordinal, "parent_ordinal": node.parent,
        "ancestor_depth": min(_depth(nodes, node), ANCESTOR_DEPTH_CAP+1),
        "ancestor_depth_capped": _depth(nodes, node) > ANCESTOR_DEPTH_CAP,
        "ancestor_type_path": _ancestors(nodes, node), "sibling_ordinal": node.sibling,
        "section_ordinal": section.ordinal if section else None,
        "node_type": "semantic_heading_role" if node.role_heading else _type(node.tag),
        "semantic_category": _semantic(node),
        "role_heading_level_category": ("valid_bounded" if node.role_heading and node.role_level
            else "invalid_or_missing" if node.role_heading else "not_applicable"),
        "period_category_bits": bits,
        "nearest_table_ordinal": nearest[0] if nearest else None,
        "nearest_table_distance": min(nearest[1], COUNT_CAP) if nearest else None}


def diagnose_dom_topology(document: DirectQ4Document) -> dict:
    parser = TopologyParser(); parser.feed(document.content); parser.close()
    nodes = parser.nodes
    all_tables = [node for node in nodes if node.tag == "table"]
    top_tables = [node for node in all_tables if not any(ancestor.tag == "table"
        for ancestor in _ancestor_nodes(nodes, node))]
    table_starts_capped = len(all_tables) > TABLE_START_CAP
    observed_tables = top_tables[:ELIGIBLE_TABLE_CAP]

    raw_period = [(node, _period_bits(_text(node))) for node in nodes
        if node.tag in NODE_TYPES and node.tag != "table" and not node.hidden]
    raw_period = [(node, bits) for node, bits in raw_period if bits]
    # Prefer the structural heading/container over inline descendants carrying identical text.
    preferred = []
    for node, bits in raw_period:
        if _semantic(node) == "ordinary_block" and any(
                descendant.ordinal != node.ordinal
                and _semantic(descendant) in ("native_heading", "explicit_role_heading", "caption")
                and _period_bits(_text(descendant))
                for descendant in _descendants(nodes, node)):
            continue
        if any(parent.ordinal != node.ordinal and parent.ordinal in [n.ordinal for n, _ in raw_period]
                and _semantic(parent) in ("native_heading", "explicit_role_heading", "caption")
                for parent in _ancestor_nodes(nodes, node)):
            continue
        preferred.append((node, bits))
    period_capped = len(preferred) > PERIOD_NODE_CAP
    period_nodes = preferred[:PERIOD_NODE_CAP]

    table_records = []
    for position, table in enumerate(observed_tables):
        descendants = _descendants(nodes, table)
        nested = any(node.tag == "table" for node in descendants)
        malformed = table.malformed or any(node.malformed for node in descendants)
        cells = [node for node in descendants if node.tag in ("td", "th")]
        metric_bits = 0
        for cell in cells:
            category, _ = _metric_category(_text(cell), _text(cell))
            if category:
                metric_bits |= 1 << list(("exact_revenue", "normalized_revenue", "total_revenue",
                    "consolidated_revenue", "record_revenue", "revenue_with_leading_structure",
                    "revenue_inline_boundary_disrupted", "other_revenue", "exact_gaap_diluted_eps",
                    "normalized_gaap_diluted_eps", "diluted_eps_without_gaap", "basic_eps",
                    "adjusted_non_gaap_diluted_eps", "other_diluted_eps")).index(category)
        section = _section(nodes, table)
        phase3b_ok = (not nested and not malformed and all(not cell.nonunit_rowspan
            for cell in cells) and len([n for n in descendants if n.tag == "tr"]) <= 40
            and all(len([nodes[c] for c in row.children if nodes[c].tag in ("td", "th")]) <= 24
                for row in descendants if row.tag == "tr"))
        table_records.append({"table_ordinal": table.ordinal, "parent_ordinal": table.parent,
            "section_ordinal": section.ordinal if section else None,
            "direct_q4_retained_category": "retained" if table.closed else "rejected",
            "current_cap_category": "within_first_eight" if position < 8 else "beyond_first_eight",
            "phase3b_category": "retained" if phase3b_ok else "rejected",
            "nested": nested, "malformed": malformed,
            "colspan_present": any(cell.colspan_present for cell in cells),
            "nonunit_rowspan_present": any(cell.nonunit_rowspan for cell in cells),
            "metric_category_bits": metric_bits,
            "period_category_bits": _period_bits(_text(table))})

    pairs, pairs_capped = [], False
    for heading, bits in period_nodes:
        for table in observed_tables:
            if len(pairs) >= PAIR_CAP:
                pairs_capped = True; break
            pairs.append(_pair(nodes, heading, bits, table))
        if pairs_capped: break

    matches = [pair for pair in pairs if any(pair["rule_outcomes"][rule] == "structurally_matches"
        for rule in pair["rule_outcomes"])]
    by_table = {}
    for pair in matches: by_table.setdefault(pair["table_ordinal"], []).append(pair)
    unique = sum(len(value) == 1 for value in by_table.values())
    ambiguous = sum(len(value) > 1 for value in by_table.values())
    if period_capped or table_starts_capped or pairs_capped:
        unique = 0

    summary = {"period_like_nodes_observed": len(period_nodes),
        "eligible_native_headings": sum(_semantic(node) == "native_heading" for node, _ in period_nodes),
        "eligible_role_headings": sum(_semantic(node) == "explicit_role_heading" for node, _ in period_nodes),
        "captions": sum(node.tag == "caption" for node, _ in period_nodes),
        "ordinary_block_period_nodes": sum(_semantic(node) == "ordinary_block" for node, _ in period_nodes),
        "table_internal_period_nodes": sum(_semantic(node) == "table_internal" for node, _ in period_nodes),
        "tables_observed": len(observed_tables), "pairs_evaluated": len(pairs),
        "caption_precondition_pairs": sum(p["rule_outcomes"]["caption"] == "structurally_matches" for p in pairs),
        "same_parent_precondition_pairs": sum(p["rule_outcomes"]["same_parent_sibling"] == "structurally_matches" for p in pairs),
        "section_precondition_pairs": sum(p["rule_outcomes"]["explicit_section"] == "structurally_matches" for p in pairs),
        "role_heading_precondition_pairs": sum(p["rule_outcomes"]["semantic_heading_role"] == "structurally_matches" for p in pairs),
        "pairs_with_competing_headings": sum(p["same_parent"]["competing_heading_between"] > 0 for p in pairs),
        "pairs_with_competing_tables": sum(p["same_parent"]["competing_table_between"] > 0 for p in pairs),
        "pairs_crossing_section_boundary": sum(p["same_parent"]["section_boundary_between"] for p in pairs),
        "pairs_exceeding_bounds": sum(any(value == "capped" for value in p["rule_outcomes"].values()) for p in pairs),
        "unique_topology_candidate_count": unique,
        "ambiguous_topology_candidate_count": ambiguous}

    return {"schema_version": SCHEMA_VERSION, "diagnostic": DIAGNOSTIC_VERSION,
        "bounds": {"node_cap": NODE_CAP, "period_node_cap": PERIOD_NODE_CAP,
            "table_start_cap": TABLE_START_CAP, "eligible_table_cap": ELIGIBLE_TABLE_CAP,
            "tables_per_section_cap": TABLES_PER_SECTION_CAP, "pair_cap": PAIR_CAP,
            "sibling_distance_cap": SIBLING_DISTANCE_CAP, "ancestor_depth_cap": ANCESTOR_DEPTH_CAP,
            "section_descendant_cap": SECTION_DESCENDANT_CAP},
        "cap_flags": {"node_cap_exceeded": parser.capped,
            "period_node_cap_exceeded": period_capped,
            "table_start_cap_exceeded": table_starts_capped,
            "eligible_table_cap_exceeded": len(top_tables) > ELIGIBLE_TABLE_CAP,
            "tables_per_section_cap_exceeded": any(sum(_section(nodes, table) is section
                for table in top_tables) > TABLES_PER_SECTION_CAP
                for section in [node for node in nodes if node.tag in ("section", "article")]),
            "pair_cap_exceeded": pairs_capped},
        "period_nodes": [_node_record(nodes, node, bits, observed_tables)
            for node, bits in period_nodes],
        "tables": table_records, "pairs": pairs, "summary": {k: _cap(v) for k, v in summary.items()},
        "title_reference_support": "bounded_id_resolution_supported",
        "financial_qualification_performed": False,
        "structural_association_component_invoked": False,
        "fiscal_target_reconciliation_performed": False}


def _ancestor_nodes(nodes, node):
    result, current = [], node
    while current.parent is not None:
        current = nodes[current.parent]; result.append(current)
    return result


def _pair(nodes, heading, bits, table):
    same_parent = heading.parent == table.parent
    precedes = heading.ordinal < table.ordinal
    between = [node for node in nodes if heading.ordinal < node.ordinal < table.ordinal
        and node.parent == heading.parent] if same_parent and precedes else []
    significant = [node for node in between if node.tag in BLOCK_TYPES]
    competing_headings = sum(_semantic(node) in ("native_heading", "explicit_role_heading", "caption")
        and bool(_period_bits(_text(node))) for node in significant)
    competing_period = sum(bool(_period_bits(_text(node))) for node in significant)
    competing_tables = sum(node.tag == "table" for node in significant)
    section_boundary = any(node.tag in ("section", "article") for node in significant)
    sibling_capped = len(significant) > SIBLING_DISTANCE_CAP
    siblings = [node for node in nodes if node.parent == heading.parent]
    following_scope = [node for node in siblings if heading.ordinal < node.ordinal
        and node.tag in BLOCK_TYPES][:SIBLING_DISTANCE_CAP+1]
    scope_tables = sum(node.tag == "table" for node in following_scope)
    preceding_scope = [node for node in siblings if heading.ordinal <= node.ordinal < table.ordinal
        and node.tag in BLOCK_TYPES][-(SIBLING_DISTANCE_CAP+1):]
    scope_headings = sum(_semantic(node) in ("native_heading", "explicit_role_heading", "caption")
        and bool(_period_bits(_text(node))) for node in preceding_scope)
    h_section, t_section = _section(nodes, heading), _section(nodes, table)
    same_section = h_section is not None and t_section is not None and h_section.ordinal == t_section.ordinal
    section_nodes = _descendants(nodes, h_section) if h_section else []
    nested_sections = sum(node.tag in ("section", "article") for node in section_nodes)
    section_headings = sum(_semantic(node) in ("native_heading", "explicit_role_heading", "caption")
        and bool(_period_bits(_text(node))) for node in section_nodes)
    section_tables = sum(node.tag == "table" for node in section_nodes)
    section_capped = (len(section_nodes) > SECTION_DESCENDANT_CAP
        or section_tables > TABLES_PER_SECTION_CAP)
    caption = heading.tag == "caption" and heading.parent == table.ordinal
    role = heading.role_heading
    ref = _title_reference(nodes, heading, table)
    same_parent_match = (same_parent and precedes and not sibling_capped and not competing_headings
        and not competing_tables and scope_tables == 1 and scope_headings == 1
        and not section_boundary and _semantic(heading) in
        ("native_heading", "explicit_role_heading"))
    section_match = (same_section and not section_capped and nested_sections == 0
        and section_headings == 1 and section_tables == 1 and _depth(nodes, table)-_depth(nodes, h_section)
        <= ANCESTOR_DEPTH_CAP)
    outcomes = {"caption": "structurally_matches" if caption else "structurally_does_not_match",
        "same_parent_sibling": "capped" if sibling_capped else
            "structurally_matches" if same_parent_match else
            "ambiguous" if same_parent and (competing_headings or competing_tables
                or scope_tables > 1 or scope_headings > 1) else "structurally_does_not_match",
        "explicit_section": "capped" if section_capped else
            "structurally_matches" if section_match else
            "ambiguous" if same_section and (section_headings > 1 or section_tables > 1) else "structurally_does_not_match",
        "semantic_heading_role": "structurally_matches" if role and (same_parent_match or section_match)
            else "structurally_does_not_match",
        "title_reference": ref}
    return {"period_node_ordinal": heading.ordinal, "table_ordinal": table.ordinal,
        "same_parent": {"same_parent": same_parent, "heading_precedes_table": precedes,
            "significant_nodes_between": min(len(significant), SIBLING_DISTANCE_CAP+1),
            "competing_heading_between": competing_headings,
            "competing_period_node_between": competing_period,
            "competing_table_between": competing_tables,
            "candidate_tables_in_heading_scope": scope_tables,
            "candidate_headings_before_table": scope_headings,
            "section_boundary_between": section_boundary,
            "traversal_cap_exceeded": sibling_capped},
        "section": {"same_explicit_section": same_section,
            "section_type": _type(h_section.tag) if h_section else "other_or_unrepresentable",
            "heading_is_first_eligible": section_headings == 1 if h_section else False,
            "table_descendant": bool(same_section), "nested_competing_sections": nested_sections,
            "competing_heading_count": max(0, section_headings-1),
            "competing_table_count": max(0, section_tables-1),
            "bounded_descendant_count": min(len(section_nodes), SECTION_DESCENDANT_CAP+1),
            "ancestor_depth": min(_depth(nodes, table), ANCESTOR_DEPTH_CAP+1),
            "cap_exceeded": section_capped},
        "caption": {"table_has_caption": any(nodes[c].tag == "caption" for c in table.children),
            "caption_period_like": caption and bool(bits), "caption_hidden": heading.hidden if caption else False,
            "caption_cardinality": sum(nodes[c].tag == "caption" for c in table.children),
            "direct_child_relation": caption},
        "title_reference": ref, "rule_outcomes": outcomes}


def _title_reference(nodes, heading, table):
    if not table.labelledby: return "reference_absent"
    identifiers = table.labelledby.split()
    if len(identifiers) != 1: return "unsupported_or_unrepresentable"
    matches = [node for node in nodes if node.element_id == identifiers[0]]
    if not matches: return "reference_missing_target"
    if len(matches) > 1: return "reference_duplicate_target"
    target = matches[0]
    if target.hidden: return "hidden_target"
    if target.ordinal == table.ordinal: return "reference_cycle"
    return "reference_uniquely_resolves" if target.ordinal == heading.ordinal else "structurally_does_not_match"

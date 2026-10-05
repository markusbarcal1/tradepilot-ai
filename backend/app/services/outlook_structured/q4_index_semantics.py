"""Bounded observational diagnostics for SEC accession-index field semantics."""
from __future__ import annotations

import re


DIAGNOSTIC_VERSION = "sec-index-semantics-1"
ENTRY_LIMIT = 512
TOKEN_LIMIT = 16
TOKEN_LENGTH_LIMIT = 32
TYPE_PATH = "directory.item[].type"
NAME_PATH = "directory.item[].name"
DESCRIPTION_PATH = "directory.item[].description"
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
SAFE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,31}$")
DESCRIPTION_RULES = (
    ("quarterly_results", re.compile(r"\bquarterly\s+results\b", re.I)),
    ("financial_results", re.compile(r"\bfinancial\s+results\b", re.I)),
    ("results_release", re.compile(r"\bresults\s+release\b", re.I)),
    ("press_release", re.compile(r"\bpress\s+release\b", re.I)),
    ("earnings", re.compile(r"\bearnings\b", re.I)),
)
DESCRIPTION_CATEGORIES = tuple(name for name, _ in DESCRIPTION_RULES) + ("other",)


def normalize_type_token(value):
    """Represent a short token without assigning it document-type meaning."""
    if not isinstance(value, str):
        return None
    token = value.strip()
    return token.upper() if SAFE_TOKEN.fullmatch(token) else None


def classify_description(value):
    """Return one observational category using most-specific-first precedence."""
    if not isinstance(value, str):
        return "unrepresentable"
    text = value[:512]
    if not text.strip():
        return "empty"
    for name, pattern in DESCRIPTION_RULES:
        if pattern.search(text):
            return name
    return "other"


def inspect_index_semantics(payload):
    directory = payload.get("directory") if isinstance(payload, dict) else None
    source_items = directory.get("item") if isinstance(directory, dict) else None
    structure_valid = isinstance(source_items, list)
    items = source_items if structure_valid else []
    examined = min(len(items), ENTRY_LIMIT)
    structure_saturated = len(items) > ENTRY_LIMIT
    name = {"schema_path": NAME_PATH, "present": 0, "absent": 0, "null": 0,
        "safe_basename": 0, "unsafe_or_unrepresentable": 0}
    type_path = {"schema_path": TYPE_PATH, "present": 0, "absent": 0, "null": 0,
        "representable": 0, "other_or_unrepresentable": 0, "token_counts": {},
        "distinct_tokens_observed": 0, "distinct_tokens_retained": 0,
        "token_limit": TOKEN_LIMIT, "saturation": False, "overflow_count": 0}
    description = {"schema_path": DESCRIPTION_PATH, "present": 0, "absent": 0,
        "null": 0, "empty": 0, "unrepresentable": 0,
        "category_counts": {category: 0 for category in DESCRIPTION_CATEGORIES}}
    cross_counts = {}

    for item in items[:ENTRY_LIMIT]:
        if not isinstance(item, dict):
            name["absent"] += 1
            type_path["absent"] += 1
            description["absent"] += 1
            continue

        if "name" not in item:
            name["absent"] += 1
        else:
            name["present"] += 1
            if item["name"] is None:
                name["null"] += 1
                name["unsafe_or_unrepresentable"] += 1
            elif isinstance(item["name"], str) and SAFE_NAME.fullmatch(item["name"]):
                name["safe_basename"] += 1
            else:
                name["unsafe_or_unrepresentable"] += 1

        token = None
        retained = False
        if "type" not in item:
            type_path["absent"] += 1
        else:
            type_path["present"] += 1
            if item["type"] is None:
                type_path["null"] += 1
            else:
                token = normalize_type_token(item["type"])
                if token is None:
                    type_path["other_or_unrepresentable"] += 1
                else:
                    type_path["representable"] += 1
                    counts = type_path["token_counts"]
                    if token in counts:
                        counts[token] += 1
                        retained = True
                    elif len(counts) < TOKEN_LIMIT:
                        counts[token] = 1
                        retained = True
                    else:
                        type_path["saturation"] = True
                        type_path["overflow_count"] += 1

        category = None
        if "description" not in item:
            description["absent"] += 1
        else:
            description["present"] += 1
            if item["description"] is None:
                description["null"] += 1
                description["unrepresentable"] += 1
                category = "unrepresentable"
            else:
                category = classify_description(item["description"])
                if category == "empty":
                    description["empty"] += 1
                elif category == "unrepresentable":
                    description["unrepresentable"] += 1
                else:
                    description["category_counts"][category] += 1
        if retained and category is not None:
            key = f"{token}|{category}"
            cross_counts[key] = cross_counts.get(key, 0) + 1

    type_path["token_counts"] = dict(sorted(type_path["token_counts"].items()))
    type_path["distinct_tokens_retained"] = len(type_path["token_counts"])
    type_path["distinct_tokens_observed"] = (
        type_path["distinct_tokens_retained"] + (1 if type_path["saturation"] else 0))
    cross_tab = {"counts": dict(sorted(cross_counts.items())),
        "saturation": type_path["saturation"],
        "overflow_count": type_path["overflow_count"]}
    return {"diagnostic_version": DIAGNOSTIC_VERSION,
        "structure": {"schema_path": "directory.item", "valid_list": structure_valid,
            "entries_examined": examined, "count_limit": ENTRY_LIMIT,
            "saturation": structure_saturated},
        "name_path": name, "type_path": type_path,
        "description_path": description, "cross_tab": cross_tab}

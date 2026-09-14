import asyncio
import json
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.auth import get_current_user
from app.main import app
from app.models.outlook import (CLASSIFICATIONS, CATEGORY_TITLES, OutlookCategory,
                                OutlookMetadata, OutlookResponse, classification_label)
from app.services.outlook import aggregate_outlook, analyze_outlook
from tests.test_authenticated_api_isolation import call_asgi

META = OutlookMetadata(provider="fixture", uses_placeholder_data=False)


@pytest.mark.parametrize("value,label", CLASSIFICATIONS.items())
def test_classifications(value, label):
    assert classification_label(value) == label
    category = OutlookCategory(status="available", value=value)
    assert category.model_dump()["label"] == label


@pytest.mark.parametrize("value,label", [(1.5, "Very Positive"), (0.5, "Positive"),
    (0.49, "Mixed"), (-0.49, "Mixed"), (-0.5, "Negative"), (-1.5, "Very Negative")])
def test_thresholds(value, label):
    assert classification_label(value) == label


def test_placeholder_and_serialization():
    first = analyze_outlook(" aapl ")
    assert first == analyze_outlook("AAPL")
    assert first.status == "placeholder"
    assert first.label is None and first.value is None
    assert first.metadata.uses_placeholder_data
    assert set(first.categories) == set(CATEGORY_TITLES)
    assert all(c.status == "insufficient_data" and not c.factors for c in first.categories.values())
    assert OutlookResponse.model_validate_json(first.model_dump_json()) == first
    assert json.loads(first.model_dump_json())["label"] is None


def test_aggregation_excludes_missing_and_not_material():
    categories = {
        "company": OutlookCategory(status="available", value=2),
        "earnings": OutlookCategory(status="available", value=0),
        "geopolitical": OutlookCategory(status="not_material"),
    }
    result = aggregate_outlook("AAPL", categories, META)
    assert result.value == 1 and result.label == "Positive" and result.status == "partial"
    assert result.categories["geopolitical"].label is None
    assert aggregate_outlook("AAPL", dict(reversed(list(categories.items()))), META) == result
    assert aggregate_outlook("AAPL", {}, META).value is None
    assert aggregate_outlook("AAPL", {key: OutlookCategory(status="not_material")
                                      for key in CATEGORY_TITLES}, META).label is None


def test_available_categories_and_factors():
    categories = {key: OutlookCategory(status="available", value=-1, factors=[{
        "title": "Fixture", "impact": "Negative", "description": "Demo evidence only."
    }]) for key in CATEGORY_TITLES}
    categories["geopolitical"] = OutlookCategory(status="not_material")
    result = aggregate_outlook("TEST", categories, META)
    assert result.status == "available" and result.label == "Negative"
    assert json.loads(result.model_dump_json())["categories"]["company"]["factors"][0]["impact"] == "Negative"


@pytest.mark.parametrize("status,value", [("available", None), ("unavailable", -1),
                                        ("not_material", -2), ("available", 3)])
def test_invalid_evidence_is_rejected(status, value):
    with pytest.raises(ValidationError):
        OutlookCategory(status=status, value=value)


def test_provider_failure_and_invalid_output_are_safe():
    class Broken:
        name = "fixture"
        uses_placeholder_data = False
        def get_evidence(self, ticker):
            raise RuntimeError("private provider error")
    result = analyze_outlook("TEST", Broken())
    assert result.status == "error" and result.label is None
    assert "private provider error" not in result.model_dump_json()
    class Invalid(Broken):
        def get_evidence(self, ticker):
            return {"company": {"status": "available", "value": 10}}
    assert analyze_outlook("TEST", Invalid()).status == "error"


def test_http_contract_and_authentication():
    status, _, _ = asyncio.run(call_asgi("GET", "/outlook/AAPL"))
    assert status == 401
    with patch.dict(app.dependency_overrides, {get_current_user: lambda: object()}):
        status, _, payload = asyncio.run(call_asgi("GET", "/outlook/AAPL"))
    assert status == 200 and payload["status"] == "placeholder"
    assert payload["value"] is None and payload["label"] is None
    assert set(payload["categories"]) == set(CATEGORY_TITLES)


def test_overall_contract_rejects_inconsistent_states():
    payload = analyze_outlook("TEST").model_dump()
    with pytest.raises(ValidationError):
        OutlookResponse.model_validate({**payload, "value": -1})
    with pytest.raises(ValidationError):
        OutlookResponse.model_validate({**payload, "categories": {}})

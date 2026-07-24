from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


DEFAULT_MINIMUM_PRICE = 5.0
DEFAULT_MINIMUM_AVERAGE_VOLUME = 500_000
DEFAULT_MINIMUM_HISTORY_BARS = 100
DEFAULT_EXCLUDE_ETFS = True
DEFAULT_EXCLUDE_LEVERAGED_ETFS = True
DEFAULT_EXCLUDE_INVERSE_ETFS = True
DEFAULT_EXCLUDE_VOLATILITY_PRODUCTS = True
DEFAULT_EXCLUDE_WARRANTS = True
DEFAULT_EXCLUDE_UNITS = True
DEFAULT_EXCLUDE_RIGHTS = True
DEFAULT_EXCLUDE_PREFERRED_SHARES = True
DEFAULT_EXCLUDE_BLANK_CHECK_COMPANIES = True
DEFAULT_REQUIRE_VALID_LATEST_PRICE = True
DEFAULT_REQUIRE_VALID_VOLUME = True


@dataclass
class ScannerEligibilityConfig:
    enabled: bool = True
    minimum_price: float = DEFAULT_MINIMUM_PRICE
    minimum_average_volume: int = DEFAULT_MINIMUM_AVERAGE_VOLUME
    minimum_history_bars: int = DEFAULT_MINIMUM_HISTORY_BARS
    exclude_etfs: bool = DEFAULT_EXCLUDE_ETFS
    exclude_leveraged_etfs: bool = DEFAULT_EXCLUDE_LEVERAGED_ETFS
    exclude_inverse_etfs: bool = DEFAULT_EXCLUDE_INVERSE_ETFS
    exclude_volatility_products: bool = DEFAULT_EXCLUDE_VOLATILITY_PRODUCTS
    exclude_warrants: bool = DEFAULT_EXCLUDE_WARRANTS
    exclude_units: bool = DEFAULT_EXCLUDE_UNITS
    exclude_rights: bool = DEFAULT_EXCLUDE_RIGHTS
    exclude_preferred_shares: bool = DEFAULT_EXCLUDE_PREFERRED_SHARES
    exclude_blank_check_companies: bool = DEFAULT_EXCLUDE_BLANK_CHECK_COMPANIES
    require_valid_latest_price: bool = DEFAULT_REQUIRE_VALID_LATEST_PRICE
    require_valid_volume: bool = DEFAULT_REQUIRE_VALID_VOLUME
    metadata_only: bool = False

    @classmethod
    def from_dict(cls, values: dict[str, Any] | None) -> "ScannerEligibilityConfig":
        if not values:
            return cls()

        merged = {
            "enabled": values.get("enabled", True),
            "minimum_price": values.get("minimum_price", DEFAULT_MINIMUM_PRICE),
            "minimum_average_volume": values.get("minimum_average_volume", DEFAULT_MINIMUM_AVERAGE_VOLUME),
            "minimum_history_bars": values.get("minimum_history_bars", DEFAULT_MINIMUM_HISTORY_BARS),
            "exclude_etfs": values.get("exclude_etfs", DEFAULT_EXCLUDE_ETFS),
            "exclude_leveraged_etfs": values.get("exclude_leveraged_etfs", DEFAULT_EXCLUDE_LEVERAGED_ETFS),
            "exclude_inverse_etfs": values.get("exclude_inverse_etfs", DEFAULT_EXCLUDE_INVERSE_ETFS),
            "exclude_volatility_products": values.get("exclude_volatility_products", DEFAULT_EXCLUDE_VOLATILITY_PRODUCTS),
            "exclude_warrants": values.get("exclude_warrants", DEFAULT_EXCLUDE_WARRANTS),
            "exclude_units": values.get("exclude_units", DEFAULT_EXCLUDE_UNITS),
            "exclude_rights": values.get("exclude_rights", DEFAULT_EXCLUDE_RIGHTS),
            "exclude_preferred_shares": values.get("exclude_preferred_shares", DEFAULT_EXCLUDE_PREFERRED_SHARES),
            "exclude_blank_check_companies": values.get("exclude_blank_check_companies", DEFAULT_EXCLUDE_BLANK_CHECK_COMPANIES),
            "require_valid_latest_price": values.get("require_valid_latest_price", DEFAULT_REQUIRE_VALID_LATEST_PRICE),
            "require_valid_volume": values.get("require_valid_volume", DEFAULT_REQUIRE_VALID_VOLUME),
            "metadata_only": values.get("metadata_only", False),
        }

        try:
            minimum_price = float(merged["minimum_price"])
        except (TypeError, ValueError):
            minimum_price = DEFAULT_MINIMUM_PRICE

        try:
            minimum_average_volume = int(merged["minimum_average_volume"])
        except (TypeError, ValueError):
            minimum_average_volume = DEFAULT_MINIMUM_AVERAGE_VOLUME

        try:
            minimum_history_bars = int(merged["minimum_history_bars"])
        except (TypeError, ValueError):
            minimum_history_bars = DEFAULT_MINIMUM_HISTORY_BARS

        if minimum_price < 0:
            minimum_price = DEFAULT_MINIMUM_PRICE
        if minimum_average_volume < 0:
            minimum_average_volume = DEFAULT_MINIMUM_AVERAGE_VOLUME
        if minimum_history_bars < 1:
            minimum_history_bars = DEFAULT_MINIMUM_HISTORY_BARS

        return cls(
            enabled=bool(merged["enabled"]),
            minimum_price=minimum_price,
            minimum_average_volume=minimum_average_volume,
            minimum_history_bars=minimum_history_bars,
            exclude_etfs=bool(merged["exclude_etfs"]),
            exclude_leveraged_etfs=bool(merged["exclude_leveraged_etfs"]),
            exclude_inverse_etfs=bool(merged["exclude_inverse_etfs"]),
            exclude_volatility_products=bool(merged["exclude_volatility_products"]),
            exclude_warrants=bool(merged["exclude_warrants"]),
            exclude_units=bool(merged["exclude_units"]),
            exclude_rights=bool(merged["exclude_rights"]),
            exclude_preferred_shares=bool(merged["exclude_preferred_shares"]),
            exclude_blank_check_companies=bool(merged["exclude_blank_check_companies"]),
            require_valid_latest_price=bool(merged["require_valid_latest_price"]),
            require_valid_volume=bool(merged["require_valid_volume"]),
            metadata_only=bool(merged["metadata_only"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "minimum_price": self.minimum_price,
            "minimum_average_volume": self.minimum_average_volume,
            "minimum_history_bars": self.minimum_history_bars,
            "exclude_etfs": self.exclude_etfs,
            "exclude_leveraged_etfs": self.exclude_leveraged_etfs,
            "exclude_inverse_etfs": self.exclude_inverse_etfs,
            "exclude_volatility_products": self.exclude_volatility_products,
            "exclude_warrants": self.exclude_warrants,
            "exclude_units": self.exclude_units,
            "exclude_rights": self.exclude_rights,
            "exclude_preferred_shares": self.exclude_preferred_shares,
            "exclude_blank_check_companies": self.exclude_blank_check_companies,
            "require_valid_latest_price": self.require_valid_latest_price,
            "require_valid_volume": self.require_valid_volume,
            "metadata_only": self.metadata_only,
        }


@dataclass
class EligibilityResult:
    eligible: bool
    stage: str
    reason_code: str
    message: str
    observed_value: Any | None = None
    required_value: Any | None = None
    security_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "stage": self.stage,
            "reason_code": self.reason_code,
            "message": self.message,
            "observed_value": self.observed_value,
            "required_value": self.required_value,
            "security_type": self.security_type,
        }


def normalize_security_type(value: Any) -> str:
    if value is None:
        return "unknown"

    text = str(value).strip().lower()
    if not text:
        return "unknown"

    aliases = {
        "common stock": "common_stock",
        "common": "common_stock",
        "equity": "common_stock",
        "stock": "common_stock",
        "etf": "etf",
        "exchange traded fund": "etf",
        "fund": "fund",
        "index": "index",
        "leveraged etf": "leveraged_etf",
        "inverse etf": "inverse_etf",
        "leveraged": "leveraged_etf",
        "inverse": "inverse_etf",
        "volatility": "volatility_product",
        "volatility product": "volatility_product",
        "warrant": "warrant",
        "unit": "unit",
        "right": "right",
        "preferred share": "preferred_share",
        "preferred": "preferred_share",
        "blank check": "blank_check_company",
        "blank-check": "blank_check_company",
        "spac": "blank_check_company",
    }

    return aliases.get(text, text.replace(" ", "_"))


def classify_security_type(metadata: dict[str, Any] | None) -> str:
    if not metadata:
        return "unknown"

    for field_name in ("quoteType", "typeDisp", "securityType", "instrumentType", "assetType", "category"):
        normalized = normalize_security_type(metadata.get(field_name))
        if normalized != "unknown":
            return normalized

    for field_name in ("longName", "shortName", "fundFamily"):
        text = str(metadata.get(field_name) or "").lower()
        if "etf" in text:
            if "leveraged" in text or "inverse" in text:
                return "leveraged_etf" if "leveraged" in text else "inverse_etf"
            return "etf"
        if "warrant" in text:
            return "warrant"
        if "unit" in text:
            return "unit"
        if "right" in text:
            return "right"
        if "preferred" in text:
            return "preferred_share"
        if "spac" in text or "blank check" in text:
            return "blank_check_company"

    return "unknown"


def evaluate_metadata_eligibility(symbol: str, metadata: dict[str, Any] | None, config: ScannerEligibilityConfig) -> EligibilityResult:
    if not config.enabled:
        return EligibilityResult(True, "metadata", "eligibility_disabled", "Eligibility disabled.")

    security_type = classify_security_type(metadata)

    if security_type == "etf" and config.exclude_etfs:
        return EligibilityResult(False, "metadata", "etf_excluded", "ETF instruments are excluded from the equity scanner.", security_type=security_type)
    if security_type == "leveraged_etf" and config.exclude_leveraged_etfs:
        return EligibilityResult(False, "metadata", "leveraged_etf_excluded", "Leveraged ETFs are excluded from the equity scanner.", security_type=security_type)
    if security_type == "inverse_etf" and config.exclude_inverse_etfs:
        return EligibilityResult(False, "metadata", "inverse_etf_excluded", "Inverse ETFs are excluded from the equity scanner.", security_type=security_type)
    if security_type == "volatility_product" and config.exclude_volatility_products:
        return EligibilityResult(False, "metadata", "volatility_product_excluded", "Volatility products are excluded from the equity scanner.", security_type=security_type)
    if security_type == "warrant" and config.exclude_warrants:
        return EligibilityResult(False, "metadata", "warrant_excluded", "Warrants are excluded from the equity scanner.", security_type=security_type)
    if security_type == "unit" and config.exclude_units:
        return EligibilityResult(False, "metadata", "unit_excluded", "Units are excluded from the equity scanner.", security_type=security_type)
    if security_type == "right" and config.exclude_rights:
        return EligibilityResult(False, "metadata", "right_excluded", "Rights are excluded from the equity scanner.", security_type=security_type)
    if security_type == "preferred_share" and config.exclude_preferred_shares:
        return EligibilityResult(False, "metadata", "preferred_share_excluded", "Preferred shares are excluded from the equity scanner.", security_type=security_type)
    if security_type == "blank_check_company" and config.exclude_blank_check_companies:
        return EligibilityResult(False, "metadata", "blank_check_company_excluded", "Blank-check companies are excluded from the equity scanner.", security_type=security_type)

    return EligibilityResult(True, "metadata", "eligible", "Eligible by metadata.", security_type=security_type)


def evaluate_market_data_eligibility(symbol: str, history: pd.DataFrame | None, config: ScannerEligibilityConfig) -> EligibilityResult:
    if not config.enabled:
        return EligibilityResult(True, "market_data", "eligibility_disabled", "Eligibility disabled.")

    if history is None:
        return EligibilityResult(False, "market_data", "empty_history", "No market data was returned.")

    if getattr(history, "empty", True):
        return EligibilityResult(False, "market_data", "empty_history", "Market data history is empty.")

    required_columns = {"Open", "High", "Low", "Close", "Volume"}
    missing_columns = sorted(required_columns - set(history.columns))
    if missing_columns:
        return EligibilityResult(False, "market_data", "missing_required_column", f"Missing required columns: {', '.join(missing_columns)}.")

    latest = history.iloc[-1]
    latest_close = latest.get("Close")
    if config.require_valid_latest_price:
        try:
            latest_close_value = float(latest_close)
        except (TypeError, ValueError):
            return EligibilityResult(False, "market_data", "invalid_latest_price", "Latest price is invalid or missing.")

        if math.isnan(latest_close_value) or math.isinf(latest_close_value):
            return EligibilityResult(False, "market_data", "invalid_latest_price", "Latest price is invalid or missing.")
        if latest_close_value < config.minimum_price:
            return EligibilityResult(False, "market_data", "below_minimum_price", f"Latest price {latest_close_value:.2f} is below the minimum of {config.minimum_price:.2f}.", observed_value=latest_close_value, required_value=config.minimum_price)

    volume_series = history.get("Volume")
    if volume_series is None:
        return EligibilityResult(False, "market_data", "invalid_average_volume", "Volume data is missing.")

    valid_volumes = []
    for value in volume_series:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            continue
        if math.isnan(numeric_value) or math.isinf(numeric_value):
            continue
        valid_volumes.append(numeric_value)

    if not valid_volumes:
        return EligibilityResult(False, "market_data", "invalid_average_volume", "No valid volume values were found.")

    if len(valid_volumes) < 1:
        return EligibilityResult(False, "market_data", "invalid_average_volume", "No valid volume values were found.")

    average_volume = float(sum(valid_volumes[-20:]) / min(20, len(valid_volumes))) if len(valid_volumes) >= 1 else 0.0
    if config.require_valid_volume and average_volume < config.minimum_average_volume:
        return EligibilityResult(False, "market_data", "below_minimum_average_volume", f"Average volume {int(average_volume):,} is below the minimum of {config.minimum_average_volume:,}.", observed_value=int(average_volume), required_value=config.minimum_average_volume)

    if len(history) < config.minimum_history_bars:
        return EligibilityResult(False, "market_data", "insufficient_history", f"Only {len(history)} bars of history were returned; {config.minimum_history_bars} are required.", observed_value=len(history), required_value=config.minimum_history_bars)

    return EligibilityResult(True, "market_data", "eligible", "Eligible by market-data checks.")


def get_eligibility_reason_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        reason_code = record.get("reason_code") or "eligible"
        counts[reason_code] = counts.get(reason_code, 0) + 1
    return counts

"""Versioned offline packages. Expectations are assertions, not stock advice."""
from typing import Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from app.models.outlook_document import SourceDocument
from app.models.outlook_evidence import CompanyContext, OutlookEvidence
from app.models.outlook_taxonomy import CategoryKey, EventType


class FixtureModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FrozenSource(FixtureModel):
    document: SourceDocument
    html: str | None = None
    expected_exhibit_url: str | None = None


class Assertion(FixtureModel):
    source_id: str | None = None
    category: CategoryKey
    event_type: EventType
    metric: str | None = None
    sign: Literal[-1, 0, 1] | None = None
    qualifier: str | None = None
    accounting_basis: str | None = None


class Relationship(FixtureModel):
    original: str
    subsequent: str
    kind: Literal["amendment", "correction", "supersession", "forecast_update"]
    reporting_period: str
    note: str


class Outcome(FixtureModel):
    category: CategoryKey
    events: int
    support: tuple[float, float] | None = None
    direction: tuple[float, float] | None = None
    status: Literal["available", "insufficient_data", "not_material"]
    label: str | None = None

    @model_validator(mode="after")
    def valid_bounds(self):
        if self.events < 0 or any(bounds and bounds[0] > bounds[1] for bounds in (self.support, self.direction)):
            raise ValueError("Invalid outcome count or interval")
        return self


class ReplayPoint(FixtureModel):
    name: str
    assessment_at: AwareDatetime
    outcomes: tuple[Outcome, ...]
    available_categories: int
    overall_status: Literal["partial", "available", "unavailable"]
    overall_label: str | None = None
    expected_reporting_periods: tuple[str, ...] | None = None
    expected_missing_periods: tuple[str, ...] | None = None


class ReportingGap(FixtureModel):
    period: str
    cause: Literal["confirmed_missing_report", "retrieval_gap", "unknown_identity"]
    known_at: AwareDatetime
    basis: str


class EvaluationPackage(FixtureModel):
    id: str
    description: str
    context: CompanyContext
    event_identity: str
    reporting_period: str
    materiality_rationale: str
    sources: tuple[FrozenSource, ...] = ()
    evidence: tuple[OutlookEvidence, ...] = ()
    supported_assertions: tuple[Assertion, ...] = ()
    unsupported_assertions: tuple[Assertion, ...] = ()
    expected_duplicate_groups: tuple[tuple[str, ...], ...] = ()
    relationships: tuple[Relationship, ...] = ()
    reporting_gaps: tuple[ReportingGap, ...] = ()
    semantic_tags: tuple[str, ...]
    replays: tuple[ReplayPoint, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def references(self):
        records = [s.document for s in self.sources] + list(self.evidence)
        ids = {r.id for r in records}
        if len(ids) != len(records):
            raise ValueError("Source/evidence IDs must be unique within a package")
        if any(r.ticker != self.context.ticker.upper() for r in records):
            raise ValueError("Package issuer and evidence must agree")
        refs = {a.source_id for a in (*self.supported_assertions, *self.unsupported_assertions) if a.source_id}
        refs.update(member for group in self.expected_duplicate_groups for member in group)
        refs.update(ref for r in self.relationships for ref in (r.original, r.subsequent))
        if not refs <= ids:
            raise ValueError("Unknown fixture reference")
        if len({p.name for p in self.replays}) != len(self.replays):
            raise ValueError("Replay names must be unique")
        return self


class EvaluationCorpus(FixtureModel):
    schema_version: Literal["1.0"]
    corpus_version: str
    provenance: str
    packages: tuple[EvaluationPackage, ...]

    @model_validator(mode="after")
    def unique_packages(self):
        if len({p.id for p in self.packages}) != len(self.packages):
            raise ValueError("Duplicate package IDs")
        return self

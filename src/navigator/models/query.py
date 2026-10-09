"""Retrieval query contract (M2.2).

Three layers:
- user layer — ``confirmed_question`` (the main retrieval question), ``context``
  (circumstance / narrative, stored for trace and later evaluation, never an
  embedding signal in the baseline) and ``experiences`` (stored, not weighted);
- interpretation layer — 2–4 ``working_hypotheses`` (working readings, not a
  diagnosis);
- structural layer — TAXONOMY ``coordinates``, ``canonical_tensions`` (closed
  TAXONOMY list) and ``free_tensions`` (meaningful tensions outside it; they
  never extend the taxonomy).

``origin`` makes the provenance of the interpretation explicit. The benchmark
adapter (``navigator.benchmark.adapter``) builds queries from benchmark cases —
center as confirmed-question proxy, expected structure as interpretation proxy —
and must never be mistaken for a production interpretation layer.

TECHNICAL-DESIGN D04 additionally lists narrative_facts, representations,
question_aspects, narrative_constraints and retrieval_summary; they belong to the
qualification/coverage stages and are not part of the M2.2 candidate-retrieval
contract.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

from navigator.models.vocabularies import COORDINATES, TENSIONS

NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]

QUERY_SCHEMA_VERSION = "query-representation/0.1.0"

QueryOrigin = Literal["benchmark_adapter", "production"]

# Attributes that must never be part of a retrieval query (M2.2 §3).
FORBIDDEN_QUERY_ATTRIBUTES = frozenset(
    {"demographics", "country", "gender", "age", "personality_type", "diagnosis", "tradition", "author"}
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class UserContext(_Strict):
    """Stored for trace/evaluation. Not a retrieval signal in the baseline."""

    circumstance: NonEmptyStr | None = None
    narrative: NonEmptyStr | None = None


class QueryProvenance(_Strict):
    origin: QueryOrigin
    confirmed_question_source: NonEmptyStr
    interpretation_source: NonEmptyStr
    benchmark_item_id: NonEmptyStr | None = None
    note: NonEmptyStr | None = None

    @model_validator(mode="after")
    def _benchmark_marked(self):
        if self.origin == "benchmark_adapter":
            if not self.confirmed_question_source.startswith("benchmark_"):
                raise ValueError("benchmark-adapter queries must name a benchmark_* confirmed-question source")
            if not self.interpretation_source.startswith("benchmark_"):
                raise ValueError("benchmark-adapter queries must name a benchmark_* interpretation source")
            if not self.benchmark_item_id:
                raise ValueError("benchmark-adapter queries must carry benchmark_item_id")
        return self


class QueryRepresentation(_Strict):
    schema_version: Literal["query-representation/0.1.0"] = QUERY_SCHEMA_VERSION

    # A. user layer
    confirmed_question: NonEmptyStr
    context: UserContext = Field(default_factory=UserContext)
    experiences: list[NonEmptyStr] = Field(default_factory=list)

    # B. interpretation layer
    working_hypotheses: list[NonEmptyStr] = Field(min_length=2, max_length=4)

    # C. structural layer
    coordinates: list[NonEmptyStr] = Field(default_factory=list)
    canonical_tensions: list[NonEmptyStr] = Field(default_factory=list)
    free_tensions: list[NonEmptyStr] = Field(default_factory=list)

    provenance: QueryProvenance

    @field_validator("coordinates")
    @classmethod
    def _canonical_coordinates(cls, v: list[str]) -> list[str]:
        bad = [c for c in v if c not in COORDINATES]
        if bad:
            raise ValueError(f"coordinates outside TAXONOMY v1.1: {bad}")
        if len(set(v)) != len(v):
            raise ValueError("coordinates contain duplicates")
        return v

    @field_validator("canonical_tensions")
    @classmethod
    def _canonical_tensions(cls, v: list[str]) -> list[str]:
        bad = [t for t in v if t not in TENSIONS]
        if bad:
            raise ValueError(f"canonical_tensions outside TAXONOMY v1.1: {bad}")
        if len(set(v)) != len(v):
            raise ValueError("canonical_tensions contain duplicates")
        return v

    @field_validator("free_tensions")
    @classmethod
    def _free_tensions(cls, v: list[str]) -> list[str]:
        canonical = [t for t in v if t in TENSIONS]
        if canonical:
            raise ValueError(f"canonical tensions must go to canonical_tensions, not free_tensions: {canonical}")
        if any("↔" not in t for t in v):
            raise ValueError("free tensions must follow the 'A ↔ B' convention")
        return v

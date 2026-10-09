"""Typed schema of the M2.1 retrieval benchmark (machine-readable form).

Source of truth: ``M2.1-RETRIEVAL-BENCHMARK-v0.1.md``. The expected structure of
a case is evaluation guidance, not a gold label (spec §2, §8.3–4): nothing here
may be used as an exact-match assertion on future retrieval output.

``extra="forbid"`` keeps mandatory card IDs, required traditions/authors or any
other undeclared field out of the benchmark (spec §8.1–2).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]
CaseId = Annotated[str, Field(pattern=r"^B\d{2}$")]
PairId = Annotated[str, Field(pattern=r"^CP\d$")]
VariantId = Annotated[str, Field(pattern=r"^CP\d-[AB]$")]

BENCHMARK_SCHEMA_VERSION = "benchmark-schema/0.1.0"

EvaluationDimensionId = Literal["relevance", "transformative_value", "distinctness", "grounding", "corpus_fit"]
EVALUATION_DIMENSIONS: tuple[str, ...] = ("relevance", "transformative_value", "distinctness", "grounding", "corpus_fit")

FailureCategoryId = Literal["INTERPRETATION", "QUERY", "RECALL", "CORPUS", "RANKING", "COMPOSITION", "UNRESOLVED"]
FAILURE_CATEGORIES: tuple[str, ...] = ("INTERPRETATION", "QUERY", "RECALL", "CORPUS", "RANKING", "COMPOSITION", "UNRESOLVED")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TensionRef(_Strict):
    """A tension exactly as written in the spec, with its relation to TAXONOMY v1.1.

    ``exact`` — identical to a TAXONOMY tension; ``reversed_poles`` — the same
    TAXONOMY tension with poles swapped; ``case_specific`` — a case-level
    formulation outside the closed TAXONOMY list (kept verbatim).
    """

    text: NonEmptyStr
    match: Literal["exact", "reversed_poles", "case_specific"]
    taxonomy_tension: NonEmptyStr | None = None

    @model_validator(mode="after")
    def _consistent(self):
        if (self.match == "case_specific") != (self.taxonomy_tension is None):
            raise ValueError("taxonomy_tension must be set iff match is exact or reversed_poles")
        return self


class ExpectedStructure(_Strict):
    role: Literal["evaluation_guidance"] = "evaluation_guidance"
    semantic_node: NonEmptyStr
    probable_coordinates: list[NonEmptyStr] = Field(min_length=1)
    probable_tensions: list[TensionRef] = Field(min_length=1)
    distinctions: list[NonEmptyStr] = Field(min_length=1)


class BenchmarkCase(_Strict):
    id: CaseId
    title: NonEmptyStr
    circumstance: NonEmptyStr
    experiences: list[NonEmptyStr] = Field(min_length=1)
    center: NonEmptyStr
    narrative: NonEmptyStr
    expected_structure: ExpectedStructure
    failure_traps: list[NonEmptyStr] = Field(min_length=1)


class ContrastVariant(_Strict):
    """One side of a contrast pair: a reference to a main case or a new narrative."""

    id: VariantId
    case_ref: CaseId | None = None
    note: NonEmptyStr | None = None
    narrative: NonEmptyStr | None = None
    expected: NonEmptyStr | None = None
    probable_coordinates: list[NonEmptyStr] = Field(default_factory=list)
    probable_tensions: list[TensionRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _one_input(self):
        if (self.case_ref is None) == (self.narrative is None):
            raise ValueError(f"{self.id}: exactly one of case_ref / narrative must be set")
        return self


class ContrastPair(_Strict):
    id: PairId
    title: NonEmptyStr
    variant_a: ContrastVariant
    variant_b: ContrastVariant
    expected_semantic_shift: NonEmptyStr | None = None
    contrast_requirement: NonEmptyStr

    @model_validator(mode="after")
    def _shift_present(self):
        has_variant_expectations = bool(self.variant_a.expected and self.variant_b.expected)
        if not self.expected_semantic_shift and not has_variant_expectations:
            raise ValueError(f"{self.id}: needs expected_semantic_shift or expectations for both variants")
        return self


class ScaleLevel(_Strict):
    score: Literal[0, 1, 2]
    description: NonEmptyStr


class EvaluationDimension(_Strict):
    id: EvaluationDimensionId
    label: NonEmptyStr
    levels: list[ScaleLevel] = Field(min_length=3, max_length=3)


class SetLevelEvaluation(_Strict):
    set_size: dict[Literal["min", "max"], int]
    main_question: NonEmptyStr
    checks: list[NonEmptyStr] = Field(min_length=1)


class Evaluation(_Strict):
    scale: list[Literal[0, 1, 2]]
    card_level_dimensions: list[EvaluationDimension]
    aggregate_score: Literal[False] = False
    aggregate_policy: NonEmptyStr
    set_level: SetLevelEvaluation


class FailureCategory(_Strict):
    id: FailureCategoryId
    description: NonEmptyStr


class CorpusContext(_Strict):
    total: int
    retrieval_eligible: int
    unresolved: int
    source_route: NonEmptyStr


class Benchmark(_Strict):
    schema_version: Literal["benchmark-schema/0.1.0"] = BENCHMARK_SCHEMA_VERSION
    benchmark_id: NonEmptyStr
    version: NonEmptyStr
    spec_document: NonEmptyStr
    spec_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    corpus_context: CorpusContext
    required_routes: list[Literal["MEANING", "STRUCTURE"]]
    source_route_required: Literal[False] = False
    expected_structure_policy: Literal["evaluation_guidance_not_gold_label"] = "evaluation_guidance_not_gold_label"
    cases: list[BenchmarkCase]
    contrast_principle: NonEmptyStr
    contrast_pairs: list[ContrastPair]
    evaluation: Evaluation
    failure_taxonomy: list[FailureCategory]
    rules: list[NonEmptyStr]
    trace_fields: list[NonEmptyStr]

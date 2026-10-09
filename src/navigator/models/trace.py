"""Data contract for a future M2.1 benchmark run (spec §9).

Contract only: nothing in the project produces these objects yet. Route names,
the query-representation shape beyond coordinates/tensions, score semantics and
the final set size are left open for M2.2 (see M2.1 closeout).

Hard invariants enforced here:
- only MEANING / STRUCTURE routes (SOURCE is disabled);
- no unresolved Fragment may appear anywhere in a trace;
- card evaluation uses exactly the five spec dimensions on a 0/1/2 scale and
  carries no aggregate score.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

from navigator.models.benchmark import FailureCategoryId
from navigator.models.retrieval import CandidateRetrievalResult
from navigator.models.vocabularies import UNRESOLVED_IDS

NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]
FragmentId = Annotated[str, Field(pattern=r"^C\d{4}$")]
BenchmarkItemId = Annotated[str, Field(pattern=r"^(B\d{2}|CP\d-[AB])$")]
Route = Literal["MEANING", "STRUCTURE"]
Score = Literal[0, 1, 2]

TRACE_SCHEMA_VERSION = "benchmark-trace/0.2.0"  # 0.2.0 adds candidate_retrieval (M2.2); 0.1.0 stays valid


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UserInput(_Strict):
    circumstance: NonEmptyStr | None = None
    experiences: list[NonEmptyStr] = Field(default_factory=list)
    center: NonEmptyStr | None = None
    narrative: NonEmptyStr


class WorkingHypothesis(_Strict):
    text: NonEmptyStr


class QueryRepresentation(_Strict):
    """M2.1 summary of the query. The full M2.2 contract is
    ``navigator.models.query.QueryRepresentation`` (in ``candidate_retrieval.query``)."""

    coordinates: list[NonEmptyStr] = Field(default_factory=list)
    tensions: list[NonEmptyStr] = Field(default_factory=list)
    # Remaining elements are not fixed before M2.2.
    other: dict[str, Any] = Field(default_factory=dict)


class RouteCandidate(_Strict):
    fragment_id: FragmentId
    route: Route
    rank: int | None = Field(default=None, ge=1)
    score: float | None = None
    signals: dict[str, Any] = Field(default_factory=dict)


class PoolCandidate(_Strict):
    fragment_id: FragmentId
    found_by: list[Route] = Field(min_length=1)
    signals: dict[str, Any] = Field(default_factory=dict)
    excluded: bool = False
    exclusion_reason: NonEmptyStr | None = None


class FinalCard(_Strict):
    fragment_id: FragmentId
    role: NonEmptyStr
    explanation: NonEmptyStr


class CardEvaluation(_Strict):
    fragment_id: FragmentId
    relevance: Score | None = None
    transformative_value: Score | None = None
    distinctness: Score | None = None
    grounding: Score | None = None
    corpus_fit: Score | None = None
    notes: NonEmptyStr | None = None


class SetEvaluation(_Strict):
    several_distinct_ways: bool | None = None
    semantic_duplication: NonEmptyStr | None = None
    operation_diversity: NonEmptyStr | None = None
    weak_cards_for_diversity: NonEmptyStr | None = None
    link_to_real_question: NonEmptyStr | None = None


class FailureClassification(_Strict):
    category: FailureCategoryId
    fragment_id: FragmentId | None = None
    notes: NonEmptyStr | None = None


class BenchmarkRunTrace(_Strict):
    schema_version: Literal["benchmark-trace/0.1.0", "benchmark-trace/0.2.0"] = TRACE_SCHEMA_VERSION
    run_id: NonEmptyStr
    benchmark_version: NonEmptyStr
    item_id: BenchmarkItemId
    config: dict[str, Any] = Field(default_factory=dict)  # versions of corpus/models/prompts etc.

    input: UserInput
    working_hypotheses: list[WorkingHypothesis] = Field(min_length=2, max_length=4)
    query_representation: QueryRepresentation

    meaning_candidates: list[RouteCandidate] = Field(default_factory=list)
    structure_candidates: list[RouteCandidate] = Field(default_factory=list)
    candidate_pool: list[PoolCandidate] = Field(default_factory=list)

    # The spec asks for 3–5 final perspectives; TECHNICAL-DESIGN/RETRIEVAL v0.2 allow 2–3.
    # The contract records any size up to 5; the target size is an open M2.2 decision.
    final_cards: list[FinalCard] = Field(default_factory=list, max_length=5)

    card_evaluations: list[CardEvaluation] = Field(default_factory=list)
    set_evaluation: SetEvaluation | None = None
    failures: list[FailureClassification] = Field(default_factory=list)

    # M2.2: full candidate-retrieval record (query → Q0 / Q1 / STRUCTURE → union).
    candidate_retrieval: CandidateRetrievalResult | None = None

    @model_validator(mode="after")
    def _invariants(self):
        ids = (
            [c.fragment_id for c in self.meaning_candidates]
            + [c.fragment_id for c in self.structure_candidates]
            + [c.fragment_id for c in self.candidate_pool]
            + [c.fragment_id for c in self.final_cards]
            + [c.fragment_id for c in self.card_evaluations]
        )
        leaked = sorted(set(ids) & UNRESOLVED_IDS)
        if leaked:
            raise ValueError(f"unresolved Fragment in trace: {leaked}")
        if any(c.route != "MEANING" for c in self.meaning_candidates):
            raise ValueError("meaning_candidates must come from the MEANING route")
        if any(c.route != "STRUCTURE" for c in self.structure_candidates):
            raise ValueError("structure_candidates must come from the STRUCTURE route")
        finals = [c.fragment_id for c in self.final_cards]
        if len(finals) != len(set(finals)):
            raise ValueError("final_cards contain duplicates")
        if self.candidate_pool:
            pool = {c.fragment_id for c in self.candidate_pool if not c.excluded}
            missing = sorted(set(finals) - pool)
            if missing:
                raise ValueError(f"final cards not in the non-excluded candidate pool: {missing}")
        cr = self.candidate_retrieval
        if cr is not None:
            prov = cr.query.provenance
            if prov.origin == "benchmark_adapter" and prov.benchmark_item_id != self.item_id:
                raise ValueError("candidate_retrieval query belongs to another benchmark item")
            if self.candidate_pool and {c.fragment_id for c in self.candidate_pool} != {c.card_id for c in cr.candidate_union}:
                raise ValueError("candidate_pool must mirror candidate_retrieval.candidate_union")
        return self

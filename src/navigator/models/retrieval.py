"""Candidate-retrieval result contracts (M2.2).

Corresponds to the recall part of the TECHNICAL-DESIGN trace (§49): per-route
candidate id / similarity / position, then the union with ``found_by`` and the
separate route signals. There is deliberately no combined score (D07).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_serializer, model_validator

from navigator.models.query import QueryRepresentation
from navigator.models.vocabularies import UNRESOLVED_IDS

NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]
FragmentId = Annotated[str, Field(pattern=r"^C\d{4}$")]

CANDIDATE_RETRIEVAL_VERSION = "candidate-retrieval/0.1.0"
DEFAULT_TOP_K = 15


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RepresentationRef(_Strict):
    version: NonEmptyStr
    text: StrictStr
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class SimilarityHit(_Strict):
    card_id: FragmentId
    rank: int = Field(ge=1)
    cosine: float


class EmbeddingRoute(_Strict):
    route: Literal["Q0_QUESTION_ONLY_CONTROL", "Q1_MEANING"]
    query: RepresentationRef
    card_representation_version: NonEmptyStr
    top_k: int = Field(ge=1)
    hits: list[SimilarityHit]


class StructureHit(_Strict):
    card_id: FragmentId
    rank: int = Field(ge=1)
    tension_overlap: int = Field(ge=0)
    matched_tensions: list[NonEmptyStr]
    coordinate_overlap: int = Field(ge=0)
    matched_coordinates: list[NonEmptyStr]
    operation: NonEmptyStr | None = None  # logged only; never scored in M2.2


class StructureRoute(_Strict):
    route: Literal["STRUCTURE"] = "STRUCTURE"
    ranking_rule: NonEmptyStr
    query_coordinates: list[NonEmptyStr]
    query_canonical_tensions: list[NonEmptyStr]
    top_k: int = Field(ge=1)
    matching_cards: int = Field(ge=0)
    tied_at_cutoff: int = Field(ge=0)
    hits: list[StructureHit]


class UnionCandidate(_Strict):
    card_id: FragmentId
    found_by: list[Literal["Q1_MEANING", "STRUCTURE"]] = Field(min_length=1)
    meaning_rank: int | None = None
    meaning_score: float | None = None
    structure_rank: int | None = None
    coordinate_overlap: int | None = None
    matched_coordinates: list[NonEmptyStr] | None = None
    tension_overlap: int | None = None
    matched_tensions: list[NonEmptyStr] | None = None
    operation: NonEmptyStr | None = None


class CandidateRetrievalResult(_Strict):
    version: Literal["candidate-retrieval/0.1.0"] = CANDIDATE_RETRIEVAL_VERSION
    query: QueryRepresentation
    embedding_config: dict
    corpus_version: NonEmptyStr | None = None
    retrieval_universe_size: int
    q0_control: EmbeddingRoute
    q1_meaning: EmbeddingRoute
    structure: StructureRoute
    union_rule: NonEmptyStr
    candidate_union: list[UnionCandidate]
    # temporary MVP retrieval diversity guardrail record (final corpus only); absent from dumps when off, so legacy
    # retrieval traces stay byte-identical
    diversity_guardrail: dict | None = None

    @model_serializer(mode="wrap")
    def _drop_absent_guardrail(self, handler):
        data = handler(self)
        if data.get("diversity_guardrail") is None:
            data.pop("diversity_guardrail", None)
        return data

    @model_validator(mode="after")
    def _invariants(self):
        ids = (
            [h.card_id for h in self.q0_control.hits]
            + [h.card_id for h in self.q1_meaning.hits]
            + [h.card_id for h in self.structure.hits]
            + [c.card_id for c in self.candidate_union]
        )
        from navigator.corpus.policy import excluded_ids_for  # per corpus: legacy guard / final package exclusions

        leaked = sorted(set(ids) & excluded_ids_for(self.corpus_version))
        if leaked:
            raise ValueError(f"unresolved Fragment in retrieval result: {leaked}")
        union = {c.card_id for c in self.candidate_union}
        expected = {h.card_id for h in self.q1_meaning.hits} | {h.card_id for h in self.structure.hits}
        if union != expected:
            raise ValueError("candidate_union must equal union(Q1 hits, STRUCTURE hits); Q0 is excluded")
        return self

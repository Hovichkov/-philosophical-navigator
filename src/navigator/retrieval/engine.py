"""Baseline candidate retriever (M2.2).

confirmed question → QueryRepresentation → Q0 (control) / Q1 (MEANING) / STRUCTURE → union.
Only the 113 retrieval-eligible Fragments are indexed. This is candidate
retrieval, not final selection: no composition, reranking or combined score.
"""

from __future__ import annotations

from pathlib import Path

from navigator.corpus.readiness import retrieval_universe
from navigator.embeddings.cache import DEFAULT_CACHE_ROOT, EmbeddingCache
from navigator.models.fragment import Fragment
from navigator.models.query import QueryRepresentation
from navigator.models.retrieval import (
    DEFAULT_TOP_K,
    CandidateRetrievalResult,
    EmbeddingRoute,
    RepresentationRef,
    StructureRoute,
)
from navigator.corpus.final_corpus import FINAL_CORPUS_VERSION
from navigator.corpus.policy import excluded_ids_for
from navigator.providers.embeddings import EmbeddingClient
from navigator.representations.meaning import (
    MEANING_CARD_DOC_VERSION,
    MEANING_SPEC_ID,
    Representation,
    meaning_card_documents,
    q0_representation,
    q1_representation,
)
from navigator.retrieval.diversity import SourceDiversityGuardrail
from navigator.retrieval.routes import (
    STRUCTURE_RANKING_RULE,
    UNION_RULE,
    candidate_union,
    cosine_rank,
    structure_rank,
)


def _ref(rep: Representation) -> RepresentationRef:
    return RepresentationRef(version=rep.version, text=rep.text, sha256=rep.sha256)


class CandidateRetriever:
    def __init__(
        self,
        fragments: list[Fragment],
        client: EmbeddingClient,
        cache_root: Path = DEFAULT_CACHE_ROOT,
        top_k: int = DEFAULT_TOP_K,
        persist_cache: bool = True,
        corpus_version: str | None = None,
        card_docs: list[Representation] | None = None,
        diversity_guardrail: SourceDiversityGuardrail | None = None,
    ):
        """``card_docs``: MEANING card documents to use instead of the meaning-v2 ones (the final-corpus retrieval
        experiment, navigator.representations.final_meaning); they must cover exactly the retrieval universe.
        ``diversity_guardrail``: temporary MVP retrieval diversity guardrail (final corpus only, None = off): a source
        cap applied to the Q1 hits AFTER the unchanged cosine ranking (navigator.retrieval.diversity)."""
        self.universe = sorted(retrieval_universe(fragments), key=lambda f: f.id)
        if corpus_version is None and self.universe and all(
                f.technical.corpus_status == "final_2026_10_07" for f in self.universe):
            corpus_version = FINAL_CORPUS_VERSION  # a final-corpus snapshot is governed by its own package
        if {f.id for f in self.universe} & excluded_ids_for(corpus_version):
            raise ValueError("unresolved Fragment in retrieval universe")
        self.client = client
        self.top_k = top_k
        self.persist_cache = persist_cache
        self.corpus_version = corpus_version
        self.card_docs = sorted(card_docs, key=lambda d: d.key) if card_docs is not None else meaning_card_documents(fragments)
        if [d.key for d in self.card_docs] != [f.id for f in self.universe]:
            raise ValueError("MEANING card documents must cover exactly the retrieval universe")
        self.card_ids = [d.key for d in self.card_docs]
        # namespaces are per MEANING spec: vectors of different specs never share a store
        self.card_cache = EmbeddingCache(cache_root, client.config, f"meaning-cards__{MEANING_SPEC_ID}")
        self.query_cache = EmbeddingCache(cache_root, client.config, f"queries__{MEANING_SPEC_ID}")
        self.card_vectors = self.card_cache.embed(self.card_docs, client, persist=persist_cache)
        self.operations = {f.id: f.philosophical_operation for f in self.universe}
        self.diversity_guardrail = diversity_guardrail
        if diversity_guardrail is not None and diversity_guardrail.pool_size != top_k:
            raise ValueError("the diversity guardrail pool size must equal top_k")
        self.source_of = {f.id: f.author or "" for f in self.universe}

    def retrieve(self, query: QueryRepresentation, query_id: str) -> CandidateRetrievalResult:
        q0 = q0_representation(query, query_id)
        q1 = q1_representation(query, query_id)
        vectors = self.query_cache.embed([q0, q1], self.client, persist=self.persist_cache)
        q0_hits = cosine_rank(vectors[0], self.card_ids, self.card_vectors, self.top_k)
        guardrail_record = None
        if self.diversity_guardrail is None:
            q1_hits = cosine_rank(vectors[1], self.card_ids, self.card_vectors, self.top_k)
        else:  # temporary MVP retrieval diversity guardrail: same cosine ranking, source cap on top
            ranked = cosine_rank(vectors[1], self.card_ids, self.card_vectors, self.diversity_guardrail.scan_limit)
            q1_hits, guardrail_record = self.diversity_guardrail.apply(ranked, self.source_of)
        s_hits, matching, tied = structure_rank(self.universe, query.coordinates, query.canonical_tensions, self.top_k)
        return CandidateRetrievalResult(
            query=query,
            embedding_config=self.client.config.public_dict(),
            corpus_version=self.corpus_version,
            retrieval_universe_size=len(self.universe),
            q0_control=EmbeddingRoute(
                route="Q0_QUESTION_ONLY_CONTROL", query=_ref(q0),
                card_representation_version=MEANING_CARD_DOC_VERSION, top_k=self.top_k, hits=q0_hits,
            ),
            q1_meaning=EmbeddingRoute(
                route="Q1_MEANING", query=_ref(q1),
                card_representation_version=MEANING_CARD_DOC_VERSION, top_k=self.top_k, hits=q1_hits,
            ),
            structure=StructureRoute(
                ranking_rule=STRUCTURE_RANKING_RULE,
                query_coordinates=query.coordinates,
                query_canonical_tensions=query.canonical_tensions,
                top_k=self.top_k,
                matching_cards=matching,
                tied_at_cutoff=tied,
                hits=s_hits,
            ),
            union_rule=UNION_RULE,
            candidate_union=candidate_union(q1_hits, s_hits, self.operations),
            diversity_guardrail=guardrail_record,
        )

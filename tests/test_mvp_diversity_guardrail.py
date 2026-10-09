"""Temporary MVP guardrails (2026-10-08), final corpus only — NOT the retrieval architecture.

1. Candidate pool: at most 3 cards per source (CSV ``author``) among the 15, taken top-down from the UNCHANGED cosine
   ranking (no re-ranking, no padding below the scan limit).
2. Final answer: at most 1 card per author; the selector is asked once to choose another author instead, on the last
   attempt the duplicate is dropped; one strong card is a valid final-corpus answer.
Legacy / compact behaviour must not change. Fake embeddings: structure and policy only, not retrieval quality."""

from __future__ import annotations

from collections import Counter

import pytest

import test_m3_3_1_human_language as base
from navigator.composition.composer import (
    FINAL_OUTPUT_SCHEMA,
    OUTPUT_SCHEMA,
    build_package,
    check_selection,
    compose,
    one_card_per_author,
)
from navigator.corpus.final_corpus import FINAL_CORPUS_VERSION, final_snapshot_fragments, load_final_active
from navigator.models.query import UserContext
from navigator.models.retrieval import SimilarityHit
from navigator.providers.fake import FakeEmbeddingClient
from navigator.representations.final_meaning import mode_snapshot
from navigator.retrieval.diversity import GUARDRAIL_VERSION, SourceDiversityGuardrail
from navigator.retrieval.engine import CandidateRetriever
from test_final_corpus_retrieval import query


@pytest.fixture(scope="module")
def final():
    return final_snapshot_fragments(load_final_active())


def hits(ids):
    return [SimilarityHit(card_id=c, rank=i + 1, cosine=1 - i / 100) for i, c in enumerate(ids)]


# ------------------------------------------------------------------ 1. the filter itself


def test_filter_keeps_original_order_and_ranks_and_caps_every_source_alike():
    ids = [f"C{n:04d}" for n in range(1, 31)]
    source = {c: ("A" if n < 10 else "B" if n < 14 else f"S{n}") for n, c in enumerate(ids)}
    kept, rec = SourceDiversityGuardrail().apply(hits(ids), source)
    assert len(kept) == 15 and rec["pool_filled"]
    assert [h.rank for h in kept] == sorted(h.rank for h in kept)  # not re-ranked
    assert all(h.cosine == 1 - (h.rank - 1) / 100 for h in kept)  # scores untouched
    assert max(Counter(source[h.card_id] for h in kept).values()) == 3  # same cap for A and B
    assert kept[0].card_id == ids[0]  # the semantic top always stays
    assert {s["source"] for s in rec["skipped"]} == {"A", "B"} and rec["version"] == GUARDRAIL_VERSION
    assert "temporary MVP" in rec["status"]


def test_filter_never_pads_below_the_scan_limit():
    ids = [f"C{n:04d}" for n in range(1, 61)]
    source = {c: ("A" if n < 50 else f"S{n}") for n, c in enumerate(ids)}  # only 3 + 0 others within rank 45
    kept, rec = SourceDiversityGuardrail().apply(hits(ids), source)
    assert len(kept) == 3 and not rec["pool_filled"]  # controlled fallback: a smaller pool, cap not relaxed
    assert rec["deepest_accepted_rank"] == 3


# ------------------------------------------------------------------ 2. inside retrieval (final corpus only)


@pytest.mark.parametrize("mode", ["A", "B"])
def test_final_retrieval_pool_is_capped_and_cosine_ranking_unchanged(mode, final, tmp_path):
    snap = mode_snapshot(final, mode)
    plain = CandidateRetriever(snap.fragments, FakeEmbeddingClient(), cache_root=tmp_path, card_docs=snap.docs)
    guarded = CandidateRetriever(snap.fragments, FakeEmbeddingClient(), cache_root=tmp_path, card_docs=snap.docs,
                                 diversity_guardrail=SourceDiversityGuardrail())
    a, b = plain.retrieve(query(), "t"), guarded.retrieve(query(), "t")
    author = {f.id: f.author for f in final}
    full = plain.retrieve(query(), "t")  # same query vector → same ranking as the guarded scan
    deep = {h.card_id: h for h in CandidateRetriever(snap.fragments, FakeEmbeddingClient(), cache_root=tmp_path,
                                                     card_docs=snap.docs, top_k=45).retrieve(query(), "t").q1_meaning.hits}
    assert len(b.q1_meaning.hits) == 15 and b.q1_meaning.top_k == 15
    assert max(Counter(author[h.card_id] for h in b.q1_meaning.hits).values()) <= 3
    for h in b.q1_meaning.hits:  # every accepted hit is the original hit (rank and cosine unchanged)
        assert deep[h.card_id] == h
    assert b.q1_meaning.hits[0] == a.q1_meaning.hits[0] == full.q1_meaning.hits[0]
    assert {c.card_id for c in b.candidate_union} == {h.card_id for h in b.q1_meaning.hits}
    assert b.q0_control == a.q0_control  # the control route is untouched
    rec = b.model_dump()["diversity_guardrail"]
    assert rec["original_top"] == [h.card_id for h in a.q1_meaning.hits]
    assert "diversity_guardrail" not in a.model_dump() and "diversity_guardrail" not in a.model_dump_json()


def test_legacy_retrieval_dump_has_no_guardrail_key(tmp_path):
    frags = base.load_test_fragments()
    r = CandidateRetriever(frags, FakeEmbeddingClient(), cache_root=tmp_path)
    assert "diversity_guardrail" not in r.retrieve(query(), "t").model_dump(mode="json")


# ------------------------------------------------------------------ 3. final answer: one card per author


EPICTETUS = ("C0281", "C0320")  # Беседы I.11, III.18
OTHERS = ("C0642", "C0599")  # Лунь юй 6.18, Еккл 9:1–3


def final_package(final, tmp_path):
    snap = mode_snapshot(final, "B")
    r = CandidateRetriever(snap.fragments, FakeEmbeddingClient(), cache_root=tmp_path, card_docs=snap.docs)
    q = query().model_copy(update={"context": UserContext(circumstance="Отношения с близким человеком",
                                                          narrative="хочу быть с нею, а она не хочет")})
    dump = r.retrieve(q, "t").model_dump(mode="json")
    chosen = [*EPICTETUS, *OTHERS]
    union = [u for u in dump["candidate_union"] if u["card_id"] not in chosen][: 15 - len(chosen)]
    for cid, u in zip(chosen, dump["candidate_union"][: len(chosen)]):
        union.insert(0, {**u, "card_id": cid})
    dump["candidate_union"] = union
    dump["q1_meaning"]["hits"][0]["card_id"] = EPICTETUS[0]
    pkg = build_package({"item_id": "t", "run_id": "t", "candidate_retrieval": dump}, final)
    assert pkg["corpus_version"] == FINAL_CORPUS_VERSION
    return pkg


class PairSelector:
    """Returns the scripted selections in turn (selection-only format)."""
    name, model = "scripted", None

    def __init__(self, *selections):
        self.selections, self.calls, self.feedback = list(selections), 0, []

    def complete(self, pkg, feedback=None):
        self.feedback.append(feedback)
        ids = self.selections[min(self.calls, len(self.selections) - 1)]
        self.calls += 1
        persp = [{"card_id": i, "role": "ход", "distinction": f"Помогает различить одно и другое ({k}).",
                  "perspective_effect": f"человек видит свой вопрос иначе, способ {k}",
                  "source_point": "источник говорит простую вещь", "user_point": "это касается вопроса",
                  "why_selected": "ясное различение"} for k, i in enumerate(ids)]
        top = pkg["q1_top_card_id"]
        return {"perspectives": persp, "count_reason": "r",
                "q1_top": {"card_id": top, "decision": "selected" if top in ids else "rejected", "reason": "r"}}, {}


def test_second_card_of_the_same_author_is_replaced_by_another_author(final, tmp_path):
    sel = PairSelector(list(EPICTETUS), [EPICTETUS[0], OTHERS[0]])
    res = compose(final_package(final, tmp_path), final, sel, max_attempts=3, writer=base.Writer())
    assert [p.card_id for p in res.perspectives] == [EPICTETUS[0], OTHERS[0]] and sel.calls == 2
    assert "двух карточек одного автора" in sel.feedback[1] and "Эпиктет" in sel.feedback[1]


def test_without_a_good_alternative_one_strong_card_is_the_answer(final, tmp_path):
    sel = PairSelector(list(EPICTETUS))  # insists on the same author every time
    res = compose(final_package(final, tmp_path), final, sel, max_attempts=2, writer=base.Writer())
    assert [p.card_id for p in res.perspectives] == [EPICTETUS[0]]  # dropped, not padded
    assert any(r.card_id == EPICTETUS[1] and r.reason.startswith("тот же автор") for r in res.rejected)
    assert res.meta.usage["writer"]["same_author_dropped"][0]["card_id"] == EPICTETUS[1]


def test_legacy_selection_keeps_two_to_three_and_no_author_rule(final):
    legacy_pkg = {"candidates": [{"card_id": c} for c in (*EPICTETUS, *OTHERS)]}
    one = {"perspectives": [{"card_id": EPICTETUS[0], "perspective_effect": "e", "distinction": "Помогает различить А и Б",
                             "role": "r", "why_selected": "w"}]}
    with pytest.raises(ValueError, match="select 2–3"):
        check_selection(legacy_pkg, one)
    check_selection({**legacy_pkg, "corpus_version": FINAL_CORPUS_VERSION}, one)  # final: one card is valid
    by_id = {f.id: f for f in final}
    pair = [{"card_id": c} for c in EPICTETUS]
    assert one_card_per_author(legacy_pkg, pair, by_id, resolve=False) == (pair, [])
    assert OUTPUT_SCHEMA["properties"]["perspectives"]["minItems"] == 2
    assert FINAL_OUTPUT_SCHEMA["properties"]["perspectives"]["minItems"] == 1


# ------------------------------------------------------------------ 4. candidate pool size (2026-10-09)


@pytest.mark.parametrize("k", [15, 20, 25])
def test_pool_size_keeps_the_source_cap_and_the_original_ranking(k, final, tmp_path):
    snap = mode_snapshot(final, "B")
    r = CandidateRetriever(snap.fragments, FakeEmbeddingClient(), cache_root=tmp_path, card_docs=snap.docs, top_k=k,
                           diversity_guardrail=SourceDiversityGuardrail(pool_size=k, scan_limit=3 * k))
    hits = r.retrieve(query(), "t").q1_meaning.hits
    author = {f.id: f.author for f in final}
    assert len(hits) == k and max(Counter(author[h.card_id] for h in hits).values()) <= 3
    assert [h.rank for h in hits] == sorted(h.rank for h in hits)
    small = CandidateRetriever(snap.fragments, FakeEmbeddingClient(), cache_root=tmp_path, card_docs=snap.docs, top_k=15,
                               diversity_guardrail=SourceDiversityGuardrail()).retrieve(query(), "t").q1_meaning.hits
    assert [h.card_id for h in hits[:15]] == [h.card_id for h in small]  # a bigger pool only extends the old one


def test_final_pool_default_is_20_and_15_remains_available():
    import inspect

    from navigator.prototype import server

    assert server.FINAL_POOL_SIZE == 20 and 15 in server.POOL_SIZES
    assert inspect.signature(server.build_final_services).parameters["pool_size"].default == 20

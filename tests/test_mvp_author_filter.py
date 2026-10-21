"""Temporary final-corpus author exclusion; fake embeddings and scripted composition only."""

from __future__ import annotations

import pytest

import test_m3_3_1_human_language as base
from navigator.composition.composer import build_package, compose
from navigator.corpus.final_corpus import FINAL_CORPUS_VERSION, final_snapshot_fragments, load_final_active
from navigator.prototype import server
from navigator.providers.fake import FakeEmbeddingClient
from navigator.representations.final_meaning import mode_snapshot
from navigator.representations.retrieval_layer import load_retrieval_layer
from navigator.retrieval.diversity import SourceDiversityGuardrail
from navigator.retrieval.engine import CandidateRetriever
from test_final_corpus_retrieval import query


@pytest.fixture(scope="module")
def final():
    return final_snapshot_fragments(load_final_active())


def test_default_filter_preserves_all_cards_and_epictetus():
    final = final_snapshot_fragments(load_final_active())
    assert server.filter_excluded_author(final, None) is final
    assert any(f.author == "Эпиктет" for f in final)


def test_excluded_author_is_removed_before_retrieval_pool_and_answer(final, tmp_path):
    filtered = server.filter_excluded_author(final, "epictetus")
    assert filtered and all(f.author != "Эпиктет" for f in filtered)
    assert len(filtered) < len(final)

    layer = load_retrieval_layer("v1-block1", known_ids={f.id for f in filtered})
    snap = mode_snapshot(filtered, "B", retrieval_layer=layer)
    retriever = CandidateRetriever(
        snap.fragments,
        FakeEmbeddingClient(),
        cache_root=tmp_path,
        corpus_version=FINAL_CORPUS_VERSION,
        card_docs=snap.docs,
        top_k=20,
        diversity_guardrail=SourceDiversityGuardrail(pool_size=20, scan_limit=60),
    )
    q = query()
    q = q.model_copy(update={
        "context": q.context.model_copy(update={
            "narrative": "Я переживаю перемены и пытаюсь понять, что зависит от моего решения."
        })
    })
    retrieval = retriever.retrieve(q, "exclude-epictetus")
    candidate_ids = {c.card_id for c in retrieval.candidate_union}
    assert candidate_ids and candidate_ids <= {f.id for f in filtered}
    assert any(retriever.source_of[cid] != "Эпиктет" for cid in candidate_ids)

    package = build_package({
        "item_id": "exclude-epictetus",
        "run_id": "exclude-epictetus",
        "candidate_retrieval": retrieval.model_dump(mode="json"),
    }, filtered)
    assert all(c["card_id"] in {f.id for f in filtered} for c in package["candidates"])
    result = compose(package, filtered, base.Selector(n=2), max_attempts=1, writer=base.Writer())
    assert result.perspectives
    assert all(next(f for f in filtered if f.id == p.card_id).author != "Эпиктет"
               for p in result.perspectives)


def test_cli_exposes_filter_without_changing_default(monkeypatch):
    calls = []
    monkeypatch.setattr(server, "serve", lambda **kwargs: calls.append(kwargs))
    from navigator.cli import main

    main(["prototype", "--corpus", "final", "--final-mode", "B"])
    assert calls[-1]["exclude_author"] is None
    main(["prototype", "--corpus", "final", "--final-mode", "B", "--exclude-author", "epictetus"])
    assert calls[-1]["exclude_author"] == "epictetus"


def test_unknown_exclusion_is_rejected():
    final = final_snapshot_fragments(load_final_active())
    with pytest.raises(ValueError, match="unknown excluded author"):
        server.filter_excluded_author(final, "unknown")


@pytest.mark.parametrize("mode", ["A", "B", "C"])
def test_mvp_default_pair_exclusion_reaches_pool_package_and_answer(final, tmp_path, mode):
    policy = server.effective_author_filter("final", None)
    assert policy == "epictetus-epicurus"
    filtered = server.filter_excluded_author(final, policy)
    banned = {"Эпиктет", "Эпикур"}
    assert len(filtered) == len(final) - sum(f.author in banned for f in final)
    assert len(filtered) == 735
    assert all(f.author not in banned for f in filtered)
    assert any(f.author in banned for f in final)  # source material stays intact
    layer = load_retrieval_layer("v1-block1", known_ids={f.id for f in filtered}) if mode == "B" else None
    snap = mode_snapshot(filtered, mode, retrieval_layer=layer)
    retriever = CandidateRetriever(snap.fragments, FakeEmbeddingClient(), cache_root=tmp_path,
        corpus_version=FINAL_CORPUS_VERSION, card_docs=snap.docs, top_k=20,
        diversity_guardrail=SourceDiversityGuardrail(pool_size=20, scan_limit=60))
    q = query()
    q = q.model_copy(update={"context": q.context.model_copy(update={
        "narrative": "Я переживаю перемены и пытаюсь понять, что зависит от моего решения."})})
    retrieval = retriever.retrieve(q, "mvp-no-pair")
    assert retrieval.candidate_union
    assert all(retriever.source_of[c.card_id] not in banned for c in retrieval.candidate_union)
    package = build_package({"item_id": "mvp-no-pair", "run_id": "mvp-no-pair",
        "candidate_retrieval": retrieval.model_dump(mode="json")}, filtered)
    result = compose(package, filtered, base.Selector(n=2), max_attempts=1, writer=base.Writer())
    by = {f.id: f for f in final}
    assert result.perspectives
    assert all(by[p.card_id].author not in banned for p in result.perspectives)


def test_explicit_comparison_and_legacy_defaults(final):
    assert server.effective_author_filter("compact", None) is None
    assert server.effective_author_filter("final", "none") == "none"
    assert server.filter_excluded_author(final, "none") == final
    assert server.effective_author_filter("final", "epictetus") == "epictetus"


def test_cli_accepts_pair_and_comparison(monkeypatch):
    calls = []
    monkeypatch.setattr(server, "serve", lambda **kwargs: calls.append(kwargs))
    from navigator.cli import main
    for option in ("epictetus-epicurus", "none"):
        main(["prototype", "--corpus", "final", "--exclude-author", option])
        assert calls[-1]["exclude_author"] == option


def test_real_service_defaults_filter_before_lazy_retriever():
    svc = server.build_final_services("unused-model", "B", "v1-block1")
    assert len(svc.fragments) == 735
    assert all(f.author not in {"Эпиктет", "Эпикур"} for f in svc.fragments)
    comparison = server.build_final_services("unused-model", "B", "v1-block1", exclude_author="none")
    assert len(comparison.fragments) == 967

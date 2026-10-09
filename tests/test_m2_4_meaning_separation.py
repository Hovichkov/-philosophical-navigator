"""M2.4 — MEANING separation: TAXONOMY vocabulary belongs to STRUCTURE only."""

from __future__ import annotations

from corpus_snapshot import blocked_ids, expected_eligible, legacy_only, load_test_fragments

import json
from pathlib import Path

import pytest

from navigator.benchmark.adapter import case_query
from navigator.corpus.readiness import retrieval_universe
from navigator.embeddings.cache import cache_dir
from navigator.models.benchmark import Benchmark
from navigator.models.fragment import Fragment
from navigator.models.vocabularies import COORDINATES, TENSIONS, UNRESOLVED_IDS
from navigator.providers.embeddings import LOCAL_EMBEDDING_CONFIG
from navigator.providers.fake import FakeEmbeddingClient
from navigator.representations.meaning import (
    MEANING_CARD_DOC_VERSION,
    MEANING_SPEC_ID,
    Q1_QUERY_VERSION,
    meaning_card_documents,
    q0_text,
    q1_text,
)
from navigator.retrieval.engine import CandidateRetriever
from navigator.retrieval.routes import structure_rank

ROOT = Path(__file__).resolve().parents[1]
M22_RUN = ROOT / "reports/benchmark-runs/m2_2-baseline-20260927T102714Z/traces.jsonl"


@pytest.fixture(scope="module")
def fragments():
    return load_test_fragments()


@pytest.fixture(scope="module")
def bench():
    return Benchmark.model_validate(json.loads((ROOT / "data/eval/benchmarks/m2_1-retrieval-benchmark-v0.1.json").read_text(encoding="utf-8")))


def test_versions_bumped():
    assert MEANING_CARD_DOC_VERSION == "meaning-card-doc/2.0" and Q1_QUERY_VERSION == "q1-meaning-query/2.0"
    assert MEANING_SPEC_ID == "meaning-v2"


def test_card_documents_have_no_coordinates_or_tensions(fragments):
    for d in meaning_card_documents(fragments):
        assert "Координаты:" not in d.text and "Напряжения:" not in d.text and "↔" not in d.text, d.key


def test_card_documents_contain_perspective_and_questions(fragments):
    by_id = {f.id: f for f in fragments}
    for d in meaning_card_documents(fragments):
        f = by_id[d.key]
        assert not f.perspective or f"Перспектива: {f.perspective}" in d.text
        for q in f.philosophical_questions or []:
            assert f"- {q}" in d.text


def test_q1_has_question_and_hypotheses_but_no_taxonomy(bench):
    for case in bench.cases:
        q = case_query(case)
        text = q1_text(q)
        assert f"Вопрос: {q.confirmed_question}" in text
        assert all(f"- {h}" in text for h in q.working_hypotheses)
        assert "↔" not in text and "напряжения" not in text.lower()
        for t in [*q.canonical_tensions, *q.free_tensions]:
            assert t not in text
        assert not any(line.startswith("Координаты") for line in text.split("\n"))
        # coordinates remain in the query representation (for STRUCTURE / trace)
        assert set(q.coordinates) <= COORDINATES and set(q.canonical_tensions) <= TENSIONS


def test_q0_unchanged(bench):
    q = case_query(bench.cases[0])
    assert q0_text(q) == q.confirmed_question


@legacy_only
@pytest.mark.skipif(not M22_RUN.exists(), reason="M2.2 run not available")
def test_structure_identical_to_m2_2(fragments, bench):
    universe = sorted(retrieval_universe(fragments), key=lambda f: f.id)
    old = {json.loads(l)["item_id"]: json.loads(l)["candidate_retrieval"]["structure"] for l in M22_RUN.read_text(encoding="utf-8").splitlines()}
    for case in bench.cases:
        q = case_query(case)
        hits, matching, tied = structure_rank(universe, q.coordinates, q.canonical_tensions, 15)
        assert [h.model_dump() for h in hits] == old[case.id]["hits"]
        assert (matching, tied) == (old[case.id]["matching_cards"], old[case.id]["tied_at_cutoff"])


def test_cache_namespace_is_spec_specific(fragments, tmp_path):
    r = CandidateRetriever(fragments, FakeEmbeddingClient(), cache_root=tmp_path)
    assert r.card_cache.dir.name == f"meaning-cards__{MEANING_SPEC_ID}"
    assert r.query_cache.dir.name == f"queries__{MEANING_SPEC_ID}"
    assert cache_dir(tmp_path, LOCAL_EMBEDDING_CONFIG, "meaning-cards") != cache_dir(tmp_path, LOCAL_EMBEDDING_CONFIG, f"meaning-cards__{MEANING_SPEC_ID}")


def test_unresolved_excluded_and_source_disabled(fragments, bench, tmp_path):
    r = CandidateRetriever(fragments, FakeEmbeddingClient(), cache_root=tmp_path)
    assert len(r.card_ids) == expected_eligible() and not set(r.card_ids) & blocked_ids()
    res = r.retrieve(case_query(bench.cases[0]), "B01")
    assert not {h.card_id for h in res.q1_meaning.hits} & blocked_ids()
    assert res.q1_meaning.card_representation_version == MEANING_CARD_DOC_VERSION
    manifest = json.loads((ROOT / "data/corpus/launch-manifest.json").read_text(encoding="utf-8"))
    assert manifest["routes"]["SOURCE"] == "disabled_pending_full_fragment_text"


@legacy_only
def test_compare_and_samples_report_raw_results(fragments, bench, tmp_path):
    from navigator.benchmark.compare import compare_runs, render_samples
    from navigator.benchmark.runner import trace_for_case

    r = CandidateRetriever(fragments, FakeEmbeddingClient(), cache_root=tmp_path)
    traces = [trace_for_case("t", bench, c.id, r.retrieve(case_query(c), c.id)).model_dump(mode="json") for c in bench.cases]
    cmp = compare_runs(traces, traces, fragments)
    assert cmp["Q1"]["identical"] and cmp["STRUCTURE"]["byte_identical_route_records"]
    md = render_samples(traces, fragments, {c.id: c for c in bench.cases}, "t")
    assert md.count("## B") == 20 and "Q1 top-10" in md and "STRUCTURE top-5" in md
    first = traces[0]["candidate_retrieval"]["q1_meaning"]["hits"][0]
    assert f"| 1 | {first['card_id']}" in md  # order preserved as retrieved

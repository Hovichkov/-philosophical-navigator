"""M2.3 diagnostic machinery. Diagnostics must not change production behaviour."""

from __future__ import annotations

from corpus_snapshot import blocked_ids, expected_eligible, legacy_only, load_test_fragments

import json
from pathlib import Path

import pytest

from navigator.benchmark.adapter import case_query
from navigator.benchmark.runner import trace_for_case
from navigator.corpus.readiness import retrieval_universe
from navigator.diagnostics.retrieval_diagnosis import (
    DOC_VARIANTS,
    build_doc_variant,
    gini,
    query_variants,
    ranking_stats,
    run_diagnosis,
    structural_share,
    template_share,
)
from navigator.models.benchmark import Benchmark
from navigator.models.fragment import Fragment
from navigator.providers.fake import FakeEmbeddingClient
from navigator.representations.meaning import meaning_card_documents, meaning_card_text_v1, q0_text, q1_text_v1
from navigator.retrieval.engine import CandidateRetriever

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def fragments():
    return load_test_fragments()


@pytest.fixture(scope="module")
def bench():
    return Benchmark.model_validate(json.loads((ROOT / "data/eval/benchmarks/m2_1-retrieval-benchmark-v0.1.json").read_text(encoding="utf-8")))


def variant(vid):
    return next(v for v in DOC_VARIANTS if v.id == vid)


def test_full_variant_equals_m2_2_document(fragments):
    # M2.3 diagnosed the M2.2 baseline, so D_full is the legacy M2.2 document
    universe = retrieval_universe(fragments)
    legacy = {f.id: meaning_card_text_v1(f) for f in universe}
    assert build_doc_variant(variant("D_full"), universe) == legacy


def test_variants_only_use_meaning_fields(fragments):
    universe = retrieval_universe(fragments)
    by_id = {f.id: f for f in universe}
    for v in DOC_VARIANTS:
        for cid, text in build_doc_variant(v, universe).items():
            f = by_id[cid]
            if f.thought:
                assert f.thought not in text
            assert "FINAL TEXTUAL PASS" not in text


@legacy_only
def test_field_variants_contain_expected_sections(fragments):
    universe = retrieval_universe(fragments)
    persp = build_doc_variant(variant("A_perspective"), universe)
    assert all(t.startswith("Перспектива:") and "Координаты:" not in t for t in persp.values())
    no_t = build_doc_variant(variant("E_full_no_tensions"), universe)
    assert all("Напряжения:" not in t for t in no_t.values())
    detempl = build_doc_variant(variant("F_full_detemplated"), universe)
    assert all("Рассмотреть ситуацию через операцию" not in t for t in detempl.values())


def test_query_variants_reproduce_production_queries(bench):
    q = case_query(bench.cases[0])
    qv = query_variants(q)
    assert qv["Q0_question_only"] == q0_text(q) and qv["Q1_full"] == q1_text_v1(q)
    assert "Смысловые напряжения" not in qv["QH_question_hypotheses"]
    assert "Рабочие интерпретации" not in qv["QT_question_tensions"]


def test_metrics():
    assert gini([1, 1, 1, 1]) == 0.0 and gini([0, 0, 0, 4]) == 0.75
    stats = ranking_stats({"B01": ["C1", "C2"], "B02": ["C1", "C3"]}, ["C1", "C2", "C3", "C4"], {"C1"},
                          baseline={"B01": ["C1", "C9"], "B02": ["C3", "C9"]}, focus="C1")
    assert stats["recovered_share"] == 0.5 and stats["unique_cards"] == 3 and stats["focus_frequency"] == 2
    assert stats["mean_overlap_with_baseline"] == 0.5 and stats["recovered_per_case"] == {"B01": 1, "B02": 1}
    assert structural_share("Перспектива: x\nКоординаты: желание") == round(len("Координаты: желание") / len("Перспектива: x\nКоординаты: желание"), 4)
    assert template_share("Перспектива: abc", set()) == 0.0


@legacy_only
def test_diagnosis_runs_with_fake_client_without_touching_production(fragments, bench, tmp_path):
    prod_before = {d.key: d.sha256 for d in meaning_card_documents(fragments)}
    client = FakeEmbeddingClient()
    retriever = CandidateRetriever(fragments, client, cache_root=tmp_path / "prod")
    traces = [trace_for_case("fake", bench, c.id, retriever.retrieve(case_query(c), c.id)).model_dump(mode="json")
              for c in bench.cases]
    res = run_diagnosis(fragments, bench, traces, client, tmp_path / "diag")
    assert set(res) >= {"baseline", "documents", "field_ablations", "query_ablations", "embedding_space", "c0056", "structure"}
    assert not any("prod" in str(p) for p in (tmp_path / "diag").rglob("*"))
    assert {d.key: d.sha256 for d in meaning_card_documents(fragments)} == prod_before

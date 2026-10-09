"""M2.2 — baseline candidate retrieval. No test performs a live API call."""

from __future__ import annotations

from corpus_snapshot import blocked_ids, expected_eligible, legacy_only, load_test_fragments

import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from navigator.benchmark.adapter import case_query, center_to_question, contrast_probe, split_tensions
from navigator.benchmark.runner import contrast_diagnostics, run_benchmark, trace_for_case, write_run
from navigator.embeddings.cache import EmbeddingCache, cache_dir
from navigator.models.benchmark import Benchmark, TensionRef
from navigator.models.fragment import Fragment
from navigator.models.query import QueryProvenance, QueryRepresentation, UserContext
from navigator.models.retrieval import CandidateRetrievalResult
from navigator.models.trace import BenchmarkRunTrace
from navigator.models.vocabularies import UNRESOLVED_IDS
from navigator.providers.embeddings import (
    BASELINE_EMBEDDING_CONFIG,
    EmbeddingClient,
    EmbeddingUnavailable,
    OpenAIEmbeddingClient,
)
from navigator.providers.fake import FakeEmbeddingClient
from navigator.representations.meaning import (
    MEANING_CARD_DOC_VERSION,
    Representation,
    meaning_card_documents,
    meaning_card_text,
    q0_text,
    q1_text,
)
from navigator.retrieval.engine import CandidateRetriever
from navigator.retrieval.routes import candidate_union, cosine_rank, structure_rank

from test_validator import corpus as synthetic_corpus

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/corpus/fragments.jsonl"
BENCH = ROOT / "data/eval/benchmarks/m2_1-retrieval-benchmark-v0.1.json"


@pytest.fixture(scope="module")
def fragments() -> list[Fragment]:
    return load_test_fragments()


@pytest.fixture(scope="module")
def bench() -> Benchmark:
    return Benchmark.model_validate(json.loads(BENCH.read_text(encoding="utf-8")))


@pytest.fixture()
def retriever(fragments, tmp_path) -> CandidateRetriever:
    return CandidateRetriever(fragments, FakeEmbeddingClient(), cache_root=tmp_path / "cache")


def prov(**kw) -> QueryProvenance:
    base = dict(origin="benchmark_adapter", confirmed_question_source="benchmark_center_proxy",
                interpretation_source="benchmark_expected_structure_proxy", benchmark_item_id="B01")
    base.update(kw)
    return QueryProvenance(**base)


def query(**kw) -> QueryRepresentation:
    base = dict(
        confirmed_question="Имею ли я право выбрать собственную жизнь?",
        context=UserContext(circumstance="семья", narrative="длинный рассказ про развод"),
        experiences=["вина"],
        working_hypotheses=["h1", "h2"],
        coordinates=["желание", "долг / ответственность"],
        canonical_tensions=["желание ↔ долг"],
        free_tensions=["конечность ↔ смысл"],
        provenance=prov(),
    )
    base.update(kw)
    return QueryRepresentation(**base)


# ------------------------------------------------------------------ QueryRepresentation


def test_query_representation_valid():
    q = query()
    assert q.provenance.origin == "benchmark_adapter"


@pytest.mark.parametrize(
    "override",
    [
        {"working_hypotheses": ["only one"]},
        {"working_hypotheses": ["a", "b", "c", "d", "e"]},
        {"coordinates": ["desire"]},
        {"canonical_tensions": ["конечность ↔ смысл"]},
        {"free_tensions": ["желание ↔ долг"]},  # canonical must not go to free
        {"free_tensions": ["просто текст"]},
        {"confirmed_question": ""},
    ],
)
def test_query_representation_rejects(override):
    with pytest.raises(ValidationError):
        query(**override)


@pytest.mark.parametrize("attr", ["tradition", "author", "gender", "age", "diagnosis", "country"])
def test_query_rejects_forbidden_attributes(attr):
    data = query().model_dump()
    data[attr] = "x"
    with pytest.raises(ValidationError):
        QueryRepresentation.model_validate(data)


def test_benchmark_adapter_must_be_marked():
    with pytest.raises(ValidationError):
        prov(confirmed_question_source="user_confirmed")
    with pytest.raises(ValidationError):
        prov(benchmark_item_id=None)
    QueryProvenance(origin="production", confirmed_question_source="user_confirmed", interpretation_source="llm")


# ------------------------------------------------------------------ benchmark adapter


def test_center_becomes_confirmed_question(bench):
    case = bench.cases[0]
    q = case_query(case)
    assert q.confirmed_question == center_to_question(case.center) == "Имею ли я право выбрать собственную жизнь?"
    assert q.provenance.confirmed_question_source == "benchmark_center_proxy"
    assert q.provenance.interpretation_source == "benchmark_expected_structure_proxy"
    assert q.working_hypotheses == [case.expected_structure.semantic_node, *case.expected_structure.distinctions]
    assert q.context.narrative == case.narrative and q.context.circumstance == case.circumstance


def test_all_benchmark_cases_adapt(bench):
    queries = [case_query(c) for c in bench.cases]
    assert len(queries) == 20 and all(2 <= len(q.working_hypotheses) <= 4 for q in queries)


def test_canonical_free_tension_separation():
    refs = [
        TensionRef(text="желание ↔ долг", match="exact", taxonomy_tension="желание ↔ долг"),
        TensionRef(text="привязанность ↔ свобода", match="reversed_poles", taxonomy_tension="свобода ↔ привязанность"),
        TensionRef(text="конечность ↔ смысл", match="case_specific"),
    ]
    assert split_tensions(refs) == (["желание ↔ долг", "свобода ↔ привязанность"], ["конечность ↔ смысл"])


def test_contrast_variants_without_center_get_no_invented_query(bench):
    cp2 = next(p for p in bench.contrast_pairs if p.id == "CP2")
    probe = contrast_probe(cp2.variant_a, bench)
    assert probe.query is None and "Q0_QUESTION_ONLY_CONTROL" in probe.unavailable
    assert probe.coordinates  # STRUCTURE still computable
    cp1 = next(p for p in bench.contrast_pairs if p.id == "CP1")
    assert contrast_probe(cp1.variant_a, bench).query is not None  # CP1-A → B11
    assert "STRUCTURE" in contrast_probe(cp1.variant_b, bench).unavailable


# ------------------------------------------------------------------ MEANING representation


def test_meaning_documents_are_deterministic_and_cover_113(fragments):
    a, b = meaning_card_documents(fragments), meaning_card_documents(list(reversed(fragments)))
    assert [(d.key, d.sha256) for d in a] == [(d.key, d.sha256) for d in b]
    assert len(a) == expected_eligible() and not {d.key for d in a} & blocked_ids()
    assert all(d.version == MEANING_CARD_DOC_VERSION for d in a)


def test_meaning_document_excludes_thought_source_and_metadata(fragments):
    by_id = {f.id: f for f in fragments}
    f = by_id["C0442"]  # has a Thought
    text = meaning_card_text(f)
    assert (not f.thought or f.thought not in text) and "Будущее — не совсем наше" not in text
    for value in (f.tradition, f.work, f.translation, f.source, f.commentary, f.context):
        if value:
            assert value not in text


def test_meaning_document_field_order_and_content():
    rec = synthetic_corpus()[0]
    rec.update(
        thought="SECRET THOUGHT", fragment="SECRET FRAGMENT", commentary="SECRET COMMENTARY",
        context="SECRET CONTEXT", author="SECRET AUTHOR", tradition="SECRET TRADITION",
        translation="SECRET TRANSLATION", source="SECRET SOURCE",
        perspective="перспектива", philosophical_questions=["вопрос?"],
        coordinates=["желание"], tensions=["желание ↔ долг (potential)"],
    )
    frag = Fragment.model_validate(rec)
    text = meaning_card_text(frag)
    assert "SECRET" not in text
    # M2.4 spec: perspective + philosophical_questions only
    assert text == "Перспектива: перспектива\nФилософские вопросы:\n- вопрос?"
    # legacy M2.2 format is still reproducible
    from navigator.representations.meaning import meaning_card_text_v1

    assert meaning_card_text_v1(frag) == text + "\nКоординаты: желание\nНапряжения: желание ↔ долг"


def test_meaning_document_excludes_placeholders():
    rec = synthetic_corpus()[0]
    rec["perspective"] = "сильный кандидат для `ожидание ↔ действительность`. Сохранять притчу целиком."
    rec["philosophical_questions"] = ["[FINAL TEXTUAL PASS: вставить]", "настоящий вопрос?"]
    text = meaning_card_text(Fragment.model_validate(rec))
    assert "сильный кандидат" not in text and "FINAL TEXTUAL PASS" not in text and "настоящий вопрос?" in text


def test_no_placeholder_in_any_real_meaning_document(fragments):
    for d in meaning_card_documents(fragments):
        assert "FINAL TEXTUAL PASS" not in d.text and "Сохранять притчу" not in d.text


# ------------------------------------------------------------------ Q0 / Q1


def test_q0_is_question_only():
    assert q0_text(query()) == "Имею ли я право выбрать собственную жизнь?"


def test_q1_composition_and_context_exclusion():
    q = query()
    text = q1_text(q)
    # M2.4 spec: confirmed question + working hypotheses only
    assert text == "Вопрос: Имею ли я право выбрать собственную жизнь?\nРабочие интерпретации:\n- h1\n- h2"
    for excluded in ("семья", "длинный рассказ", "вина", "желание", "долг", "↔", "конечность"):
        assert excluded not in text
    from navigator.representations.meaning import q1_text_v1

    assert q1_text_v1(q) == text + "\nСмысловые напряжения:\n- желание ↔ долг\n- конечность ↔ смысл"


# ------------------------------------------------------------------ provider / cosine / cache


def test_provider_abstraction():
    fake = FakeEmbeddingClient()
    assert isinstance(fake, EmbeddingClient) and fake.is_fake
    assert fake.embed(["а б", "в"]).shape == (2, fake.config.dimensions)
    from navigator.providers.embeddings import OPENAI_EMBEDDING_CONFIG

    # optional OpenAI provider keeps its config
    assert OPENAI_EMBEDDING_CONFIG.model == "text-embedding-3-large" and OPENAI_EMBEDDING_CONFIG.dimensions == 3072
    assert "key" not in json.dumps(BASELINE_EMBEDDING_CONFIG.public_dict()).lower()


def test_openai_client_requires_env_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(EmbeddingUnavailable):
        OpenAIEmbeddingClient()


def test_cosine_ranking_and_tie_break():
    vectors = np.array([[1, 0], [0, 1], [1, 0], [0.9, 0.1]], dtype=np.float32)
    hits = cosine_rank(np.array([1, 0], dtype=np.float32), ["C0003", "C0001", "C0002", "C0004"], vectors, 3)
    assert [h.card_id for h in hits] == ["C0002", "C0003", "C0004"]  # tie → card_id ascending
    assert [h.rank for h in hits] == [1, 2, 3] and hits[0].cosine == pytest.approx(1.0)


def test_cache_identity_and_invalidation(tmp_path):
    client = FakeEmbeddingClient()
    cache = EmbeddingCache(tmp_path, client.config, "cards")
    r1 = Representation("C0001", "v1", "текст один")
    cache.embed([r1], client)
    assert len(client.calls) == 1
    EmbeddingCache(tmp_path, client.config, "cards").embed([r1], client)  # reload: hit
    assert len(client.calls) == 1
    changed = Representation("C0001", "v1", "текст изменён")
    EmbeddingCache(tmp_path, client.config, "cards").embed([changed], client)
    assert len(client.calls) == 2
    reloaded = EmbeddingCache(tmp_path, client.config, "cards")
    assert reloaded.get(r1) is None and reloaded.get(changed) is not None
    bumped = Representation("C0001", "v2", "текст изменён")
    assert reloaded.get(bumped) is None


def test_cache_never_mixes_configurations(tmp_path):
    from dataclasses import replace

    client = FakeEmbeddingClient()
    other = FakeEmbeddingClient(replace(client.config, model="other-model"))
    assert cache_dir(tmp_path, client.config, "cards") != cache_dir(tmp_path, other.config, "cards")
    cache = EmbeddingCache(tmp_path, client.config, "cards")
    with pytest.raises(ValueError):
        cache.embed([Representation("C0001", "v1", "x")], other)


# ------------------------------------------------------------------ STRUCTURE


def _frags(specs):
    recs = synthetic_corpus(len(specs))
    for rec, (coords, tensions, op) in zip(recs, specs):
        rec.update(coordinates=coords, tensions=tensions, philosophical_operation=op)
    return [Fragment.model_validate(r) for r in recs]


def test_structure_exact_matching_and_lexicographic_order():
    frags = _frags([
        (["желание", "действие"], [], "DISTINGUISH"),                    # C9000: 0 t, 2 c
        (["желание"], ["желание ↔ долг (potential)"], "DISTINGUISH"),     # C9001: 1 t, 1 c
        (["контроль"], [], "DISTINGUISH"),                                # C9002: no match
        (["действие"], ["желание ↔ долг"], "DISTINGUISH"),                # C9003: 1 t, 1 c
    ])
    hits, matching, tied = structure_rank(frags, ["желание", "действие"], ["желание ↔ долг"], 15)
    assert [h.card_id for h in hits] == ["C9001", "C9003", "C9000"]
    assert matching == 3 and tied == 0
    assert hits[0].matched_tensions == ["желание ↔ долг"] and hits[2].matched_coordinates == ["действие", "желание"]


def test_structure_tie_break_and_cutoff():
    frags = _frags([(["желание"], [], "DISTINGUISH")] * 4)
    hits, matching, tied = structure_rank(frags, ["желание"], [], 2)
    assert [h.card_id for h in hits] == ["C9000", "C9001"] and matching == 4 and tied == 2


def test_operation_does_not_affect_structure_score():
    a = _frags([(["желание"], [], "DISTINGUISH"), (["желание"], [], "REVALUE_GOOD")])
    b = _frags([(["желание"], [], "REVALUE_GOOD"), (["желание"], [], "DISTINGUISH")])
    ha, _, _ = structure_rank(a, ["желание"], [], 5)
    hb, _, _ = structure_rank(b, ["желание"], [], 5)
    assert [h.card_id for h in ha] == [h.card_id for h in hb]
    assert [h.operation for h in ha] == ["DISTINGUISH", "REVALUE_GOOD"]


# ------------------------------------------------------------------ union / engine


def test_candidate_union_signals(retriever, bench):
    result = retriever.retrieve(case_query(bench.cases[2]), "B03")
    union = {c.card_id: c for c in result.candidate_union}
    q1 = {h.card_id for h in result.q1_meaning.hits}
    st = {h.card_id for h in result.structure.hits}
    assert set(union) == q1 | st
    for cid, c in union.items():
        assert (c.meaning_rank is not None) == (cid in q1)
        assert (c.structure_rank is not None) == (cid in st)
        assert "final_score" not in c.model_dump()
    assert [c.card_id for c in result.candidate_union] == sorted(union)


def test_q0_excluded_from_union():
    from navigator.models.retrieval import SimilarityHit

    m = [SimilarityHit(card_id="C0001", rank=1, cosine=0.9)]
    union = candidate_union(m, [], {"C0001": "DISTINGUISH"})
    assert [c.card_id for c in union] == ["C0001"]


def test_result_rejects_cards_outside_q1_and_structure(retriever, bench):
    result = retriever.retrieve(case_query(bench.cases[0]), "B01")
    data = result.model_dump()
    in_union = {c["card_id"] for c in data["candidate_union"]}
    outsider = next(cid for cid in retriever.card_ids if cid not in in_union)
    data["candidate_union"].append({"card_id": outsider, "found_by": ["Q1_MEANING"]})
    with pytest.raises(ValidationError):  # e.g. a Q0-only card cannot enter the union
        CandidateRetrievalResult.model_validate(data)


def test_unresolved_never_retrieved(retriever, bench):
    assert len(retriever.card_ids) == expected_eligible() and not set(retriever.card_ids) & blocked_ids()
    for case in bench.cases:
        r = retriever.retrieve(case_query(case), case.id)
        ids = {h.card_id for h in r.q0_control.hits} | {c.card_id for c in r.candidate_union}
        assert not ids & blocked_ids()
    data = r.model_dump()
    data["candidate_union"][0]["card_id"] = "C0364" if blocked_ids() != UNRESOLVED_IDS else "C0377"
    with pytest.raises(ValidationError):
        CandidateRetrievalResult.model_validate(data)


def test_retrieval_is_deterministic(fragments, bench, tmp_path):
    q = case_query(bench.cases[5])
    a = CandidateRetriever(fragments, FakeEmbeddingClient(), cache_root=tmp_path / "a").retrieve(q, "B06")
    b = CandidateRetriever(fragments, FakeEmbeddingClient(), cache_root=tmp_path / "b").retrieve(q, "B06")
    assert a.model_dump() == b.model_dump()


# ------------------------------------------------------------------ contrast / trace / runner


def test_contrast_overlap_diagnostics(retriever, bench):
    diag = contrast_diagnostics(bench, retriever)
    assert [d["pair_id"] for d in diag] == ["CP1", "CP2", "CP3", "CP4"]
    for d in diag:
        assert set(d["routes"]) == {"Q0_QUESTION_ONLY_CONTROL", "Q1_MEANING", "STRUCTURE", "NARRATIVE_CONTROL"}
        nc = d["routes"]["NARRATIVE_CONTROL"]
        assert nc["status"] == "computed" and 0 <= nc["overlap_count"] <= 10
        assert nc["overlap_share_of_top_n"] == round(nc["overlap_count"] / 10, 3)
        assert "threshold" not in json.dumps(d).lower().replace("no pass threshold", "")
    cp2 = diag[1]["routes"]
    assert cp2["STRUCTURE"]["status"] == "computed" and cp2["Q0_QUESTION_ONLY_CONTROL"]["status"] == "not_computable"
    assert diag[0]["routes"]["STRUCTURE"]["status"] == "not_computable"  # CP1-B lists no coordinates


def test_trace_serialization_roundtrip(retriever, bench):
    case = bench.cases[1]
    trace = trace_for_case("run-x", bench, case.id, retriever.retrieve(case_query(case), case.id))
    data = json.loads(json.dumps(trace.model_dump(mode="json"), ensure_ascii=False))
    back = BenchmarkRunTrace.model_validate(data)
    cr = back.candidate_retrieval
    assert back.schema_version == "benchmark-trace/0.2.0"
    assert cr.query.confirmed_question == center_to_question(case.center)
    assert {c.fragment_id for c in back.candidate_pool} == {c.card_id for c in cr.candidate_union}
    assert back.final_cards == []  # no composition in M2.2
    wrong = dict(data, item_id="B09")
    with pytest.raises(ValidationError):
        BenchmarkRunTrace.model_validate(wrong)


@legacy_only
def test_run_benchmark_structure_with_fake_but_refuse_to_record(retriever, bench, tmp_path):
    traces, diag = run_benchmark(bench, retriever, "fake-run")
    assert len(traces) == 20 and len(diag) == 4
    runs = tmp_path / "runs"
    with pytest.raises(RuntimeError):
        write_run(bench, retriever, runs_dir=runs)
    assert not runs.exists()


# ------------------------------------------------------------------ corpus invariants


@legacy_only
def test_corpus_invariants_preserved(fragments):
    from navigator.corpus.readiness import retrieval_universe

    assert len(fragments) == 124 and len(retrieval_universe(fragments)) == 113
    assert {f.id for f in fragments if f.technical.operational_status == "unresolved"} == UNRESOLVED_IDS
    manifest = json.loads((ROOT / "data/corpus/launch-manifest.json").read_text(encoding="utf-8"))
    assert manifest["routes"]["SOURCE"] == "disabled_pending_full_fragment_text"
    from navigator.corpus.sources import sha256

    assert sha256(CORPUS).startswith("5554aa8c006afe6b")


@legacy_only
def test_structure_only_run_needs_no_embeddings(fragments, bench, tmp_path):
    from navigator.benchmark.runner import write_structure_only_run

    out = write_structure_only_run(bench, fragments, runs_dir=tmp_path)
    data = json.loads((out / "structure-results.json").read_text(encoding="utf-8"))
    assert len(data["cases"]) == 20 and "PENDING_API" in data["scope"]
    ids = {h["card_id"] for c in data["cases"] for h in c["hits"]}
    assert ids and not ids & UNRESOLVED_IDS
    assert "meaning" not in json.dumps(data["cases"]).lower()

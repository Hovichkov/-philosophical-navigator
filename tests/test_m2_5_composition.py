"""M2.5 composition contracts. No test calls a live model."""

from __future__ import annotations

from corpus_snapshot import load_test_fragments

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from navigator.benchmark.adapter import case_query
from navigator.benchmark.runner import trace_for_case
from navigator.composition.composer import SYSTEM_PROMPT, build_package, compose, source_label
from navigator.composition.runner import render_samples, run_composition
from navigator.models.benchmark import Benchmark
from navigator.models.composition import OPENING_LINE, CompositionResult
from navigator.models.fragment import Fragment
from navigator.models.vocabularies import UNRESOLVED_IDS
from navigator.providers.fake import FakeEmbeddingClient
from navigator.retrieval.engine import CandidateRetriever

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def fragments():
    return load_test_fragments()


@pytest.fixture(scope="module")
def bench():
    return Benchmark.model_validate(json.loads((ROOT / "data/eval/benchmarks/m2_1-retrieval-benchmark-v0.1.json").read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def trace(fragments, bench, tmp_path_factory):
    r = CandidateRetriever(fragments, FakeEmbeddingClient(), cache_root=tmp_path_factory.mktemp("c"))
    return trace_for_case("t", bench, "B03", r.retrieve(case_query(bench.cases[2]), "B03")).model_dump(mode="json")


class ScriptedComposer:
    """Test double returning pre-written structured outputs."""

    name = "scripted"
    model = None

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.feedback: list[str | None] = []

    def complete(self, package, feedback=None):
        self.feedback.append(feedback)
        return self.outputs.pop(0), {"calls": 1}


def output(pkg, n=3, **over):
    ids = [c["card_id"] for c in pkg["candidates"]]
    persp = [
        {"card_id": ids[i], "role": f"ход {i}", "title": f"Вывод {i}", "perspective": f"Перспектива {i}.",
         "reflection_question": f"Что я вижу, если {i}?", "why_selected": "причина", "main_idea": "Главная мысль источника.", "applied_insight": "Что это может значить для вопроса.", "distinction": "Помогает различить одно и другое.", "question_explanation": "Речь о том, что вы видите сейчас."}
        for i in range(n)
    ]
    out = {"perspectives": persp, "fewer_than_three_reason": None if n == 3 else "третья дублирует первые две",
           "rejected": [{"card_id": ids[-1], "reason": "ложное совпадение"}],
           "q1_top": {"card_id": pkg["q1_top_card_id"],
                      "decision": "selected" if pkg["q1_top_card_id"] in ids[:n] else "rejected", "reason": "r"}}
    out.update(over)
    return out


def test_package_contains_only_candidate_pool(trace, fragments):
    pkg = build_package(trace, fragments)
    pool = [c["card_id"] for c in trace["candidate_retrieval"]["candidate_union"]]
    assert [c["card_id"] for c in pkg["candidates"]] == pool
    assert len(pkg["candidates"]) < 113 and not set(pool) & UNRESOLVED_IDS
    text = json.dumps(pkg, ensure_ascii=False)
    for f in fragments:
        if f.thought and f.id in pool:
            assert f.thought not in text  # retrieval fields only


def test_valid_three_perspectives_with_sources_from_corpus(trace, fragments):
    pkg = build_package(trace, fragments)
    res = compose(pkg, fragments, ScriptedComposer([output(pkg)]))
    assert len(res.perspectives) == 3 and res.opening == OPENING_LINE
    by_id = {f.id: f for f in fragments}
    for p in res.perspectives:
        assert p.source == source_label(by_id[p.card_id])  # never model-written
        assert p.reflection_question.endswith("?")
    assert res.rejected and res.q1_top.card_id == pkg["q1_top_card_id"]
    assert res.user_text().startswith(OPENING_LINE)


def test_two_perspectives_allowed_with_reason(trace, fragments):
    pkg = build_package(trace, fragments)
    res = compose(pkg, fragments, ScriptedComposer([output(pkg, n=2)]))
    assert len(res.perspectives) == 2 and res.fewer_than_three_reason


def test_two_perspectives_without_reason_rejected(trace, fragments):
    pkg = build_package(trace, fragments)
    bad = output(pkg, n=2, fewer_than_three_reason=None)
    with pytest.raises(ValueError):
        compose(pkg, fragments, ScriptedComposer([bad, bad]))


@pytest.mark.parametrize("n", [1, 4])
def test_perspective_count_bounds(trace, fragments, n):
    pkg = build_package(trace, fragments)
    bad = output(pkg, n=min(n, len(pkg["candidates"]) - 1))
    if n == 1 and pkg.get("corpus_version"):  # final corpus (MVP): one strong card is a valid answer
        assert len(compose(pkg, fragments, ScriptedComposer([bad, bad])).perspectives) == 1
        return
    with pytest.raises(ValueError):
        compose(pkg, fragments, ScriptedComposer([bad, bad]))


def test_selection_outside_pool_and_unresolved_rejected(trace, fragments):
    pkg = build_package(trace, fragments)
    outsider = next(f.id for f in fragments if f.id not in {c["card_id"] for c in pkg["candidates"]} and f.technical.retrieval_eligible)
    bad = output(pkg)
    bad["perspectives"][0]["card_id"] = outsider
    unresolved = output(pkg)
    unresolved["perspectives"][0]["card_id"] = "C0377"
    for o in (bad, unresolved):
        with pytest.raises(ValueError):
            compose(pkg, fragments, ScriptedComposer([o, o]))


def test_repair_attempt_gets_validation_feedback(trace, fragments):
    pkg = build_package(trace, fragments)
    bad = output(pkg)
    bad["perspectives"][0]["reflection_question"] = "без вопросительного знака"
    composer = ScriptedComposer([bad, output(pkg)])
    res = compose(pkg, fragments, composer)
    assert res.meta.attempts == 2 and composer.feedback[0] is None and "reflection_question" in composer.feedback[1]


def test_reflection_question_required_and_advice_blocked(trace, fragments):
    pkg = build_package(trace, fragments)
    missing = output(pkg)
    missing["perspectives"][0]["reflection_question"] = ""
    advice = output(pkg)
    advice["perspectives"][1]["perspective"] = "Вам следует уехать, это правильное решение."
    for o in (missing, advice):
        with pytest.raises(ValueError):
            compose(pkg, fragments, ScriptedComposer([o, o]))


def test_q1_top_decision_must_match_selection(trace, fragments):
    pkg = build_package(trace, fragments)
    o = output(pkg)
    o["q1_top"]["decision"] = "rejected" if o["q1_top"]["decision"] == "selected" else "selected"
    with pytest.raises(ValueError):
        compose(pkg, fragments, ScriptedComposer([o, o]))


def test_model_supplied_source_is_ignored(trace, fragments):
    pkg = build_package(trace, fragments)
    o = output(pkg)
    o["perspectives"][0]["source"] = "Выдуманный автор, гл. 99"  # a model trying to write a source
    res = compose(pkg, fragments, ScriptedComposer([o]))
    by_id = {f.id: f for f in fragments}
    assert res.perspectives[0].source == source_label(by_id[res.perspectives[0].card_id])
    assert "Выдуманный" not in res.model_dump_json()


def test_no_tradition_diversity_requirement():
    assert "НЕ традицией или автором" in SYSTEM_PROMPT
    assert "tradition" not in CompositionResult.model_fields and "traditions" not in CompositionResult.model_fields


def test_runner_trace_and_samples(trace, fragments, bench, tmp_path):
    pkg = build_package(trace, fragments)
    results = run_composition([trace], fragments, ScriptedComposer([output(pkg)]), tmp_path)
    saved = CompositionResult.model_validate_json((tmp_path / "compositions" / "B03.json").read_text(encoding="utf-8"))
    assert saved.perspectives and saved.rejected and saved.candidate_pool == [c["card_id"] for c in pkg["candidates"]]
    assert (tmp_path / "packages" / "B03.json").exists()
    md = render_samples(results, [trace], {c.id: c for c in bench.cases}, fragments, "t")
    assert "Why these cards" in md and OPENING_LINE in md and "Notable rejected candidates" in md
    # resume: existing composition is reused without calling the composer
    again = run_composition([trace], fragments, ScriptedComposer([]), tmp_path)
    assert again["B03"] == saved

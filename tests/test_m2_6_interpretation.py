"""M2.6 interpretation layer contracts. No test calls a live model."""

from __future__ import annotations

from corpus_snapshot import load_test_fragments

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from navigator.interpretation.interpreter import confirm, interpret, to_query_representation
from navigator.interpretation.runner import case_input, load_benchmark, render_samples, run_interpretation
from navigator.models.interpretation import (
    Confirmation,
    InsufficientInterpretation,
    InterpretationInput,
    InterpretationResult,
)
from navigator.models.query import QueryRepresentation
from navigator.models.vocabularies import COORDINATES, TENSIONS

ROOT = Path(__file__).resolve().parents[1]
BENCH = load_benchmark(ROOT / "data/eval/interpretation/m2_6-interpretation-benchmark-v0.1.json")
RUN = ROOT / "reports/interpretation-runs/m2_6-interpretation-20260927/interpretations"
R01 = BENCH["cases"][0]


class ScriptedInterpreter:
    name = "scripted"
    model = None

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0
        self.feedback = []

    def complete(self, inp, feedback=None):
        self.calls += 1
        self.feedback.append(feedback)
        return self.outputs.pop(0), {"calls": 1}


def good(**over):
    out = {
        "sufficient": True, "insufficiency_reason": None,
        "reading_notes": [{"kind": "tension", "note": "желание запретить сталкивается с пониманием, что это не поможет"}],
        "working_hypotheses": ["забота может переживаться как обязанность устранить трудность",
                               "невозможность изменить происходящее создаёт напряжение между действием и принятием"],
        "proposed_question": "Как мне быть рядом с сыном, принимая то, что я не могу немедленно исправить?",
        "coordinates": ["принятие / сопротивление", "контроль", "отношение к другому"],
        "canonical_tensions": ["действие ↔ принятие"],
        "free_tensions": ["забота ↔ контроль"],
        "ambiguity_notes": [],
    }
    out.update(over)
    return out


def test_result_has_proposed_question_hypotheses_and_trace():
    res = interpret(case_input(R01), ScriptedInterpreter([good()]))
    assert isinstance(res, InterpretationResult) and res.proposed_question.endswith("?")
    assert 2 <= len(res.working_hypotheses) <= 4
    assert res.trace.reading_notes and res.trace.input_sha256 and res.trace.attempts == 1


@pytest.mark.parametrize("hyps", [["одна"], ["1", "2", "3", "4", "5"]])
def test_hypothesis_count_bounds(hyps):
    with pytest.raises(ValueError):
        interpret(case_input(R01), ScriptedInterpreter([good(working_hypotheses=hyps)] * 2))


def test_coordinates_and_canonical_tensions_from_taxonomy_free_allowed():
    res = interpret(case_input(R01), ScriptedInterpreter([good()]))
    assert set(res.coordinates) <= COORDINATES and set(res.canonical_tensions) <= TENSIONS
    assert res.free_tensions == ["забота ↔ контроль"]
    for bad in (good(coordinates=["беспомощность"]), good(canonical_tensions=["забота ↔ контроль"]),
                good(free_tensions=["действие ↔ принятие"])):
        with pytest.raises(ValueError):
            interpret(case_input(R01), ScriptedInterpreter([bad, bad]))


def test_no_diagnosis_or_advice_fields():
    fields = set(InterpretationResult.model_fields)
    assert not fields & {"diagnosis", "advice", "recommendation", "treatment", "confirmed_question"}
    data = interpret(case_input(R01), ScriptedInterpreter([good()])).model_dump()
    data["diagnosis"] = "x"
    with pytest.raises(ValidationError):
        InterpretationResult.model_validate(data)


def test_advice_and_new_clinical_labels_are_rejected_with_repair():
    advice = good(proposed_question="Вам следует обратиться к врачу, как поступить?")
    diag = good(working_hypotheses=["у отца гиперопека", "у сына расстройство"])
    for bad in (advice, diag):
        s = ScriptedInterpreter([bad, good()])
        res = interpret(case_input(R01), s)
        assert res.trace.attempts == 2 and s.feedback[1]


def test_user_word_is_not_blocked_but_new_label_is():
    # «невроз» comes from the user; the guard only blocks labels the user did not use
    res = interpret(case_input(R01), ScriptedInterpreter([good(working_hypotheses=["слово «невроз» употребил сам человек", "h2"])]))
    assert res.status == "interpreted"


def test_insufficient_narrative_is_explicit_without_model_call():
    s = ScriptedInterpreter([])
    res = interpret(InterpretationInput(topic="Другое", experiences=[], difficulty_center="другое", free_narrative="всё сложно"), s)
    assert isinstance(res, InsufficientInterpretation) and s.calls == 0 and res.clarification_prompt
    reported = interpret(case_input(R01), ScriptedInterpreter([good(sufficient=False, insufficiency_reason="бессвязно")]))
    assert isinstance(reported, InsufficientInterpretation) and reported.reason == "бессвязно"


def test_proposed_is_not_confirmed_until_confirmation():
    res = interpret(case_input(R01), ScriptedInterpreter([good()]))
    assert not hasattr(res, "confirmed_question")
    rejected = confirm(res, action="rejected")
    with pytest.raises(ValueError):
        to_query_representation(res, rejected)
    user = confirm(res, action="confirmed", source="user")
    q = to_query_representation(res, user)
    assert isinstance(q, QueryRepresentation) and q.confirmed_question == res.proposed_question
    assert q.provenance.origin == "production" and q.provenance.confirmed_question_source == "user_confirmed"
    edited = confirm(res, action="edited", edited_text="Как мне быть рядом с сыном?")
    assert to_query_representation(res, edited).confirmed_question == "Как мне быть рядом с сыном?"
    sim = confirm(res, action="confirmed", source="benchmark_simulation")
    qs = to_query_representation(res, sim, item_id="R01")
    assert qs.provenance.origin == "benchmark_adapter" and "simulated" in qs.provenance.confirmed_question_source
    with pytest.raises(ValidationError):
        Confirmation(action="confirmed", source="user", proposed_question="А?", confirmed_question="Б?")


def test_runner_saves_trace_and_renders_samples(tmp_path):
    cases = [R01, BENCH["edge_cases"][0]]
    results = run_interpretation(cases, ScriptedInterpreter([good()]), tmp_path, workers=1)
    assert (tmp_path / "interpretations" / "R01.json").exists() and results["X01"].status == "insufficient_input"
    md = render_samples(cases, results, "t")
    assert "### Proposed question" in md and "insufficient input" in md and "Working hypotheses (internal)" in md


def test_benchmark_has_about_20_raw_cases_including_regression():
    ids = [c["id"] for c in BENCH["cases"]]
    assert len(ids) == 20 and len(set(ids)) == 20 and ids[0] == "R01"
    assert R01["free_narrative"].startswith("У моего сына невроз")


def _question(cid):
    return json.loads((RUN / f"{cid}.json").read_text(encoding="utf-8"))


@pytest.mark.skipif(not (RUN / "R01.json").exists(), reason="interpretation run not recorded")
def test_recorded_regression_case_preserves_key_elements():
    rec = _question("R01")
    exp = BENCH["regression_expectations"]["R01"]
    q = rec["proposed_question"].lower()
    q_and_h = " ".join([q, *rec["working_hypotheses"]]).lower()
    missing = [k for k, stems in exp["must_preserve_in_question"].items() if not any(s in q for s in stems)]
    missing += [k for k, stems in exp["must_preserve_in_question_or_hypotheses"].items() if not any(s in q_and_h for s in stems)]
    assert missing == [], (missing, rec["proposed_question"])
    assert not [s for s in exp["must_not_contain_in_question"] if s in q]
    assert exp["owner_decision"] and exp["human_review_notes"]  # accepted without exact match


@pytest.mark.skipif(not RUN.exists(), reason="interpretation run not recorded")
def test_recorded_run_covers_all_cases_and_validates():
    from pydantic import TypeAdapter

    adapter = TypeAdapter(InterpretationResult | InsufficientInterpretation)
    for c in BENCH["cases"]:
        res = adapter.validate_json((RUN / f"{c['id']}.json").read_text(encoding="utf-8"))
        assert res.status == "interpreted", c["id"]


def test_e2e_smoke_chain_marks_simulated_confirmation(tmp_path):
    from navigator.interpretation.runner import run_e2e_smoke
    from navigator.models.fragment import Fragment
    from navigator.providers.fake import FakeEmbeddingClient
    from navigator.retrieval.engine import CandidateRetriever

    fragments = load_test_fragments()
    interp = interpret(case_input(R01), ScriptedInterpreter([good()]))
    retriever = CandidateRetriever(fragments, FakeEmbeddingClient(), cache_root=tmp_path / "c")

    class Composer:
        name, model = "scripted", None

        def complete(self, package, feedback=None):
            ids = [c["card_id"] for c in package["candidates"]][:3]
            persp = [{"card_id": i, "role": "ход", "title": "Одно и другое — разные вещи", "perspective": "Перспектива.",
                      "reflection_question": "Что я вижу?", "why_selected": "причина", "main_idea": "Главная мысль источника.", "applied_insight": "Что это может значить для вопроса.", "distinction": "Помогает различить одно и другое.", "question_explanation": "Речь о том, что вы видите сейчас."} for i in ids]
            top = package["q1_top_card_id"]
            return {"perspectives": persp, "fewer_than_three_reason": None, "rejected": [],
                    "q1_top": {"card_id": top, "decision": "selected" if top in ids else "rejected", "reason": "r"}}, {}

    rec = run_e2e_smoke(R01, interp, fragments, retriever, Composer(), tmp_path / "smoke")
    assert rec["confirmation"]["source"] == "benchmark_simulation"
    assert rec["query_representation"]["provenance"]["confirmed_question_source"] == "benchmark_simulated_user_confirmation"
    assert rec["query_representation"]["confirmed_question"] == interp.proposed_question
    assert len(rec["composition"]["perspectives"]) == 3 and (tmp_path / "smoke" / "E2E-SMOKE.md").exists()

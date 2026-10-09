"""M3.1 result clarity: plain-language card contract, psychological-function guard, «Подробнее»,
Copy / Share, backward compatibility. No test calls a live model."""

from __future__ import annotations

from corpus_snapshot import load_test_fragments

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from navigator.benchmark.adapter import case_query
from navigator.benchmark.runner import trace_for_case
from navigator.composition.composer import SYSTEM_PROMPT, build_package, compose
from navigator.interpretation import interpreter as interp_mod
from navigator.models.benchmark import Benchmark
from navigator.models.composition import CompositionResult, Perspective
from navigator.models.fragment import Fragment
from navigator.models.interpretation import PSYCH_FUNCTION_RULE, amplification_hits
from navigator.providers.fake import FakeEmbeddingClient
from navigator.retrieval.engine import CandidateRetriever

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "src/navigator/prototype/static/index.html"
DISCLAIMER = "Инструмент предназначен для самоанализа и не заменяет профессиональную помощь."

# The sentence found in the manual M3 session (card 1, Иов 38) that motivated the rule.
FOUND = ("Если объяснение «причина во мне» держится крепче, чем позволяет знание о целом, то вина может оказаться "
         "не только чувством, но и способом сделать происходящее понятным.")


@pytest.fixture(scope="module")
def fragments():
    return load_test_fragments()


@pytest.fixture(scope="module")
def package(fragments, tmp_path_factory):
    bench = Benchmark.model_validate(json.loads((ROOT / "data/eval/benchmarks/m2_1-retrieval-benchmark-v0.1.json").read_text(encoding="utf-8")))
    r = CandidateRetriever(fragments, FakeEmbeddingClient(), cache_root=tmp_path_factory.mktemp("c"))
    trace = trace_for_case("t", bench, "B03", r.retrieve(case_query(bench.cases[2]), "B03")).model_dump(mode="json")
    return build_package(trace, fragments)


def card(cid, **over):
    c = {"card_id": cid, "role": "ход", "title": "Целое видно не полностью",
         "distinction": "Помогает различить чувство вины и знание причины.",
         "question_explanation": "Речь о том, что происходит с сыном вне дома.",
         "main_idea": "Иов требует объяснения, но ему показывают, как мало он видит из целого.",
         "applied_insight": "Вы пишете: «мне кажется, я виновата». Можно спросить себя, что ещё может влиять на сына.",
         "perspective": "Книга Иова показывает предел взгляда одного человека. Тот, кто не видит целого, "
                        "не может быть уверен в своём объяснении до конца.",
         "reflection_question": "Что я знаю о жизни сына в школе, что не укладывается в «это из-за меня»?",
         "why_selected": "предел объяснения"}
    c.update(over)
    return c


class Scripted:
    name, model = "scripted", None

    def __init__(self, outputs):
        self.outputs, self.feedback = list(outputs), []

    def complete(self, package, feedback=None):
        self.feedback.append(feedback)
        return self.outputs.pop(0), {}


def output(pkg, first=None):
    ids = [c["card_id"] for c in pkg["candidates"]][:3]
    persp = [card(i) for i in ids]
    if first:
        persp[0] = card(ids[0], **first)
    top = pkg["q1_top_card_id"]
    return {"perspectives": persp, "fewer_than_three_reason": None, "rejected": [],
            "q1_top": {"card_id": top, "decision": "selected" if top in ids else "rejected", "reason": "r"}}


# ------------------------------------------------------------------ psychological-function guard


def test_psych_function_patterns():
    for bad in (FOUND, "Возможно, вина даёт ощущение контроля над происходящим.",
                "Тревога помогает вам не чувствовать беспомощность.",
                "Может быть, желание всё исправить служит защитой от бессилия.",
                "Если так, забота нужна вам, чтобы не чувствовать себя лишней."):
        assert amplification_hits(bad), bad
    for ok in ("Вы пишете: «мне кажется, я виновата». Можно спросить себя, на чём держится это объяснение.",
               "Моисей говорит, что бремя превышает его силы, и бремя разделяется с другими.",
               "Можно исследовать, какую роль для вас играет надежда, что это пройдёт.",
               "Если признать предел, забота может стать общей, а не только моей."):
        assert not amplification_hits(ok), ok


def test_rule_is_in_both_prompts():
    assert PSYCH_FUNCTION_RULE in SYSTEM_PROMPT
    assert PSYCH_FUNCTION_RULE in interp_mod.SYSTEM_PROMPT


def test_psych_function_in_card_is_repaired_and_logged(package, fragments):
    c = Scripted([output(package, first={"applied_insight": FOUND}), output(package)])
    res = compose(package, fragments, c)
    assert res.meta.attempts == 2 and "unconfirmed hypothesis" in c.feedback[1]
    assert res.meta.usage["repairs"] and "способом" in res.meta.usage["repairs"][0]
    assert not any(amplification_hits(p.applied_insight + p.perspective) for p in res.perspectives)


def test_psych_function_in_details_is_repaired(package, fragments):
    c = Scripted([output(package, first={"perspective": FOUND}), output(package)])
    assert compose(package, fragments, c).meta.attempts == 2


# ------------------------------------------------------------------ plain-language card contract


def test_new_result_has_card_fields(package, fragments):
    res = compose(package, fragments, Scripted([output(package)]))
    assert res.schema_version == "composition/0.4.0" and res.meta.usage["repairs"] == []
    for p in res.perspectives:
        assert p.title and p.main_idea and p.applied_insight and p.reflection_question and p.perspective
    assert "Иов требует" in res.user_text()


@pytest.mark.parametrize("over,needle", [
    ({"main_idea": " ".join(["слово"] * 60)}, "main_idea is too long"),
    ({"applied_insight": "Карточка утверждает, что вина — это ответственность."}, "vocabulary"),
    ({"perspective": "Фрагмент показывает предел взгляда."}, "vocabulary"),
])
def test_long_or_technical_card_is_repaired(package, fragments, over, needle):
    c = Scripted([output(package, first=over), output(package)])
    res = compose(package, fragments, c)
    assert res.meta.attempts == 2 and needle in c.feedback[1]


def test_main_idea_and_applied_insight_come_together():
    base = {k: v for k, v in card("C0013").items()}
    base["source"] = "x"
    with pytest.raises(ValidationError):
        Perspective(**{**base, "applied_insight": None})


def test_old_composition_results_still_load():
    files = sorted((ROOT / "reports/composition-runs/m2_5-composition-20260927/compositions").glob("*.json"))
    if not files:
        pytest.skip("M2.5 run not present")
    for f in files[:5]:
        r = CompositionResult.model_validate_json(f.read_text(encoding="utf-8"))
        assert r.schema_version == "composition/0.1.0" and r.perspectives[0].main_idea is None


# ------------------------------------------------------------------ UI: «Подробнее», Copy / Share, disclaimer


def test_ui_has_details_copy_share_and_unchanged_disclaimer():
    html = INDEX.read_text(encoding="utf-8")
    for needle in ('"Подробнее"', 'id="copy"', 'id="share"', "navigator.share", "navigator.clipboard",
                   "main_idea", "applied_insight", "Вопрос к себе"):
        assert needle in html, needle
    assert f"<footer>{DISCLAIMER}</footer>" in html
    assert "специалист" not in html  # no separate referral line (owner decision for M3.1)


def test_public_view_card_keys(fragments, tmp_path):
    from navigator.prototype.flow import Services, Session

    class Interp:
        name, model = "scripted", None

        def complete(self, inp, feedback=None):
            return {"sufficient": True, "insufficiency_reason": None,
                    "reading_notes": [{"kind": "tension", "note": "желание исправить и предел влияния"}],
                    "working_hypotheses": ["возможно, вина даёт ощущение контроля",
                                           "принятие может переживаться как отказ от сына"],
                    "proposed_question": "Как мне помочь сыну, если я не могу всё исправить?",
                    "coordinates": ["принятие / сопротивление", "контроль"],
                    "canonical_tensions": ["действие ↔ принятие"], "free_tensions": [], "ambiguity_notes": []}, {}

    class Comp:
        name, model = "scripted", None

        def complete(self, pkg, feedback=None):
            return output(pkg), {}

    svc = Services(fragments, Interp(), Comp(),
                   lambda: CandidateRetriever(fragments, FakeEmbeddingClient(), cache_root=tmp_path / "c"))
    s = Session(svc, None)
    s.submit("Семья / дети / родители", ["Вину"], "Мне трудно принять происходящее",
             "Меня беспокоят вспышки агрессии у сына в школе, мне кажется я виновата и не могу это исправить.")
    s.confirm("confirmed")
    view = s.answer()
    p = view["perspectives"][0]
    assert set(p) == {"title", "source", "main_idea", "applied_insight", "reflection_question", "question_explanation", "details"}
    assert p["details"] == s.composition.perspectives[0].perspective
    assert "ощущение контроля" not in json.dumps(view, ensure_ascii=False)  # hypothesis stays internal

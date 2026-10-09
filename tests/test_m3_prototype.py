"""M3 prototype: flow state machine, confirmation paths, integration, amplification guard, server smoke.
No test calls a live model."""

from __future__ import annotations

from corpus_snapshot import load_test_fragments

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from navigator.composition.composer import build_package, compose
from navigator.interpretation.interpreter import interpret
from navigator.models.fragment import Fragment
from navigator.models.interpretation import InterpretationInput, amplification_hits
from navigator.models.vocabularies import UNRESOLVED_IDS
from navigator.prototype.flow import FlowError, Services, Session
from navigator.prototype.options import TOPICS, difficulty_options
from navigator.prototype.server import App, make_handler
from navigator.providers.fake import FakeEmbeddingClient
from navigator.retrieval.engine import CandidateRetriever

ROOT = Path(__file__).resolve().parents[1]
R01_NARRATIVE = ("У моего сына невроз - я не знаю как реагировать. Хочу ему запретить - но это не улучшит ситуацию. "
                 "У меня тоже в детстве было такое. Не знаю что делать (понятное дело, что я пойду к неврологу с ним), "
                 "но не хочу проблематизировать - надеюсь что это возрастное")


@pytest.fixture(scope="module")
def fragments():
    return load_test_fragments()


def interp_output(question="Как мне быть рядом с сыном, принимая то, что я не могу немедленно исправить?"):
    return {
        "sufficient": True, "insufficiency_reason": None,
        "reading_notes": [{"kind": "tension", "note": "желание запретить и понимание, что это не поможет"}],
        "working_hypotheses": ["возможно, запрет — способ вернуть ощущение контроля", "принятие может быть способом быть рядом"],
        "proposed_question": question,
        "coordinates": ["принятие / сопротивление", "отношение к другому", "контроль"],
        "canonical_tensions": ["действие ↔ принятие"], "free_tensions": [], "ambiguity_notes": [],
    }


class ScriptedInterpreter:
    name, model = "scripted", None

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.feedback = []

    def complete(self, inp, feedback=None):
        self.feedback.append(feedback)
        return self.outputs.pop(0), {}


class ScriptedComposer:
    name, model = "scripted", None

    def __init__(self, title=None, n=3):
        self.title, self.n, self.feedback = title, n, []

    def complete(self, package, feedback=None):
        self.feedback.append(feedback)
        ids = [c["card_id"] for c in package["candidates"]][: self.n]
        persp = [{"card_id": i, "role": "ход", "title": (self.title if (self.title and k == 0 and not feedback) else f"Вывод {k}"),
                  "perspective": "Можно посмотреть на это иначе.", "reflection_question": "Что я здесь вижу?",
                  "why_selected": "причина", "main_idea": "Главная мысль источника.", "applied_insight": "Что это может значить для вопроса.", "distinction": "Помогает различить одно и другое.", "question_explanation": "Речь о том, что вы видите сейчас."} for k, i in enumerate(ids)]
        top = package["q1_top_card_id"]
        return {"perspectives": persp, "fewer_than_three_reason": None if self.n == 3 else "третья дублирует",
                "rejected": [], "q1_top": {"card_id": top, "decision": "selected" if top in ids else "rejected", "reason": "r"}}, {}


@pytest.fixture()
def services(fragments, tmp_path):
    return Services(
        fragments=fragments,
        interpreter=ScriptedInterpreter([interp_output(), interp_output(), interp_output()]),
        composer=ScriptedComposer(),
        retriever_factory=lambda: CandidateRetriever(fragments, FakeEmbeddingClient(), cache_root=tmp_path / "cache"),
    )


def submit_r01(session):
    return session.submit("Отношения с близким человеком", ["Беспомощность", "Тревогу", "Желание всё исправить"],
                          "Мне трудно принять происходящее таким, какое оно сейчас есть", R01_NARRATIVE)


# ------------------------------------------------------------------ flow / state transitions


def test_state_transitions_and_proposed_not_confirmed(services, tmp_path):
    s = Session(services, tmp_path / "traces")
    assert s.state == "new"
    view = submit_r01(s)
    assert s.state == "proposed" and "proposed_question" in view and "confirmed_question" not in view
    assert s.query is None  # nothing enters retrieval before confirmation
    with pytest.raises(FlowError):
        s.answer()
    s.confirm("confirmed")
    assert s.state == "confirmed" and s.query.confirmed_question == s.interpretation.proposed_question
    assert s.query.provenance.origin == "production" and s.query.provenance.confirmed_question_source == "user_confirmed"
    result = s.answer()
    assert s.state == "answered" and 2 <= len(result["perspectives"]) <= 3
    assert (tmp_path / "traces" / f"{s.id}.json").exists()


def test_edit_confirmation_path(services):
    s = Session(services)
    submit_r01(s)
    s.confirm("edited", "Как мне быть рядом с сыном?")
    assert s.query.confirmed_question == "Как мне быть рядом с сыном?" and s.confirmation.action == "edited"
    assert s.query.provenance.confirmed_question_source == "user_edited"


def test_reject_with_own_question_path(services):
    s = Session(services)
    submit_r01(s)
    view = s.confirm("replaced", "Почему мне так тревожно за сына?")
    assert view["confirmed_question"] == "Почему мне так тревожно за сына?"
    assert s.confirmation.action == "replaced" and s.query.provenance.confirmed_question_source == "user_replaced"
    with pytest.raises(FlowError):
        Session(services).confirm("confirmed")  # nothing to confirm yet


def test_empty_own_text_and_unknown_action_rejected(services):
    s = Session(services)
    submit_r01(s)
    for action, text in (("edited", "  "), ("replaced", None), ("rejected", None), ("bogus", None)):
        with pytest.raises(FlowError):
            s.confirm(action, text)


def test_insufficient_narrative(services):
    s = Session(services)
    view = s.submit("Другое", [], "Другое", "всё сложно, не знаю")
    assert s.state == "insufficient" and view["clarification"] and "proposed_question" not in view
    with pytest.raises(FlowError):
        s.confirm("confirmed")


def test_integration_no_unresolved_and_public_view_hides_internals(services):
    s = Session(services)
    submit_r01(s)
    s.confirm("confirmed")
    view = s.answer()
    assert not {p.card_id for p in s.composition.perspectives} & UNRESOLVED_IDS
    assert set(view["perspectives"][0]) == {"title", "source", "main_idea", "applied_insight", "reflection_question", "question_explanation", "details"}
    text = json.dumps(view, ensure_ascii=False)
    for internal in ("working_hypotheses", "coordinates", "tensions", "card_id", "cosine", "C0"):
        assert internal not in text
    debug = s.debug_view()
    assert debug["interpretation"]["working_hypotheses"] and debug["retrieval"]["candidate_union"] and debug["composition"]


def test_two_perspectives_allowed(fragments, tmp_path):
    svc = Services(fragments, ScriptedInterpreter([interp_output()]), ScriptedComposer(n=2),
                   lambda: CandidateRetriever(fragments, FakeEmbeddingClient(), cache_root=tmp_path / "c"))
    s = Session(svc)
    submit_r01(s)
    s.confirm("confirmed")
    assert len(s.answer()["perspectives"]) == 2


def test_runtime_error_is_human_and_traced(fragments, tmp_path):
    class Broken:
        name, model = "broken", None

        def complete(self, *a, **k):
            raise RuntimeError("CLI error: secret stack detail")

    svc = Services(fragments, Broken(), ScriptedComposer(), lambda: None)
    s = Session(svc, tmp_path)
    with pytest.raises(FlowError) as exc:
        submit_r01(s)
    assert "stack" not in exc.value.user_message and "Попробуйте ещё раз" in exc.value.user_message
    assert s.errors and "secret stack detail" in s.errors[0]["error"]


# ------------------------------------------------------------------ amplification guard


def test_amplification_patterns():
    assert amplification_hits("…не отмахиваясь надеждой, что «само пройдёт»?")
    assert amplification_hits("Вы отмахиваетесь надеждой, что это пройдёт")
    assert amplification_hits("Похоже, за этим стоит невысказанная мысль")
    assert amplification_hits("Вам невыносимо происходящее, поэтому вы пытаетесь контролировать сына")
    assert not amplification_hits("Можно исследовать, какую роль для вас играет надежда, что это пройдёт")
    assert not amplification_hits("Можно проверить, связано ли желание вмешаться с тем, насколько трудно выдерживать происходящее")


def test_interpretation_amplified_question_is_repaired():
    s = ScriptedInterpreter([
        interp_output("Как мне быть рядом с сыном, не отмахиваясь надеждой, что «само пройдёт»?"),
        interp_output(),
    ])
    res = interpret(InterpretationInput(topic="t", experiences=[], difficulty_center="c", free_narrative=R01_NARRATIVE), s)
    assert res.trace.attempts == 2 and "unconfirmed hypothesis" in s.feedback[1]
    # bold INTERNAL hypotheses stay allowed
    assert "контроля" in res.working_hypotheses[0]


def test_composition_amplified_title_is_repaired(fragments, tmp_path):
    r = CandidateRetriever(fragments, FakeEmbeddingClient(), cache_root=tmp_path)
    svc = Session(Services(fragments, ScriptedInterpreter([interp_output()]), ScriptedComposer(), lambda: r))
    submit_r01(svc)
    svc.confirm("confirmed")
    trace = {"item_id": "x", "run_id": "x", "candidate_retrieval": r.retrieve(svc.query, "x").model_dump(mode="json")}
    composer = ScriptedComposer(title="Похоже, за этим стоит ваша невыносимость?")
    res = compose(build_package(trace, fragments), fragments, composer)
    assert res.meta.attempts == 2 and "unconfirmed hypothesis" in composer.feedback[1]


# ------------------------------------------------------------------ options / server smoke


def test_difficulty_options_contextual_with_other():
    opts = difficulty_options("Отношения с близким человеком")
    assert opts[-1] == "Другое" and "Мне трудно принять происходящее таким, какое оно сейчас есть" in opts
    assert all(difficulty_options(t)[-1] == "Другое" for t in TOPICS)


def test_server_endpoints_with_fakes(services, tmp_path):
    app = App(services, tmp_path / "t")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def post(path, body):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    try:
        with urllib.request.urlopen(base + "/") as r:
            assert "Инструмент Самоанализа" in r.read().decode()
        with urllib.request.urlopen(base + "/api/options") as r:
            assert json.loads(r.read())["topics"] == TOPICS
        code, v = post("/api/interpret", {"topic": "Отношения с близким человеком", "experiences": ["Тревогу"],
                                          "difficulty_center": "c", "narrative": R01_NARRATIVE})
        assert code == 200 and v["state"] == "proposed"
        code, bad = post("/api/answer", {"session_id": v["session_id"]})
        assert code == 422 and "Traceback" not in bad["error"]
        code, c = post("/api/confirm", {"session_id": v["session_id"], "action": "confirmed"})
        assert code == 200 and c["confirmed_question"] == v["proposed_question"]
        code, a = post("/api/answer", {"session_id": v["session_id"]})
        assert code == 200 and 2 <= len(a["perspectives"]) <= 3
        with urllib.request.urlopen(base + f"/debug/session/{v['session_id']}") as r:
            assert json.loads(r.read())["interpretation"]["working_hypotheses"]
        code, e = post("/api/confirm", {"session_id": "nope", "action": "confirmed"})
        assert code == 422 and e["error"]
    finally:
        httpd.shutdown()


# ------------------------------------------------------------------ recorded R01 run through the real UI


def _r01_session():
    d = ROOT / "reports/prototype-sessions"
    for p in sorted(d.glob("*.json")) if d.exists() else []:
        data = json.loads(p.read_text(encoding="utf-8"))
        if (data.get("interpretation_input") or {}).get("free_narrative", "").startswith("У моего сына невроз") and data["state"] == "answered":
            return data
    return None


@pytest.mark.skipif(_r01_session() is None, reason="R01 prototype session not recorded")
def test_recorded_r01_ui_session():
    d = _r01_session()
    assert d["confirmation"]["source"] == "user" and d["confirmation"]["action"] == "confirmed"
    assert d["query_representation"]["confirmed_question"] == d["interpretation"]["proposed_question"]
    ids = [p["card_id"] for p in d["composition"]["perspectives"]]
    assert 2 <= len(ids) <= 3 and not set(ids) & UNRESOLVED_IDS
    assert not amplification_hits(d["interpretation"]["proposed_question"])

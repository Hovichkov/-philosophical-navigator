"""MVP flow: STORY → FEELINGS → QUESTION → PHILOSOPHICAL ANSWER.

One clear question goes straight to the answer (no confirmation step); several independent questions → the person
picks one and the others stay in the session; an unclear story → one short clarifying question. The story is read
by ONE interpreter call; choosing a question (also later, from the answer) never calls the interpreter again.
No live model: scripted interpreter / selector / writer, fake embeddings."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import test_m3_3_1_human_language as base
from navigator.interpretation.interpreter import CLARIFICATION_PROMPT, UNCLEAR_PROMPT, interpret
from navigator.models.interpretation import InterpretationInput
from navigator.prototype.flow import FlowError, Services, Session
from navigator.providers.fake import FakeEmbeddingClient
from navigator.retrieval.engine import CandidateRetriever

ROOT = Path(__file__).resolve().parents[1]
fragments = base.fragments  # module fixture
SON, Q1 = base.SON, base.GOOD_Q
Q2 = "У меня тоже в детстве было такое. Как мне быть с тем, что я узнаю это в сыне?"
Q3 = "Как не проблематизировать то, что я надеюсь считать возрастным?"


class CountingInterp(base.Interp):
    def __init__(self, outputs):
        super().__init__(outputs)
        self.calls = 0

    def complete(self, inp, feedback=None):
        self.calls += 1
        self.inputs = [*getattr(self, "inputs", []), inp]
        return super().complete(inp, feedback)


def out(question=Q1, others=(), **over):
    hypotheses = over.pop("other_question_hypotheses", [])
    return {**base.interp_out(question), "other_questions": list(others),
            "other_question_hypotheses": hypotheses, "clarifying_question": None, **over}


def unclear(clarifying):
    return {**out(), "sufficient": False, "insufficiency_reason": "непонятно, что происходит",
            "clarifying_question": clarifying}


def services(fragments, tmp_path, outputs):
    it, sel = CountingInterp(outputs), base.Selector()  # counts its own calls
    svc = Services(fragments, it, sel,
                   lambda: CandidateRetriever(fragments, FakeEmbeddingClient(), cache_root=tmp_path / "c"),
                   writer=base.Writer())
    return svc, it, sel


def submit(s, narrative=SON, feelings=("Беспомощность",)):
    return s.submit("", list(feelings), "", narrative, auto_confirm=True)


# ------------------------------------------------------------------ 1. one clear question → straight to the answer


def test_one_clear_question_goes_to_the_answer_without_confirmation(fragments, tmp_path):
    svc, it, sel = services(fragments, tmp_path, [out()])
    s = Session(svc, tmp_path / "t")
    view = submit(s)
    assert s.state == "confirmed" and view["confirmed_question"] == Q1 and "questions" not in view
    assert s.auto_confirmed and s.query.confirmed_question == Q1
    assert s.input.topic == "Другое" and s.input.difficulty_center == "Другое"  # no topic / difficulty screens
    answered = s.compose()
    assert s.state == "answered" and answered["perspectives"]
    assert it.calls == 1 and sel.calls == 1  # one reading of the story, one selection — nothing in between
    assert json.loads((tmp_path / "t" / f"{s.id}.json").read_text())["auto_confirmed"] is True


def test_without_auto_confirm_the_old_confirmation_contract_stays(fragments, tmp_path):
    svc, it, _ = services(fragments, tmp_path, [out()])
    s = Session(svc, None)
    s.submit("", [], "", SON)
    assert s.state == "proposed" and s.query is None and not s.auto_confirmed


# ------------------------------------------------------------------ 2. several questions → choose one, keep the rest


def test_several_questions_are_offered_and_the_others_stay(fragments, tmp_path):
    primary_hyp = ["main hypothesis one", "main hypothesis two"]
    second_hyp = ["second question lens one", "second question lens two"]
    third_hyp = ["third question lens one", "third question lens two"]
    svc, it, sel = services(fragments, tmp_path, [out(
        Q1, [Q2, Q3], working_hypotheses=primary_hyp,
        other_question_hypotheses=[second_hyp, third_hyp])])
    s = Session(svc, None)
    view = submit(s)
    assert s.state == "proposed" and view["questions"] == [Q1, Q2, Q3] and s.query is None
    chosen = s.choose(1)
    assert s.state == "confirmed" and chosen["confirmed_question"] == Q2 and s.query.confirmed_question == Q2
    assert s.query.working_hypotheses == second_hyp
    assert chosen["questions"] == [Q1, Q2, Q3]  # the others stay in the session
    s.compose()
    assert s.state == "answered"
    back = s.choose(2)  # later, from the answer screen: another question of the same story
    assert back["confirmed_question"] == Q3 and s.composition is None and s.retrieval is None
    assert s.query.working_hypotheses == third_hyp
    assert s.compose()["confirmed_question"] == Q3
    assert it.calls == 1 and sel.calls == 2  # the story is never read again; each answer is one selection


def test_custom_question_before_retrieval_keeps_story_feelings_and_drops_other_hypotheses(fragments, tmp_path):
    main_hyp = ["main lens one", "main lens two"]
    alt_hyp = ["alternative lens one", "alternative lens two"]
    svc, it, _ = services(fragments, tmp_path, [out(Q1, [Q2], working_hypotheses=main_hyp,
                                                    other_question_hypotheses=[alt_hyp])])
    s = Session(svc, tmp_path / "t")
    submit(s, feelings=("Беспомощность", "Тревогу"))
    own = "Как мне распределить ответственность за общие решения?"
    view = s.confirm("replaced", own)
    assert view["confirmed_question"] == own and s.query.confirmed_question == own
    assert s.query.working_hypotheses == []
    assert s.query.context.narrative == SON and s.query.experiences == ["Беспомощность", "Тревогу"]
    assert it.calls == 1 and s.retrieval is None


def test_custom_question_then_return_to_first_proposed_restores_its_hypotheses(fragments, tmp_path):
    main_hyp = ["main question lens one", "main question lens two"]
    second_hyp = ["second question lens one", "second question lens two"]
    third_hyp = ["third question lens one", "third question lens two"]
    svc, it, sel = services(fragments, tmp_path, [out(
        Q1, [Q2, Q3], working_hypotheses=main_hyp,
        other_question_hypotheses=[second_hyp, third_hyp])])
    s = Session(svc, tmp_path / "t")
    submit(s, feelings=("Беспомощность", "Тревогу"))

    own = "Как мне распределить ответственность за общие решения?"
    s.confirm("replaced", own)
    assert s.query.confirmed_question == own and s.query.working_hypotheses == []
    assert s.compose()["confirmed_question"] == own

    s.choose(0)
    assert s.query.confirmed_question == Q1
    assert s.query.working_hypotheses == main_hyp
    assert s.query.context.narrative == SON and s.query.experiences == ["Беспомощность", "Тревогу"]

    s.choose(1)
    assert s.query.confirmed_question == Q2 and s.query.working_hypotheses == second_hyp
    assert it.calls == 1 and sel.calls == 1


def test_single_question_has_no_artificial_alternatives_and_the_prompt_only_splits():
    from navigator.interpretation.interpreter import SYSTEM_PROMPT

    result = interpret(InterpretationInput(topic="Другое", difficulty_center="Другое", free_narrative=SON),
                      CountingInterp([out(Q1)]))
    assert result.other_questions == []
    # 2026-10-23: the visible question is the person's own; other questions only if he asked them himself
    assert "только отделяет вопросы человека друг от друга" in SYSTEM_PROMPT
    assert "Никаких новых ракурсов" in SYSTEM_PROMPT and "обычно этот список пуст" in SYSTEM_PROMPT
    assert "а НЕ часть вопроса" in SYSTEM_PROMPT and "скрытые мотивы за факт" in SYSTEM_PROMPT


def test_choose_rejects_unknown_index_and_wrong_state(fragments, tmp_path):
    svc, *_ = services(fragments, tmp_path, [out(Q1, [Q2])])
    s = Session(svc, None)
    with pytest.raises(FlowError):
        s.choose(0)  # nothing read yet
    submit(s)
    for bad in (5, -1, True):
        with pytest.raises(FlowError):
            s.choose(bad)


def test_an_other_question_that_breaks_the_contract_is_dropped_without_a_repair_call():
    bad = "Почему мне страшно? Что со мной? Как быть? И что дальше?"  # 4 sentences + unnamed feeling
    it = CountingInterp([out(Q1, [bad, Q2])])
    res = interpret(InterpretationInput(topic="Другое", difficulty_center="Другое", free_narrative=SON), it)
    assert res.other_questions == [Q2] and it.calls == 1 and res.trace.attempts == 1


# ------------------------------------------------------------------ 3. unclear story → one short clarifying question


def test_unclear_story_gets_one_clarifying_question_and_the_answer_is_added(fragments, tmp_path):
    ask = "Что именно произошло с сыном?"
    svc, it, _ = services(fragments, tmp_path, [unclear(ask), out()])
    s = Session(svc, None)
    view = submit(s)
    assert s.state == "insufficient" and view["clarification"] == ask
    narrative = SON + "\n\nУ него начался тик, и я не знаю, как с ним говорить."
    view = submit(s, narrative)
    assert s.state == "confirmed" and view["confirmed_question"] == Q1 and it.calls == 2
    assert it.inputs[1].free_narrative == narrative and it.inputs[1].experiences == ["Беспомощность"]


@pytest.mark.parametrize("clarifying", [None, "", "Расскажите подробнее.", "Что случилось? И когда?"])
def test_a_missing_or_malformed_clarifying_question_falls_back_to_the_safe_prompt(clarifying):
    res = interpret(InterpretationInput(topic="Другое", difficulty_center="Другое", free_narrative=SON),
                    CountingInterp([unclear(clarifying)]))
    assert res.clarification_prompt == UNCLEAR_PROMPT


def test_a_too_short_story_is_asked_without_a_model_call(fragments, tmp_path):
    svc, it, _ = services(fragments, tmp_path, [out()])
    s = Session(svc, None)
    assert submit(s, "плохо")["clarification"] == CLARIFICATION_PROMPT and it.calls == 0


# ------------------------------------------------------------------ 4. feelings: optional, at most three


def test_feelings_are_optional_and_capped(fragments, tmp_path):
    svc, it, _ = services(fragments, tmp_path, [out(), out()])
    s = Session(svc, None)
    submit(s, feelings=())
    assert it.inputs[0].experiences == []
    submit(s, feelings=("Тревогу", "Страх", "Вину", "Злость", "Тревогу"))
    assert it.inputs[1].experiences == ["Тревогу", "Страх", "Вину"]


def test_feeling_options_are_the_approved_sixteen_plus_free_text():
    from navigator.prototype.options import EXPERIENCES, OTHER

    assert EXPERIENCES == [
        "Тревога", "Страх", "Злость", "Грусть", "Обида", "Одиночество", "Стыд", "Вина",
        "Зависть", "Разочарование", "Растерянность", "Пустота", "Радость", "Любовь", "Надежда", "Гордость",
        OTHER,
    ]
    assert "Раздражение" not in EXPERIENCES
    assert "Благодарность" not in EXPERIENCES


# ------------------------------------------------------------------ 5. the HTTP API


def test_api_interpret_auto_confirm_and_choose(fragments, tmp_path):
    from navigator.prototype.server import App, make_handler
    from http.server import ThreadingHTTPServer

    svc, it, sel = services(fragments, tmp_path, [out(Q1, [Q2])])
    app = App(svc, tmp_path / "traces")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base_url = f"http://127.0.0.1:{httpd.server_address[1]}"

    def post(path, body):
        req = urllib.request.Request(base_url + path, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    try:
        code, v = post("/api/interpret", {"experiences": [], "narrative": SON, "auto_confirm": True})
        assert code == 200 and v["state"] == "proposed" and v["questions"] == [Q1, Q2]
        code, c = post("/api/choose", {"session_id": v["session_id"], "index": 1})
        assert code == 200 and c["state"] == "confirmed" and c["confirmed_question"] == Q2
        code, a = post("/api/answer", {"session_id": v["session_id"]})
        assert code == 200 and a["perspectives"]
        code, e = post("/api/choose", {"session_id": v["session_id"], "index": "x"})
        assert code == 422 and "Traceback" not in e["error"]
        assert it.calls == 1
    finally:
        httpd.shutdown()


# ------------------------------------------------------------------ 6. the page: order of screens, no dead end


def test_page_order_is_story_feelings_question_answer_and_has_no_dead_end():
    page = (ROOT / "src/navigator/prototype/static/index.html").read_text(encoding="utf-8")
    assert '<section class="screen active" id="s-story">' in page  # the story is the first screen
    order = [page.index(f'id="{i}"') for i in ("s-story", "s-exp", "s-clarify", "s-choose", "s-result")]
    assert order == sorted(order)
    story = page[page.index('id="s-story"'):page.index("</section>", page.index('id="s-story"'))]
    assert "С чего начнём?" in story and "Можно начать с нескольких предложений." in story
    for gone in ('id="s-topic"', 'id="s-diff"', 'id="s-confirm"', 'id="s-next"', 'id="reflection"',
                 "в разработке", "Следующий круг", "/api/reflect", "Правильно ли мы поняли"):
        assert gone not in page, gone
    for kept in ('id="copy"', 'id="restart"', "auto_confirm: true", "/api/choose", "Пропустить",
                 "MAX_FEELINGS = 3", "if (BUSY) return;", "class Stale"):
        assert kept in page, kept


# ------------------------------------------------------------------ 7. «Изменить вопрос» on the answer screen


EDITED = "Как быть рядом с сыном, когда мне хочется запретить, но я понимаю, что это не поможет?"


def answered_session(fragments, tmp_path, outputs=None):
    svc, it, sel = services(fragments, tmp_path, outputs or [out()])
    s = Session(svc, tmp_path / "t")
    submit(s, feelings=("Беспомощность", "Тревогу"))
    first = s.compose()
    return s, it, sel, first


def test_edited_question_rebuilds_the_answer_without_the_interpreter(fragments, tmp_path):
    s, it, sel, first = answered_session(fragments, tmp_path)
    story, feelings, interpretation = s.input.free_narrative, list(s.input.experiences), s.interpretation
    view = s.confirm("edited", f"  {EDITED} ")
    assert view["state"] == "confirmed" and view["confirmed_question"] == EDITED
    assert "perspectives" not in view and s.composition is None and s.retrieval is None  # the old answer is gone
    assert s.query.confirmed_question == EDITED and s.query.provenance.confirmed_question_source == "user_edited"
    new = s.compose()
    assert new["confirmed_question"] == EDITED and new["perspectives"]
    assert s.composition.confirmed_question == EDITED  # the new selection was made for the edited question
    assert it.calls == 1 and sel.calls == 2  # no new reading of the story; one new selection
    assert s.input.free_narrative == story and s.input.experiences == feelings == ["Беспомощность", "Тревогу"]
    assert s.interpretation is interpretation and s.questions == [Q1]


def test_edited_question_reaches_the_selection_package(fragments, tmp_path):
    s, it, sel, _ = answered_session(fragments, tmp_path)
    seen = []
    orig = sel.complete
    sel.complete = lambda pkg, feedback=None: (seen.append(pkg["confirmed_question"]), orig(pkg, feedback))[1]
    s.confirm("edited", EDITED)
    s.compose()
    assert seen == [EDITED]


def test_cancel_sends_nothing_and_an_empty_edit_changes_nothing(fragments, tmp_path):
    s, it, sel, first = answered_session(fragments, tmp_path)
    composition = s.composition
    with pytest.raises(FlowError):
        s.confirm("edited", "   ")  # the page never sends it; the server keeps the answer anyway
    assert s.state == "answered" and s.composition is composition and s.public_view()["perspectives"]
    assert it.calls == 1 and sel.calls == 1
    page = (ROOT / "src/navigator/prototype/static/index.html").read_text(encoding="utf-8")
    cancel = page[page.index('$("edit-q-cancel")'):page.index("\n", page.index('$("edit-q-cancel")'))]
    assert "api(" not in cancel and "exclusive" not in cancel  # «Отмена» only closes the box


def test_only_an_edit_is_accepted_after_the_answer(fragments, tmp_path):
    s, *_ = answered_session(fragments, tmp_path)
    for action in ("confirmed", "replaced"):
        with pytest.raises(FlowError):
            s.confirm(action, EDITED)
    assert s.state == "answered"


def test_page_has_the_edit_action_next_to_the_question():
    page = (ROOT / "src/navigator/prototype/static/index.html").read_text(encoding="utf-8")
    result = page[page.index('id="s-result"'):]
    assert result.index('id="confirmed"') < result.index('id="edit-q"') < result.index('id="cards"')
    for needle in ("Изменить вопрос", 'action: "edited"', "exclusive(() => editQuestion(text))"):
        assert needle in page, needle


# ------------------------------------------------------------------ 2026-10-23: fast split, structure in the background


class Splitter:
    name, model = "scripted-split", None

    def __init__(self, out):
        self.out, self.calls = out, 0

    def complete(self, inp, feedback=None):
        self.calls += 1
        return self.out, {}


class FixedInterp(CountingInterp):
    def complete(self, inp, feedback=None, fixed_questions=None):
        self.fixed = fixed_questions
        return super().complete(inp, feedback)


OWN = "Как мне быть с тем, что я узнаю это в сыне?"  # made of the words of the invented story below
STORY = SON + " " + OWN


def split_session(fragments, tmp_path, split_out):
    svc, it, sel = services(fragments, tmp_path, [out(Q1)])
    it = svc.interpreter = FixedInterp([out(Q1)])
    svc.splitter = Splitter(split_out)
    return Session(svc, tmp_path / "t"), it, sel, svc.splitter


def test_own_question_is_shown_from_the_split_and_answered_with_the_background_structure(fragments, tmp_path):
    s, it, sel, sp = split_session(fragments, tmp_path, {"sufficient": True, "insufficiency_reason": None,
                                                          "clarifying_question": None, "asked": True,
                                                          "questions": [OWN]})
    view = s.submit("", ["Тревогу"], "", STORY, auto_confirm=True)
    assert view["state"] == "confirmed" and view["confirmed_question"] == OWN and sp.calls == 1
    answer = s.compose()  # waits for the structure, confirms, retrieves, composes
    assert answer["confirmed_question"] == OWN and answer["perspectives"]
    assert it.calls == 1 and it.fixed == [OWN]  # the structure was built for the person's own words
    assert s.interpretation.proposed_question == OWN and s.input.experiences == ["Тревогу"]
    assert [t["stage"] for t in s.timings][:2] == ["question_split", "search_structure"]


def test_a_split_question_not_made_of_his_words_falls_back_to_the_full_interpretation(fragments, tmp_path):
    invented = "Где моя ответственность перед чужим ребёнком, а где перед своим?"
    s, it, sel, sp = split_session(fragments, tmp_path, {"sufficient": True, "insufficiency_reason": None,
                                                          "clarifying_question": None, "asked": True,
                                                          "questions": [invented]})
    view = s.submit("", [], "", STORY, auto_confirm=True)
    assert sp.calls == 2 and it.fixed is None  # rejected twice → the old single call formulates the question
    assert view["confirmed_question"] == Q1


def test_no_own_question_uses_the_full_interpretation(fragments, tmp_path):
    s, it, sel, sp = split_session(fragments, tmp_path, {"sufficient": True, "insufficiency_reason": None,
                                                          "clarifying_question": None, "asked": False,
                                                          "questions": []})
    view = s.submit("", [], "", SON, auto_confirm=True)
    assert sp.calls == 1 and view["confirmed_question"] == Q1 and it.fixed is None


class FlakyInterp(FixedInterp):
    """The background structure fails once (a temporary model error), then works."""

    def complete(self, inp, feedback=None, fixed_questions=None):
        if self.calls == 0:
            self.calls += 1
            from navigator.interpretation.interpreter import InterpreterUnavailable
            raise InterpreterUnavailable("timeout")
        return super().complete(inp, feedback, fixed_questions)


OWN2 = "Что мне сказать ему вечером?"


def flaky_session(fragments, tmp_path, questions):
    s, _, sel, sp = split_session(fragments, tmp_path, {"sufficient": True, "insufficiency_reason": None,
                                                         "clarifying_question": None, "asked": True,
                                                         "questions": questions})
    it = s.services.interpreter = FlakyInterp([out(Q1)])
    return s, it, sel


def test_retry_after_a_failed_background_structure_builds_only_the_missing_step(fragments, tmp_path):
    s, it, sel = flaky_session(fragments, tmp_path, [OWN])
    s.submit("", ["Тревогу"], "", STORY + " " + OWN2, auto_confirm=True)
    with pytest.raises(FlowError):
        s.retrieve()
    assert s.state == "confirmed" and s.questions == [OWN] and s.input.experiences == ["Тревогу"]
    view = s.retrieve()  # «Попробовать ещё раз»: the structure is built again, then the search runs
    assert view["state"] == "retrieved" and view["confirmed_question"] == OWN
    assert s.compose()["perspectives"] and it.calls == 2 and it.fixed == [OWN] and sel.calls == 1
    s.retrieve()
    assert it.calls == 2  # nothing is rebuilt once the structure is there


def test_retry_after_a_failed_structure_also_works_when_choosing_one_of_several_questions(fragments, tmp_path):
    s, it, sel = flaky_session(fragments, tmp_path, [OWN, OWN2])
    view = s.submit("", [], "", STORY + " " + OWN2, auto_confirm=True)
    assert view["state"] == "proposed" and view["questions"] == [OWN, OWN2]
    with pytest.raises(FlowError):
        s.choose(1)
    assert s.state == "proposed" and s.questions == [OWN, OWN2]
    assert s.choose(1)["confirmed_question"] == OWN2 and it.calls == 2 and it.fixed == [OWN, OWN2]


def test_a_repeated_tap_during_the_rebuild_is_refused_without_a_second_model_call(fragments, tmp_path):
    s, it, sel = flaky_session(fragments, tmp_path, [OWN])
    s.submit("", [], "", STORY + " " + OWN2, auto_confirm=True)
    with pytest.raises(FlowError):
        s.retrieve()
    s._busy.acquire()  # the first retry is still running
    try:
        with pytest.raises(FlowError, match="concurrent"):
            s.retrieve()
    finally:
        s._busy.release()
    assert it.calls == 1


# invented examples: a lost/added negation or swapped actors is not the person's own question
WORK = "Я не хочу остаться на работе. Почему я не хочу остаться на работе?"
BOSS = "Мой начальник не доверяет коллеге, и мне от этого неловко. Почему начальник не доверяет коллеге?"


@pytest.mark.parametrize("question, narrative, ok", [
    ("Почему я не хочу остаться на работе?", WORK, True),
    ("Почему я хочу остаться на работе?", WORK, False),  # negation lost
    ("Почему начальник не доверяет коллеге?", BOSS, True),
    ("Почему коллега не доверяет начальнику?", BOSS, False),  # actors swapped
    ("Почему начальник доверяет коллеге?", BOSS, False),  # negation lost
    ("Почему я не хочу уйти с работы?", "Почему я хочу уйти с работы?", False),  # negation added
    ("Мой начальник не доверяет коллеге. Почему начальник не доверяет коллеге?", BOSS, True),  # context kept
])
def test_own_question_check_catches_negation_and_actor_changes(question, narrative, ok):
    from navigator.interpretation.interpreter import own_question_problem

    assert (own_question_problem(question, narrative) is None) is ok


def test_a_split_with_a_lost_negation_is_retried_then_left_to_the_full_interpretation(fragments, tmp_path):
    s, it, sel, sp = split_session(fragments, tmp_path, {"sufficient": True, "insufficiency_reason": None,
                                                          "clarifying_question": None, "asked": True,
                                                          "questions": ["Почему я хочу остаться на работе?"]})
    view = s.submit("", [], "", SON + " " + WORK, auto_confirm=True)
    assert sp.calls == 2 and it.fixed is None and view["confirmed_question"] == Q1

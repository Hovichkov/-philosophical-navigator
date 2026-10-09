"""MVP stabilization pass 1 (2026-10-08): final-corpus card contract, display label, feelings, unclear input and
failure messages. Structure and contracts only; language quality is judged in the real browser runs. No live model."""

from __future__ import annotations

import re
import threading

import pytest

import test_m3_3_1_human_language as base
from navigator.composition.composer import SYSTEM_PROMPT as SELECTOR_PROMPT
from navigator.composition.references import display_label
from navigator.composition.writer import (
    FINAL_WRITER_PROMPT,
    check_final_card,
    lead_excerpt,
    verbatim_excerpt,
)
from navigator.corpus.final_corpus import final_snapshot_fragments, load_final_active
from navigator.interpretation.interpreter import SYSTEM_PROMPT as INTERPRETER_PROMPT
from navigator.interpretation.interpreter import UNCLEAR_PROMPT, interpret
from navigator.models.interpretation import InsufficientInterpretation, InterpretationInput
from navigator.prototype.flow import (
    MAX_EXPERIENCES,
    USER_ERROR_BUSY,
    USER_ERROR_LIMIT,
    USER_ERROR_MODEL,
    FlowError,
    user_message_for,
)


@pytest.fixture(scope="module")
def final():
    return final_snapshot_fragments(load_final_active())


SEL = {"card_id": "C0281", "role": "ход", "why_selected": "w", "distinction": "Помогает различить А и Б"}
USER = "Я хочу быть с ней, а она говорит, что любит другого. Мне трудно принять это. Тревогу Грусть"
QUOTE = "Если ты хочешь, чтобы твои дети, жена и друзья всегда пребывали среди живых, то ты неразумен."


def card(**over):
    f = {"main_idea": "Эпиктет отделяет то, что решает сам человек, от того, что решает другой.",
         "applied_insight": "Вы пишете, что хотите быть с ней, а она любит другого. Её чувство решает она.",
         "reflection_question": "Что в этой истории зависит от моих поступков?", "quote_excerpt": "",
         "metaphor_words": []}
    f.update(over)
    return check_final_card("C0281", f, SEL, "Эпиктет · Беседы · I.11", USER, None, QUOTE)


# ------------------------------------------------------------------ 1. the four-part card


def test_final_card_has_no_title_details_or_explanation():
    c = card()
    assert c.card_format == "final-mvp" and c.title is None and c.perspective is None and c.question_explanation is None


@pytest.mark.parametrize("q", ["Что я думаю о её ответе? И чего хочу после него?", "Что я думаю о её ответе.",
                               "Что я думаю? о её ответе"])
def test_exactly_one_question(q):
    with pytest.raises(ValueError, match="question"):
        card(reflection_question=q)


@pytest.mark.parametrize("text", ["Вам следует отпустить её.", "Сделайте паузу в разговоре.", "Попробуйте её понять."])
def test_no_advice(text):
    with pytest.raises(ValueError, match="advice"):
        card(applied_insight="Вы пишете, что хотите быть с ней. " + text)


def test_comment_must_not_retell_the_quote():
    with pytest.raises(ValueError, match="retells the quote"):
        card(main_idea="Эпиктет говорит: кто хочет, чтобы дети, жена и друзья всегда пребывали среди живых, неразумен.")


def test_unnamed_feeling_and_gender_are_still_checked():
    with pytest.raises(ValueError, match="did not name"):
        card(applied_insight="Вы пишете, что хотите быть с ней. Вам стыдно перед ней.")
    with pytest.raises(ValueError, match="gender"):
        card(reflection_question="Я готов принять её ответ?")


def test_long_quote_is_shown_as_a_verbatim_excerpt():
    long = ("Из существующих вещей одни находятся в нашей власти, другие нет. В нашей власти мнение, стремление, "
            "желание, уклонение — одним словом все, что является нашим. Вне пределов нашей власти — наше тело, "
            "имущество, доброе имя, государственная карьера, одним словом — все, что не наше. И то, что в нашей "
            "власти, по природе свободно, ничем не сдерживается и не ограничивается.")
    good = "В нашей власти мнение, стремление, желание, уклонение — одним словом все, что является нашим."
    assert verbatim_excerpt(long, good) == good
    assert verbatim_excerpt(long, "В нашей власти наши мысли и наши желания, а всё прочее не наше.") is None  # not verbatim
    lead = lead_excerpt(long)
    assert lead in re.sub(r"\s+", " ", long) and lead.startswith("Из существующих вещей")
    c = check_final_card("C0376", {"main_idea": "Эпиктет делит всё на своё и чужое.",
                                   "applied_insight": "Вы пишете, что хотите быть с ней. Её решение — не ваше.",
                                   "reflection_question": "Что здесь решаю я?", "quote_excerpt": "переписанный текст",
                                   "metaphor_words": []}, SEL, "src", USER, None, long)
    assert c.quote_excerpt == lead  # an invented «excerpt» falls back to the verbatim leading sentences


# ------------------------------------------------------------------ 2. display label


def test_display_label_has_no_service_values(final):
    for f in final:
        label = display_label(f)
        assert label and not re.search(r"[*`]|\(|speaker|по фрагменту|candidate|традиционный корпус|голос", label), (f.id, label)
    by = {f.id: f for f in final}
    assert display_label(by["C0241"]) == "Будда · Амбалаттхикарахуловада сутта · МН 61"
    assert display_label(by["C0281"]) == "Эпиктет · Беседы · I.11"
    assert display_label(by["C0780"]) == "Коран · 2:216"
    assert display_label(by["C0599"]) == "Ветхий Завет · Екклесиаст 9:1–3"


# ------------------------------------------------------------------ 3. feelings, representation, unclear input


def test_feelings_are_capped_at_three_and_reach_the_pipeline(final, tmp_path):
    s = base.session(final, tmp_path, experiences=["Тревогу", "Страх", "Грусть", "Злость", "Вину"])
    assert s.input.experiences == ["Тревогу", "Страх", "Грусть"] and MAX_EXPERIENCES == 3
    assert s.query.experiences == ["Тревогу", "Страх", "Грусть"]  # → selection package and card writer
    view = s.compose()
    assert view["perspectives"]
    assert "Рабочие гипотезы ОБЯЗАТЕЛЬНО учитывают названные чувства" in INTERPRETER_PROMPT
    assert "Переживания (experiences) человек выбрал сам" in SELECTOR_PROMPT
    assert "Чувства, которые человек выбрал" in FINAL_WRITER_PROMPT


def test_representation_keeps_charged_details_and_accepts_partial_input():
    assert "Смысл важнее гладкости" in INTERPRETER_PROMPT and "чувырло" in INTERPRETER_PROMPT
    assert "Строй вопрос только по этой понятной части" in INTERPRETER_PROMPT and "бессмысленные слова из рассказа в вопрос" in INTERPRETER_PROMPT


def test_unclear_input_gets_a_human_message():
    class Gibberish:
        name, model = "scripted", None

        def complete(self, inp, feedback=None):
            return {"sufficient": False, "insufficiency_reason": "бессмысленные слова", "reading_notes": [],
                    "working_hypotheses": [], "proposed_question": "", "coordinates": [], "canonical_tensions": [],
                    "free_tensions": [], "ambiguity_notes": []}, {}

    inp = InterpretationInput(topic="t", experiences=[], difficulty_center="c",
                              free_narrative="Я шабудубу, да, а она мне говорит: нет, ну и как так-то епрст?")
    res = interpret(inp, Gibberish())
    assert isinstance(res, InsufficientInterpretation) and res.clarification_prompt == UNCLEAR_PROMPT
    assert res.reason == "бессмысленные слова"  # the technical reason stays in the trace


# ------------------------------------------------------------------ 4. failures are explained, double submit refused


@pytest.mark.parametrize("err,msg", [
    ("CLI error: {'result': \"You've hit your session limit\", 'api_error_status': 429}", USER_ERROR_LIMIT),
    ("CLI error: {'subtype': 'error'}", USER_ERROR_MODEL),
])
def test_model_failures_get_a_specific_message(err, msg):
    assert user_message_for(RuntimeError(err), "interpret") == msg


def test_second_request_while_one_runs_is_refused(final, tmp_path):
    s = base.session(final, tmp_path)
    gate, done = threading.Event(), threading.Event()
    slow = s.services.composer.complete

    def blocking(pkg, feedback=None):
        gate.wait(5)
        return slow(pkg, feedback)

    s.services.composer.complete = blocking
    t = threading.Thread(target=lambda: (s.compose(), done.set()))
    t.start()
    try:
        for _ in range(100):
            if s._busy.locked():
                break
            threading.Event().wait(0.01)
        with pytest.raises(FlowError) as exc:
            s.compose()
        assert exc.value.user_message == USER_ERROR_BUSY
    finally:
        gate.set()
        t.join(10)
    assert done.is_set() and s.state == "answered"
    assert s.compose()["perspectives"]  # and the session keeps working afterwards

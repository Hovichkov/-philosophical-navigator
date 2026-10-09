"""M3.4.1 perspective quality correction: regression tests for the classes of problems found in the M3.4 outputs.

Code checks what is reliable: the selector's own frame comparison is consistent (a card it places in the frame of a
selected one is not shown; two selected cards cannot open the same frame), an open hypothesis about the person is
written openly and never in the title (the evidence is the verbatim sentence, checked on the text), no added causal
«почему» in the proposed question, no gendered first-person forms when the gender is unknown, the source's images are
not carried onto the person, a «Подробнее» without a new element is short, and the reflection keeps choice / text /
both. Whether the frames are really different and whether a hypothesis was noticed at all is judged by the control
runs. No live model; nothing here is specific to an author or a case."""

from __future__ import annotations

from corpus_snapshot import legacy_card_only

from pathlib import Path

import pytest

import test_m3_3_1_human_language as base
from navigator.composition.composer import SYSTEM_PROMPT, check_selection
from navigator.composition.writer import WRITER_PROMPT
from navigator.interpretation.interpreter import interpret
from navigator.language import gendered_first_person_hits, person_gender
from navigator.models.interpretation import InterpretationInput

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ("не знаю, продолжать заниматься несколькими проектами или сосредоточиться на одном. Если выбирать один, "
            "боюсь не зарабатывать достаточно или что один проект мне наскучит. Если же продолжать несколько "
            "одновременно, боюсь выгореть")

fragments = base.fragments  # module fixture


class FrameSelector(base.Selector):
    """M3.4.1 selection: effects + frames for the selected cards and the model's own verdict on the others."""

    def __init__(self, selected, others=()):
        super().__init__(n=len(selected))
        self.selected, self.others = selected, list(others)  # [(effect, frame)], [(decision, dup_index, effect, frame)]

    def complete(self, pkg, feedback=None):
        out, usage = super().complete(pkg, feedback)
        ids = [p["card_id"] for p in out["perspectives"]]
        for p, (e, f) in zip(out["perspectives"], self.selected):
            p["perspective_effect"], p["perspective_frame"] = e, f
        out.pop("fewer_than_three_reason", None)
        out.pop("rejected", None)
        spare = [c["card_id"] for c in pkg["candidates"] if c["card_id"] not in ids]
        out["considered"] = [{"card_id": i, "perspective_effect": e, "perspective_frame": f, "decision": "selected",
                              "duplicate_of": None, "reason": "сильная"} for i, (e, f) in zip(ids, self.selected)]
        for k, (decision, dup, e, f) in enumerate(self.others):
            out["considered"].append({"card_id": spare[k], "perspective_effect": e, "perspective_frame": f,
                                      "decision": decision, "duplicate_of": ids[dup] if dup is not None else None,
                                      "reason": "см. решение"})
        out["count_reason"] = "минимально достаточно"
        return out, usage


class AuditWriter(base.Writer):
    """Card 0, first attempt: ``fields`` + extra audit entries / internal fields; later attempts are clean."""

    def __init__(self, fields=None, entries=(), internal=None):
        super().__init__()
        self.fields, self.entries, self.internal = fields or {}, list(entries), internal or {}

    def complete(self, brief, feedback=None):
        out, usage = super().complete(brief, feedback)
        self.briefs = getattr(self, "briefs", []) + [brief]
        if brief["различение_карточки"].endswith("(0).") and self.calls[brief["различение_карточки"]] == 1:
            out.update(self.fields)
            out.update(self.internal)
            out["grounding"] = out["grounding"] + self.entries
        return out, usage


def run(fragments, tmp_path, selector=None, writer=None, narrative=base.SON, experiences=None):
    s = base.session(fragments, tmp_path, narrative=narrative, selector=selector, writer=writer, experiences=experiences)
    view = s.compose()
    fb = [f for fs in (writer.feedback.values() if writer else []) for f in fs if f]
    return s, view, fb


def hyp(field, sentence):
    return {"field": field, "claim": sentence, "kind": "open_hypothesis", "evidence": sentence}


# ------------------------------------------------------------------ A. minimum sufficient perspectives


def test_two_strong_and_a_weak_third_gives_two(fragments, tmp_path):
    sel = FrameSelector([("незнание исхода не значит бессилия", "как действовать без гарантий"),
                         ("страх у пути не довод против него", "как соотносятся страх и выбор")],
                        others=[("strained_application", None, "качество важнее количества",
                                 "по какой мерке сравнивать пути")])
    s, view, _ = run(fragments, tmp_path, selector=sel)
    assert len(view["perspectives"]) == 2
    assert any(r.reason.startswith("натянутое применение") for r in s.composition.rejected)


def test_three_independent_frames_give_three(fragments, tmp_path):
    sel = FrameSelector([("незнание исхода не значит бессилия", "как действовать без гарантий"),
                         ("страх у пути не довод против него", "как соотносятся страх и выбор"),
                         ("выбор не обязан быть окончательным", "обязательно ли решать сейчас и навсегда")])
    s, view, _ = run(fragments, tmp_path, selector=sel)
    assert len(view["perspectives"]) == 3
    assert [p.perspective_frame for p in s.composition.perspectives][2] == "обязательно ли решать сейчас и навсегда"
    assert "perspective_frame" not in str(view)


def test_prompt_asks_for_minimum_sufficient_not_a_default_count():
    for needle in ("perspective_frame", "Нужен минимальный достаточный результат: не «обычно 2» и не «обычно 3»",
                   "лежит в той же рамке, что одна из первых", "требует натянутого применения источника"):
        assert needle in SYSTEM_PROMPT, needle
    assert "разных авторов" not in SYSTEM_PROMPT and "НЕ традицией или автором" in SYSTEM_PROMPT


# ------------------------------------------------------------------ B. higher-level diversity


def test_two_effects_in_one_frame_are_one_perspective():
    pkg = {"candidates": [{"card_id": c} for c in ("C0442", "C0296", "C0441")]}
    out = {"perspectives": [
        {"card_id": "C0442", "perspective_effect": "будущее не гарантировано, но от действий зависит многое",
         "perspective_frame": "Как действовать без гарантий.", "distinction": "Помогает различить А и Б", "role": "r",
         "why_selected": "w"},
        {"card_id": "C0296", "perspective_effect": "исход не в моей власти, а суждение — в моей",
         "perspective_frame": "как действовать без гарантий", "distinction": "Помогает различить В и Г", "role": "r",
         "why_selected": "w"}], "count_reason": "две"}
    with pytest.raises(ValueError, match="same perspective_frame"):
        check_selection(pkg, out)
    out["perspectives"][1]["perspective_frame"] = "что в выборе моё, а что нет"
    out["considered"] = [{"card_id": "C0442", "decision": "selected"},
                         {"card_id": "C0296", "decision": "same_frame_as_selected", "duplicate_of": "C0442"}]
    with pytest.raises(ValueError, match="same_frame_as_selected"):
        check_selection(pkg, out)  # the model itself put it in the frame of a selected card


# ------------------------------------------------------------------ C. hypothesis grounding (every field)


@legacy_card_only
@pytest.mark.parametrize("field,sentence", [
    ("applied_insight", "Ваш стыд касается чужой жалости, а не самого события."),
    ("question_explanation", "Можно не винить себя и всё же не хотеть, чтобы другие видели тебя в жалком положении."),
    ("perspective", "Значит, стыдно вам не за сокращение, а за то, как вас пожалеют."),
])
def test_hypothesis_about_a_feeling_is_not_stated_as_fact(field, sentence, fragments, tmp_path):
    fields = {field: sentence} if field != "perspective" else {field: base.written()["perspective"] + " " + sentence}
    w = AuditWriter(fields, [hyp(field, sentence)])
    s, view, fb = run(fragments, tmp_path, writer=w, narrative=base.LAYOFF, experiences=["Растерянность"])
    assert fb and "stated as a fact" in fb[0]
    assert sentence not in str(view)


def test_hypothesis_in_the_title_is_rejected(fragments, tmp_path):
    title = "Стыдно бывает не за событие, а за чужую жалость"
    w = AuditWriter({"title": title}, [hyp("title", title)])
    s, view, fb = run(fragments, tmp_path, writer=w, narrative=base.LAYOFF, experiences=["Растерянность"])
    assert fb and "in the title" in fb[0] and title not in str(view)


@legacy_card_only
def test_open_hypothesis_is_allowed(fragments, tmp_path):
    q = "Относится ли ваш стыд к самому событию или к тому, как его могут увидеть другие?"
    applied = "Вы пишете, что вам стыдно сказать друзьям. Эпиктет предлагает различить само событие и чужой взгляд на него."
    w = AuditWriter({"applied_insight": applied},
                    [hyp("applied_insight", "Эпиктет предлагает различить само событие и чужой взгляд на него."),
                     {"field": "reflection_question", "claim": q, "kind": "question", "evidence": ""}])
    s, view, fb = run(fragments, tmp_path, writer=w, narrative=base.LAYOFF, experiences=["Растерянность"])
    assert not fb and view["perspectives"][0]["applied_insight"] == applied


def test_hypothesis_evidence_must_be_the_real_sentence(fragments, tmp_path):
    w = AuditWriter({"applied_insight": "Ваш стыд касается чужой жалости."},
                    [hyp("applied_insight", "Возможно, ваш стыд касается чужой жалости?")])  # softened only in the audit
    s, view, fb = run(fragments, tmp_path, writer=w, narrative=base.LAYOFF, experiences=["Растерянность"])
    assert fb and "is not found" in fb[0]


# ------------------------------------------------------------------ D. identity grounding


def test_identity_border_is_not_decided_for_the_person(fragments, tmp_path):
    decided = "Место и положение уходят вместе с работой, а человек остаётся."
    w = AuditWriter({"applied_insight": "Вы спрашиваете, кто вы теперь без этой работы. " + decided},
                    [hyp("applied_insight", decided)])
    s, view, fb = run(fragments, tmp_path, writer=w, narrative=base.LAYOFF, experiences=["Растерянность"])
    assert fb and "stated as a fact" in fb[0] and decided not in str(view)
    assert "где проходит граница между «ролью» и «мной»" in WRITER_PROMPT


def test_identity_distinction_may_be_offered_for_exploration(fragments, tmp_path):
    offered = "История Иова предлагает различить то, что давала должность, и то, что вы продолжаете считать своим."
    w = AuditWriter({"applied_insight": "Вы спрашиваете, кто вы теперь без этой работы. " + offered},
                    [hyp("applied_insight", offered)])
    s, view, fb = run(fragments, tmp_path, writer=w, narrative=base.LAYOFF, experiences=["Растерянность"])
    assert not fb


# ------------------------------------------------------------------ E. no causal expansion in the proposed question


def test_feeling_is_not_turned_into_a_why_question():
    why = "Меня сократили, и теперь я не знаю, кто я без этой работы. И почему мне стыдно сказать об этом друзьям?"
    ok = "Меня сократили, и теперь я не знаю, кто я без этой работы. Как быть со стыдом сказать об этом друзьям?"
    it = base.Interp([base.interp_out(why), base.interp_out(ok)])
    res = interpret(InterpretationInput(topic="t", experiences=["Страх"], difficulty_center="c",
                                        free_narrative=base.LAYOFF), it)
    assert res.proposed_question == ok and "causal question" in it.feedback[1]


def test_the_persons_own_why_is_kept():
    asked = base.LAYOFF + " Почему мне стыдно, если я не виноват?"
    q = "Меня сократили, и я не виноват. Почему мне всё равно стыдно сказать друзьям?"
    it = base.Interp([base.interp_out(q)])
    res = interpret(InterpretationInput(topic="t", experiences=["Страх"], difficulty_center="c", free_narrative=asked), it)
    assert res.proposed_question == q and res.trace.attempts == 1


# ------------------------------------------------------------------ F. unknown gender


@legacy_card_only
def test_unknown_gender_forbids_gendered_first_person(fragments, tmp_path):
    assert person_gender(PROJECTS) is None
    w = AuditWriter({"reflection_question": "Что я теряю в каждом пути? Какую из этих потерь я готов нести?"})
    s, view, fb = run(fragments, tmp_path, writer=w, narrative=PROJECTS)
    assert fb and "gender is unknown" in fb[0]
    assert not any(gendered_first_person_hits(p["reflection_question"]) for p in view["perspectives"])
    assert w.briefs[0]["род_человека"] == "неизвестен"


@legacy_card_only
def test_known_gender_and_source_characters_are_not_touched(fragments, tmp_path):
    assert person_gender(base.LAYOFF) == "m"  # «я там был»
    w = AuditWriter({"reflection_question": "Что за 12 лет я считал своим? Что у меня осталось?",
                     "main_idea": "Моисей в какой-то момент прямо говорит, что он готов делить груз. Дело он не бросает."})
    s, view, fb = run(fragments, tmp_path, writer=w, narrative=base.LAYOFF, experiences=["Растерянность"])
    assert not fb
    assert gendered_first_person_hits("Иов говорит, что он готов принять всё") == []


def test_proposed_question_is_neutral_when_gender_unknown():
    bad = "Я веду несколько проектов. Какой путь я готов выбрать, если каждый пугает?"
    ok = "Я веду несколько проектов. Как выбирать, если каждый путь пугает по-своему?"
    it = base.Interp([base.interp_out(bad), base.interp_out(ok)])
    res = interpret(InterpretationInput(topic="t", experiences=["Тревогу"], difficulty_center="c",
                                        free_narrative=PROJECTS), it)
    assert res.proposed_question == ok and "gender is unknown" in it.feedback[1]


# ------------------------------------------------------------------ G. the source's metaphor is not carried over


@legacy_card_only
def test_source_metaphor_is_not_carried_onto_the_person(fragments, tmp_path):
    w = AuditWriter({"main_idea": "Эпикур говорит, что с едой выбирают не самую большую порцию, а самую вкусную.",
                     "reflection_question": "В какие дни работа над проектами мне по вкусу? Что в такие дни иначе?"},
                    internal={"metaphor_words": ["еда", "порция", "вкус"]})
    s, view, fb = run(fragments, tmp_path, writer=w, narrative=PROJECTS)
    assert fb and "image is carried" in fb[0] and "вкус" in fb[0]
    assert "по вкусу" not in view["perspectives"][0]["reflection_question"]


@legacy_card_only
def test_metaphor_may_explain_the_source_itself(fragments, tmp_path):
    w = AuditWriter({"main_idea": "Эпикур говорит, что с едой выбирают не самую большую порцию, а самую вкусную."},
                    internal={"metaphor_words": ["еда", "порция", "вкус"]})
    s, view, fb = run(fragments, tmp_path, writer=w, narrative=PROJECTS)
    assert not fb and "порцию" in view["perspectives"][0]["main_idea"]
    assert "переноси РАЗЛИЧЕНИЕ, а не лексику образа" in WRITER_PROMPT


# ------------------------------------------------------------------ H. «Подробнее»: semantic novelty


@legacy_card_only
def test_detail_without_a_new_element_must_be_short(fragments, tmp_path):
    # different words, same meaning as the card: the writer itself reports no new element → it cannot stay long
    long_paraphrase = ("Эпиктет разводит две вещи. Есть то, что с человеком случилось. И есть то, как это видят другие. "
                       "Это не одно и то же. Одно дело — само событие. Другое — чужой взгляд на него. Их легко спутать, "
                       "но это разные вещи, и Эпиктет просит их не смешивать.")
    w = AuditWriter({"perspective": long_paraphrase}, internal={"detail_new_element": {"kind": "none", "what": "—"}})
    s, view, fb = run(fragments, tmp_path, writer=w, narrative=base.LAYOFF, experiences=["Растерянность"])
    assert fb and "adds nothing new" in fb[0]
    assert view["perspectives"][0]["details"] != long_paraphrase


def test_detail_with_a_new_element_or_short_passes(fragments, tmp_path):
    w = AuditWriter({"perspective": "Эпиктет начинает с самого обстоятельства и потом добавляет к нему чужую жалость."},
                    internal={"detail_new_element": {"kind": "none", "what": "—"}})
    s, view, fb = run(fragments, tmp_path, writer=w)
    assert not fb
    for needle in ("хотя бы один НОВЫЙ смысловой элемент", "Пересказ того же другими словами — не новый элемент"):
        assert needle in WRITER_PROMPT, needle


# ------------------------------------------------------------------ I. reflection: choice, own text, both


@pytest.mark.parametrize("chosen,text", [(0, None), (None, "Вижу, что боюсь не того, о чём думал."), (1, "и ещё вот это")])
def test_reflection_choice_text_or_both(chosen, text, fragments, tmp_path):
    s, view, _ = run(fragments, tmp_path)
    out = s.reflect(chosen, text)
    r = s.debug_view()["reflection"]
    assert s.state == "reflected" and r["chosen_index"] == chosen and r["own_text"] == (text.strip() if text else None)
    assert out["reflection"]["chosen_title"] == (view["perspectives"][chosen]["title"] if chosen is not None else None)


def test_reflection_copy_says_both_are_possible():
    page = (ROOT / "src/navigator/prototype/static/index.html").read_text(encoding="utf-8")
    assert "или сделать и то и другое" in page
    # the button is enabled by a choice OR own text (both together included)
    assert 'reflection.chosen === null && !$("reflection-text").value.trim()' in page

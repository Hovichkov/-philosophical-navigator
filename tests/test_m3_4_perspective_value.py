"""M3.4 perspective value & result flow: regression tests.

What code can check reliably: two cards are a full result (no reason demanded, no retry), the selector's own
effect comparison is consistent (a card it calls the same thinking operation as a selected one is not shown), a
third card with its own effect is kept, «Подробнее» that restates the card is rewritten, titles of works get «» in
prose (not in the reference line), the person's «принять» is not swapped for «смириться», the reflection step keeps
the chosen card / own words, and the onboarding is on the first screen. Whether perspectives are really different
ways of seeing the question is judged by the control runs, not by these tests. No live model."""

from __future__ import annotations

from corpus_snapshot import legacy_card_only

import json
from pathlib import Path

import pytest

import test_m3_3_1_human_language as base
from navigator.composition.composer import SYSTEM_PROMPT, check_selection
from navigator.composition.writer import WRITER_PROMPT
from navigator.interpretation.interpreter import interpret
from navigator.language import quote_work_titles, retold_sentences
from navigator.models.interpretation import InterpretationInput
from navigator.prototype.flow import NEXT_ROUND, FlowError

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ("не знаю, продолжать заниматься несколькими проектами или сосредоточиться на одном. Если выбирать один, "
            "боюсь не зарабатывать достаточно или что один проект мне наскучит. Если же продолжать несколько "
            "одновременно, боюсь выгореть")

fragments = base.fragments  # module fixture


class EffectSelector(base.Selector):
    """Selection with explicit perspective effects and the model's own comparison of candidates (M3.4 format)."""

    def __init__(self, effects, considered_extra=(), count_reason="причина числа"):
        super().__init__(n=len(effects))
        self.effects, self.extra, self.count_reason = effects, list(considered_extra), count_reason

    def complete(self, pkg, feedback=None):
        out, usage = super().complete(pkg, feedback)
        ids = [p["card_id"] for p in out["perspectives"]]
        for p, e in zip(out["perspectives"], self.effects):
            p["perspective_effect"] = e
        out.pop("fewer_than_three_reason", None)
        out.pop("rejected", None)
        pool = [c["card_id"] for c in pkg["candidates"]]
        spare = [c for c in pool if c not in ids]
        out["considered"] = [{"card_id": i, "perspective_effect": e, "decision": "selected", "duplicate_of": None,
                              "reason": "сильная"} for i, e in zip(ids, self.effects)]
        for k, (decision, dup_index) in enumerate(self.extra):
            out["considered"].append({"card_id": spare[k], "perspective_effect": self.effects[dup_index or 0],
                                      "decision": decision, "duplicate_of": ids[dup_index] if dup_index is not None else None,
                                      "reason": "то же, что выбранная"})
        out["count_reason"] = self.count_reason
        return out, usage


def run(fragments, tmp_path, selector=None, writer=None, narrative=base.SON):
    s = base.session(fragments, tmp_path, narrative=narrative, selector=selector, writer=writer)
    return s, s.compose()


# ------------------------------------------------------------------ 1–4. number of cards, duplicates by effect


def test_two_cards_are_a_full_result_without_justification(fragments, tmp_path):
    sel = EffectSelector(["отсутствие гарантии не делает действие бессмысленным",
                          "разные опасения получают вес из разных ценностей"], count_reason="")
    s, view = run(fragments, tmp_path, selector=sel)
    assert len(view["perspectives"]) == 2 and sel.calls == 1  # no repair demanded for returning two
    assert s.composition.schema_version == "composition/0.5.0" and s.composition.meta.usage["repairs"] == []
    assert "Никакого бонуса за количество нет" in SYSTEM_PROMPT and "полноценный хороший результат" in SYSTEM_PROMPT
    assert "Верни 3, только если" not in SYSTEM_PROMPT  # 3 is no longer the default with 2 as an exception


def test_semantic_duplicate_is_not_added_as_third(fragments, tmp_path):
    # the selector itself marks the third candidate as the same thinking operation as a selected card
    sel = EffectSelector(["отсутствие гарантии не делает действие бессмысленным",
                          "разные опасения получают вес из разных ценностей"],
                         considered_extra=[("same_operation_as_selected", 0)])
    s, view = run(fragments, tmp_path, selector=sel)
    assert len(view["perspectives"]) == 2
    dup = [r for r in s.composition.rejected if r.reason.startswith("та же мыслительная операция")]
    assert dup and s.composition.perspectives[0].card_id in dup[0].reason


def test_different_sources_with_the_same_effect_compete():
    pkg = {"candidates": [{"card_id": c} for c in ("C0442", "C0296", "C0345")]}
    same = "неизвестность будущего переводит внимание на то, что зависит от человека"
    out = {"perspectives": [
        {"card_id": "C0442", "perspective_effect": same, "distinction": "Помогает различить А и Б", "role": "r",
         "why_selected": "w"},
        {"card_id": "C0296", "perspective_effect": same.capitalize() + ".", "distinction": "Помогает различить В и Г",
         "role": "r", "why_selected": "w"}], "count_reason": "две"}
    with pytest.raises(ValueError, match="same perspective_effect"):
        check_selection(pkg, out)  # Epicurus and Epictetus doing one job are not two perspectives
    out["perspectives"][1]["perspective_effect"] = "разные опасения получают вес из разных ценностей"
    out["considered"] = [{"card_id": "C0442", "decision": "selected"},
                         {"card_id": "C0296", "decision": "same_operation_as_selected", "duplicate_of": "C0442"}]
    with pytest.raises(ValueError, match="marked «same_operation_as_selected»"):
        check_selection(pkg, out)  # the model's own comparison says duplicate: it cannot be shown


def test_third_card_with_its_own_effect_is_kept(fragments, tmp_path):
    sel = EffectSelector(["отсутствие гарантии не делает действие бессмысленным",
                          "разные опасения получают вес из разных ценностей",
                          "выбор не обязан быть окончательным прямо сейчас"],
                         count_reason="третья даёт самостоятельный эффект")
    s, view = run(fragments, tmp_path, selector=sel)
    assert len(view["perspectives"]) == 3 and s.composition.count_reason == "третья даёт самостоятельный эффект"
    assert [p.perspective_effect for p in s.composition.perspectives][2] == "выбор не обязан быть окончательным прямо сейчас"
    assert "perspective_effect" not in json.dumps(view, ensure_ascii=False)  # internal field


# ------------------------------------------------------------------ 5–6. «Подробнее» deepens, «Что имеется в виду?» clarifies


@legacy_card_only
def test_detail_that_retells_the_card_is_rewritten(fragments, tmp_path):
    c = base.written()
    retell = " ".join([c["main_idea"], c["applied_insight"]])  # «Подробнее» = the card again
    w = base.Writer(bad={0: {"perspective": retell}})
    s, view = run(fragments, tmp_path, writer=w)
    fb = [f for fs in w.feedback.values() for f in fs if f]
    assert fb and "repeats the card" in fb[0]
    assert all(p["details"] != retell for p in view["perspectives"])


@legacy_card_only
def test_explanation_and_detail_have_different_functions(fragments, tmp_path):
    c = base.written()
    w = base.Writer(bad={0: {"question_explanation": "Речь о простых делах рядом с сыном. Например, обычный день.",
                             "perspective": "Речь о простых делах рядом с сыном. Например, обычный день. " + c["perspective"]}})
    s, view = run(fragments, tmp_path, writer=w)
    fb = [f for fs in w.feedback.values() for f in fs if f]
    assert fb and "repeats the card" in fb[0]
    for needle in ("ПОЯСНЕНИЕ для того, кому мысль карточки показалась непонятной",
                   "УГЛУБЛЕНИЕ для того, кому интересно, почему из источника вообще следует такая мысль",
                   "не повторяй «Что имеется в виду?»", "пиши КОРОЧЕ"):
        assert needle in WRITER_PROMPT, needle
    assert retold_sentences("Эпиктет считает иначе и объясняет почему, шаг за шагом.", c["main_idea"]) == []


# ------------------------------------------------------------------ 7–9. titles of works, reference line, quotes


@legacy_card_only
def test_titles_of_works_are_quoted_in_prose(fragments, tmp_path):
    w = base.Writer(bad={0: {"main_idea": "В Бхагавад-гите есть мысль, что трудно отличить действие от бездействия.",
                             "perspective": "Гита не делит поступки на хорошие и плохие. Эпиктет в Беседах думает о "
                                            "другом, а Дао дэ цзин — о третьем. Коран здесь не упоминается."}})
    s, view = run(fragments, tmp_path, writer=w)
    p = view["perspectives"][0]
    assert "В «Бхагавад-гите» есть мысль" in p["main_idea"]
    assert p["details"].startswith("«Гита» не делит") and "в «Беседах»" in p["details"] and "«Дао дэ цзин»" in p["details"]
    assert "Коран здесь" in p["details"]  # sacred scriptures are not put in quotes
    assert quote_work_titles("в «Бхагавад-гите»") == "в «Бхагавад-гите»"  # never double-quoted
    assert quote_work_titles("после беседы с сыном") == "после беседы с сыном"  # the ordinary word stays


@legacy_card_only
def test_reference_line_is_not_changed(fragments, tmp_path):
    s, view = run(fragments, tmp_path)
    for p in view["perspectives"]:
        assert "«" not in p["source"]
        f = next(f for f in fragments if f.id in {x.card_id for x in s.composition.perspectives} and
                 s._reference(next(x for x in s.composition.perspectives if x.card_id == f.id)) == p["source"])
        assert f is not None


def test_verified_quote_state_is_unchanged(fragments, tmp_path):
    w = base.Writer(extra={"quote": "«цитата по памяти»"})
    s, view = run(fragments, tmp_path, writer=w)
    assert all(p.verified_quote is None for p in s.composition.perspectives)
    assert "цитата по памяти" not in json.dumps(view, ensure_ascii=False)
    inv = json.loads((ROOT / "data/quotes/QUOTE-READINESS-INVENTORY.json").read_text(encoding="utf-8"))
    assert inv["counts"] == {"READY": 0, "PARTIAL": 66, "NOT_READY": 47}  # M3.3 audit unchanged
    assert not [c for c in inv["cards"].values() if c["category"] == "READY"]


# ------------------------------------------------------------------ 10. M3.3.2 grounding stays


def test_grounding_of_m3_3_2_still_applies(fragments, tmp_path):
    claim = "Например, умение договариваться с людьми осталось у вас."
    w = base.Writer(bad={0: {"question_explanation": claim, "grounding": [
        {"field": "question_explanation", "claim": claim, "kind": "user_fact", "evidence": "умею договариваться"}]}})
    s, view = run(fragments, tmp_path, writer=w, narrative=base.LAYOFF)
    fb = [f for fs in w.feedback.values() for f in fs if f]
    assert fb and "not in the person's own words" in fb[0]
    assert "ПРОИСХОЖДЕНИЕ КАЖДОГО УТВЕРЖДЕНИЯ" in WRITER_PROMPT


# ------------------------------------------------------------------ 11–12. the person's words; one part of a question


def test_accept_is_not_turned_into_resign_in_the_proposed_question():
    bad = "С сыном происходит то, что было и у меня. Как быть рядом с ним, если мне трудно смириться с этим?"
    it = base.Interp([base.interp_out(bad), base.interp_out(base.GOOD_Q)])
    res = interpret(InterpretationInput(topic="t", experiences=[], difficulty_center=
                                        "Мне трудно принять происходящее таким, какое оно сейчас есть",
                                        free_narrative=base.SON), it)
    assert res.proposed_question == base.GOOD_Q and "принять" in it.feedback[1]


def test_accept_is_not_turned_into_resign_in_the_card(fragments, tmp_path):
    w = base.Writer(bad={0: {"applied_insight": "Вы пишете, что вам трудно смириться. Но не всякое действие помогает."}})
    s, view = run(fragments, tmp_path, writer=w)  # the confirmed question says «трудно принять»
    fb = [f for fs in w.feedback.values() for f in fs if f]
    assert fb and "near-synonym" in fb[0]


def test_a_card_may_work_with_one_part_of_the_question(fragments, tmp_path):
    assert "Карточка может работать с одной важной частью вопроса" in WRITER_PROMPT
    assert "не требуй от неё охватить весь вопрос" in SYSTEM_PROMPT
    # a card that speaks only to the first part of a two-part question passes every check
    w = base.Writer(bad={0: {"applied_insight": "Вы пишете, что хочется запретить. Хотеть запретить ещё не значит запрещать."}})
    s, view = run(fragments, tmp_path, writer=w)
    assert all(r["attempts"] == 1 for r in s.composition.meta.usage["writer"]["cards"])


# ------------------------------------------------------------------ 13–15. reflection state and onboarding


def test_reflection_keeps_the_chosen_perspective(fragments, tmp_path):
    s, view = run(fragments, tmp_path)
    out = s.reflect(1, None)
    r = s.debug_view()["reflection"]
    assert s.state == "reflected" and r["chosen_index"] == 1
    assert r["chosen_card_id"] == s.composition.perspectives[1].card_id and r["chosen_title"] == view["perspectives"][1]["title"]
    assert r["question"] == view["confirmed_question"] and r["shown_perspectives"] == view["perspectives"]
    assert out["reflection"]["next"] == NEXT_ROUND and out["perspectives"] == view["perspectives"]


def test_reflection_keeps_own_text(fragments, tmp_path):
    s, view = run(fragments, tmp_path)
    s.reflect(None, "  Я вижу, что хочу запретить не ради сына.  ")
    r = s.debug_view()["reflection"]
    assert r["own_text"] == "Я вижу, что хочу запретить не ради сына." and r["chosen_index"] is None
    s.reflect(0, "и ещё первая мысль")  # can be changed; both are kept together
    assert s.reflection["chosen_index"] == 0 and s.reflection["own_text"] == "и ещё первая мысль"
    with pytest.raises(FlowError):
        s.reflect(None, "   ")
    with pytest.raises(FlowError):
        s.reflect(7, None)


def test_onboarding_is_the_first_screen_of_a_new_flow():
    page = (ROOT / "src/navigator/prototype/static/index.html").read_text(encoding="utf-8")
    start = page.index('id="s-start"')
    assert '<section class="screen active" id="s-start">' in page  # shown first
    first = page[start:page.index("</section>", start)]
    for needle in ("Здесь не будет совета, как правильно поступить", "точнее сформулировать ваш вопрос",
                   "философские и духовные тексты", "могут различаться и даже противоречить",
                   "выбрать мысль, с которой хочется продолжить", ">Начать<"):
        assert needle in first, needle
    for needle in ("Что изменилось в вашем вопросе?", "Продолжить разбор", "/api/reflect"):
        assert needle in page, needle

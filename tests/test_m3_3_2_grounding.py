"""M3.3.2 grounding correction: regression tests for the CLASSES of made-up claims found in the M3.3.1 control run.

The writer lists every claim about the person, another person from their story or the source with its provenance
(user_fact / source_fact / distinction / question / impersonal_example). Code checks what can be checked reliably:
user facts and source facts must quote the person's words / the corpus card data verbatim, an inference may stand
only as a question. Whether the audit is complete and honest is judged by the real control runs, not by these tests.
No live model."""

from __future__ import annotations

from corpus_snapshot import legacy_card_only

import json

import pytest

import test_m3_3_1_human_language as base
from navigator.composition.writer import WRITER_PROMPT, WRITER_SCHEMA, grounding_problems
from navigator.interpretation.interpreter import SYSTEM_PROMPT as INTERPRETATION_PROMPT

TEACHER = ("Я шакольный учитель. У меня есть ученик с дцп, но дееспособный. И он отказывается участвовать в работе. "
           "Все время себя самоуничижает. Я хочу ему помочь, пытаюсь включить в рабочий процесс, но он идет в отказ")

fragments = base.fragments  # module fixture


class AuditWriter(base.Writer):
    """Card 0 gets ``fields`` and extra audit ``entries`` on its first attempt; later attempts are clean."""

    def __init__(self, fields=None, entries=(), drop_kinds=()):
        super().__init__()
        self.fields, self.entries, self.drop_kinds = fields or {}, list(entries), set(drop_kinds)

    def complete(self, brief, feedback=None):
        out, usage = super().complete(brief, feedback)
        first_of_card0 = brief["различение_карточки"].endswith("(0).") and self.calls[brief["различение_карточки"]] == 1
        if first_of_card0:
            out.update(self.fields)
            out["grounding"] = [e for e in out["grounding"] if e["kind"] not in self.drop_kinds] + self.entries
        return out, usage


def run(fragments, tmp_path, writer, narrative=base.SON, experiences=None):
    s = base.session(fragments, tmp_path, narrative=narrative, writer=writer, experiences=experiences)
    view = s.compose()
    fb = [f for fs in writer.feedback.values() for f in fs if f]
    return s, view, fb


def entry(field, claim, kind, evidence=""):
    return {"field": field, "claim": claim, "kind": kind, "evidence": evidence}


# ------------------------------------------------------------------ 1–2. third persons: no new motive, no inner choice


def test_third_person_motive_is_not_stated_as_fact(fragments, tmp_path):
    claim = "Ученик отказывается, потому что не видит смысла в заданиях."
    w = AuditWriter({"applied_insight": claim}, [entry("applied_insight", claim, "new_inference")])
    s, view, fb = run(fragments, tmp_path, w, narrative=TEACHER)
    assert fb and "new inference stated as a fact" in fb[0]
    assert claim not in json.dumps(view, ensure_ascii=False)


@pytest.mark.parametrize("kind,evidence,reason", [
    ("new_inference", "", "new inference stated as a fact"),
    ("user_fact", "его отказ это его выбор", "not in the person's own words"),  # passed off as the user's words
])
def test_third_person_free_choice_is_not_stated_as_fact(kind, evidence, reason, fragments, tmp_path):
    claim = "Его «нет» и его слова о себе — уже его выбор."
    w = AuditWriter({"perspective": base.written()["perspective"] + " " + claim},
                    [entry("perspective", claim, kind, evidence)])
    s, view, fb = run(fragments, tmp_path, w, narrative=TEACHER)
    assert fb and reason in fb[0]
    assert claim not in json.dumps(view, ensure_ascii=False)


# ------------------------------------------------------------------ 3–5. the person: no ability, no scene, no advice


@pytest.mark.parametrize("kind,evidence,reason", [
    ("user_fact", "умею договариваться с людьми", "not in the person's own words"),
    ("impersonal_example", "", "not impersonal"),
])
def test_unnamed_ability_of_the_person(kind, evidence, reason, fragments, tmp_path):
    claim = "Например, умение договариваться с людьми осталось у вас."
    w = AuditWriter({"question_explanation": claim}, [entry("question_explanation", claim, kind, evidence)])
    s, view, fb = run(fragments, tmp_path, w, narrative=base.LAYOFF, experiences=["Растерянность"])
    assert fb and reason in fb[0]
    assert claim not in json.dumps(view, ensure_ascii=False)


def test_invented_everyday_scene_is_not_a_fact(fragments, tmp_path):
    claim = "Например, что вы говорите ему за ужином."
    w = AuditWriter({"question_explanation": "Речь о ваших словах рядом с сыном. " + claim},
                    [entry("question_explanation", claim, "user_fact", "говорю ему за ужином")])
    s, view, fb = run(fragments, tmp_path, w)
    assert fb and "not in the person's own words" in fb[0]
    assert "за ужином" not in json.dumps(view, ensure_ascii=False)


def test_new_behaviour_option_is_not_offered(fragments, tmp_path):
    claim = "Можно пока ничего не говорить сыну о проблеме."
    w = AuditWriter({"perspective": base.written()["perspective"] + " " + claim},
                    [entry("perspective", claim, "new_inference")])
    s, view, fb = run(fragments, tmp_path, w)
    assert fb and "new inference stated as a fact" in fb[0]
    assert claim not in view["copy_text"]


# ------------------------------------------------------------------ 6. expandable fields: same grounding rules


@pytest.mark.parametrize("field", ["question_explanation", "perspective", "reflection_question", "main_idea", "title"])
def test_every_user_field_goes_through_grounding(field, fragments, tmp_path):
    claim = "У сына свои причины и свои мысли"
    w = AuditWriter(entries=[entry(field, claim, "new_inference")])
    s, view, fb = run(fragments, tmp_path, w)
    assert fb and "new inference" in fb[0] and f"({field})" in fb[0]
    assert set(WRITER_SCHEMA["properties"]["grounding"]["items"]["properties"]["field"]["enum"]) == set(
        base.written()) - {"grounding"}


# ------------------------------------------------------------------ 7. the source is not extended from model memory


def test_source_knowledge_from_memory_is_rejected(fragments, tmp_path):
    claim = "Эпикур писал о том, как жить без лишней тревоги."
    w = AuditWriter({"perspective": claim + " " + base.written()["perspective"]},
                    [entry("perspective", claim, "source_fact", "как жить без лишней тревоги")])
    s, view, fb = run(fragments, tmp_path, w)
    assert fb and "not in the card data" in fb[0]
    assert claim not in json.dumps(view, ensure_ascii=False)


def test_source_explanation_must_rest_on_card_data(fragments, tmp_path):
    w = AuditWriter(drop_kinds={"source_fact"})
    s, view, fb = run(fragments, tmp_path, w)
    assert fb and "no source_fact" in fb[0]


def test_selector_retelling_is_not_a_ground_for_the_source():
    """Only the corpus card data counts; the selector's own retelling of the source does not."""
    audit = [entry("main_idea", "Лао-цзы часто говорит о слабом.", "source_fact", "часто говорит о слабом"),
             entry("applied_insight", "Вы пишете, что сына сократили", "user_fact", "меня сократили")]
    problems = grounding_problems(audit, base.LAYOFF, "Дао дэ цзин, глава 22 согнутое сохраняется, пустое наполняется")
    assert len(problems) == 1 and "not in the card data" in problems[0]


# ------------------------------------------------------------------ 8. the person's own words are kept


@legacy_card_only
def test_facts_given_by_the_person_are_not_treated_as_inventions(fragments, tmp_path):
    own = [entry("applied_insight", "Вы сами пишете, что пойдёте к неврологу.", "user_fact", "я пойду к неврологу"),
           entry("question_explanation", "Вы пишете, что у вас в детстве тоже было такое.", "user_fact",
                 "У меня тоже в детстве было такое"),  # case and punctuation differ from the story: still found
           entry("applied_insight", "Вам трудно принять происходящее.", "user_fact", "трудно принять")]
    w = AuditWriter({"applied_insight": "Вы сами пишете, что пойдёте к неврологу. Запретить — не единственный путь."},
                    own)
    s, view, fb = run(fragments, tmp_path, w)
    assert not fb and all(r["attempts"] == 1 for r in s.composition.meta.usage["writer"]["cards"])
    assert "неврологу" in view["perspectives"][0]["applied_insight"]


# ------------------------------------------------------------------ 9. a distinction may become a question, not a fact


@legacy_card_only
def test_hypothesis_may_stand_as_a_question(fragments, tmp_path):
    q = "Что в его отказе вы считаете его собственным решением, а что связываете с обстоятельствами?"
    w = AuditWriter({"reflection_question": q},
                    [entry("reflection_question", q, "question"),
                     entry("perspective", "Признать предел ещё не значит сдаться.", "distinction")])
    s, view, fb = run(fragments, tmp_path, w, narrative=TEACHER)
    assert not fb and view["perspectives"][0]["reflection_question"] == q


def test_writer_own_new_inference_label_is_always_rejected():
    """Even phrased as a question in the audit, a claim the writer itself calls a new inference is not shown."""
    audit = [entry("applied_insight", "Вы пишете, что сократили", "user_fact", "меня сократили"),
             entry("main_idea", "Иов теряет имущество", "source_fact", "Иов в один день теряет имущество"),
             entry("perspective", "Разве его отказ не его решение?", "new_inference")]
    problems = grounding_problems(audit, base.LAYOFF, "Иов в один день теряет имущество и детей")
    assert len(problems) == 1 and "new inference" in problems[0]


# ------------------------------------------------------------------ 10. invariants of M3.3.1 stay green


def test_audit_is_internal_and_the_pipeline_is_unchanged(fragments, tmp_path):
    sel = base.Selector()
    w = AuditWriter(entries=[entry("perspective", "Сын думает, что его не любят.", "new_inference")])
    s = base.session(fragments, tmp_path, selector=sel, writer=w)
    view = s.compose()
    assert sel.calls == 1 and sorted(w.calls.values()) == [1, 1, 2]  # two steps; only the failing card rewritten
    assert "grounding" not in json.dumps(view, ensure_ascii=False) and "user_fact" not in view["copy_text"]
    cards = s.composition.meta.usage["writer"]["cards"]
    assert all(c.get("grounding") for c in cards)  # the audit is kept in the trace for review
    assert all(p.verified_quote is None for p in s.composition.perspectives)


def test_prompts_carry_the_provenance_rule():
    for needle in ("ПРОИСХОЖДЕНИЕ КАЖДОГО УТВЕРЖДЕНИЯ", "user_fact", "source_fact", "impersonal_example",
                   "не придумывай бытовых сцен", "не предлагай от себя вариантов поведения", "«свободный выбор»",
                   "Его собственные слова — не домысел", "«Лао-цзы часто говорит…»"):
        assert needle in WRITER_PROMPT, needle
    assert "Не добавляй новых фактов ни о человеке, ни о других людях" in INTERPRETATION_PROMPT

"""M3.4.2 independent grounding validation: regression tests.

The semantic judgement is made by a separate model call (``grounding_validator``); here it is replaced by a scripted
validator that labels sentences the way the prompt asks. What these tests pin down is the MECHANISM: the validator
sees only the person's words, the source material and the final text of all six fields (never the writer's audit), a
violation anywhere — «Подробнее» included — sends only that card back to the writer with the exact sentence and its
type, open formulations pass, and the deterministic checks (invented horizon, «… предложил бы») work on their own.
Whether the real validator notices a hidden hypothesis is shown by the control runs. No live model."""

from __future__ import annotations

from corpus_snapshot import legacy_card_only

import json

import pytest

import test_m3_3_1_human_language as base
from navigator.composition.grounding_validator import (
    VALIDATOR_PROMPT,
    VIOLATIONS,
    validation_material,
    violations_of,
)
from navigator.composition.writer import WRITER_PROMPT
from navigator.composition.composer import SYSTEM_PROMPT
from navigator.language import author_simulation_hits, invented_horizon_hits

fragments = base.fragments  # module fixture


class ScriptedValidator:
    """Labels a sentence by the first matching rule (substring → label); everything else is fine."""
    name, model = "scripted", None

    def __init__(self, rules=()):
        self.rules, self.calls, self.seen = list(rules), 0, []

    def complete(self, material):
        self.calls += 1
        self.seen.append(material)
        text = material["текст_карточки"]
        names = {"заголовок": "title", "что говорит источник": "main_idea", "применение к вопросу": "applied_insight",
                 "вопрос к себе": "reflection_question", "«Что имеется в виду?»": "question_explanation",
                 "«Подробнее»": "perspective"}
        out = []
        for ru, field in names.items():
            for sent in [x for x in __import__("re").split(r"(?<=[.!?…])\s+", text[ru]) if x.strip()]:
                label = next((lab for sub, lab in self.rules if sub in sent), "source_frame")
                out.append({"field": field, "sentence": sent, "label": label, "reason": "scripted"})
        return {"sentences": out}, {"output_tokens": 1}


class AuditWriter(base.Writer):
    """Card 0 first attempt gets ``fields`` (and optionally a self-report that claims no hypothesis at all)."""

    def __init__(self, fields=None, self_report=None):
        super().__init__()
        self.fields, self.self_report = fields or {}, self_report

    def complete(self, brief, feedback=None):
        out, usage = super().complete(brief, feedback)
        if brief["различение_карточки"].endswith("(0).") and self.calls[brief["различение_карточки"]] == 1:
            out.update(self.fields)
            if self.self_report is not None:
                out["grounding"] = out["grounding"] + self.self_report
        return out, usage


def run(fragments, tmp_path, writer, validator, narrative=base.LAYOFF, experiences=("Растерянность",)):
    svc_writer = writer
    s = base.session(fragments, tmp_path, narrative=narrative, writer=svc_writer, experiences=list(experiences))
    s.services.validator = validator
    view = s.compose()
    fb = [f for fs in writer.feedback.values() for f in fs if f]
    return s, view, fb


SHAME_FACT = "Ваш стыд связан с тем, как вас увидят друзья."


# ------------------------------------------------------------------ A, J. hidden hypothesis; self-report independence


@legacy_card_only
def test_hidden_hypothesis_is_caught_by_the_independent_validator(fragments, tmp_path):
    w = AuditWriter({"applied_insight": "Вы пишете, что друзьям сказать стыдно. " + SHAME_FACT})
    v = ScriptedValidator([(SHAME_FACT, "hypothesis_as_fact")])
    s, view, fb = run(fragments, tmp_path, w, v)
    assert fb and SHAME_FACT in fb[0] and "гипотеза о человеке подана как факт" in fb[0]
    assert SHAME_FACT not in json.dumps(view, ensure_ascii=False)


@legacy_card_only
def test_writer_self_report_saying_no_hypothesis_does_not_matter(fragments, tmp_path):
    # KEY TEST: the writer calls the sentence a general distinction; the text states HYPOTHESIS → FACT.
    sentence = "Отсюда понятно, как стыд обходится без вины: он откликается не на поступок, а на перемену в чужом взгляде."
    w = AuditWriter({"perspective": base.written()["perspective"] + " " + sentence},
                    self_report=[{"field": "perspective", "claim": sentence, "kind": "distinction", "evidence": ""}])
    v = ScriptedValidator([("откликается не на поступок", "hypothesis_as_fact")])
    s, view, fb = run(fragments, tmp_path, w, v)
    assert fb and "откликается не на поступок" in fb[0]
    assert sentence not in json.dumps(view, ensure_ascii=False)
    for m in v.seen:  # the validator never sees the writer's audit or the selector's reasoning
        dumped = json.dumps(m, ensure_ascii=False)
        assert "distinction" not in dumped and "grounding" not in dumped and "kind" not in dumped
        assert set(m) == {"слова_человека", "материал_источника", "текст_карточки"}


# ------------------------------------------------------------------ B, C. open hypothesis and source distinction pass


@legacy_card_only
def test_open_hypothesis_and_source_distinction_pass(fragments, tmp_path):
    open_h = "Можно проверить, связан ли стыд с тем, как вы представляете разговор с друзьями."
    frame = "Лао-цзы связывает почёт и унижение с зависимостью от чужого отношения."
    w = AuditWriter({"applied_insight": "Вы пишете, что друзьям сказать стыдно. " + open_h, "main_idea": frame})
    v = ScriptedValidator([(open_h, "open_hypothesis"), (frame, "source_frame")])
    s, view, fb = run(fragments, tmp_path, w, v)
    assert not fb and view["perspectives"][0]["main_idea"] == frame
    assert all(len(c["validation"]) == 1 for c in s.composition.meta.usage["writer"]["cards"])


# ------------------------------------------------------------------ D. identity


@legacy_card_only
def test_identity_decided_for_the_person_fails_and_open_distinction_passes(fragments, tmp_path):
    decided = "Работа была вашей ролью, но не частью вас."
    w = AuditWriter({"applied_insight": "Вы спрашиваете, кто вы теперь без работы. " + decided})
    v = ScriptedValidator([(decided, "identity_decided")])
    s, view, fb = run(fragments, tmp_path, w, v)
    assert fb and "кто я" in fb[0] and decided not in json.dumps(view, ensure_ascii=False)
    offered = "История Иова предлагает различить то, что давала должность, и то, что вы продолжаете считать своим."
    w2 = AuditWriter({"applied_insight": "Вы спрашиваете, кто вы теперь без работы. " + offered})
    s2, view2, fb2 = run(fragments, tmp_path / "2", w2, ScriptedValidator([(offered, "open_hypothesis")]))
    assert not fb2
    assert "«кто я» — особо строго" in WRITER_PROMPT.replace("«Кто я»", "«кто я»")


# ------------------------------------------------------------------ E. invented horizon (deterministic)


@legacy_card_only
def test_invented_horizon_fails_unless_the_person_named_it(fragments, tmp_path):
    q = "Что произойдёт с каждым вариантом через год? Что из этого мне важнее?"
    w = AuditWriter({"reflection_question": q})
    s, view, fb = run(fragments, tmp_path, w, ScriptedValidator())
    assert fb and "invented time horizon" in fb[0]
    assert invented_horizon_hits(q, base.LAYOFF + " Через год я хочу понять, куда иду.") == []
    assert invented_horizon_hits("На следующей неделе будет яснее.", base.LAYOFF) == ["На следующей неделе"]


# ------------------------------------------------------------------ F. historical-author simulation


@legacy_card_only
def test_author_speaking_to_the_person_fails(fragments, tmp_path):
    w = AuditWriter({"applied_insight": "Вы спрашиваете о своих проектах. Конфуций предложил бы вам спросить, ради чего они."})
    s, view, fb = run(fragments, tmp_path, w, ScriptedValidator())
    assert fb and "author is made to speak" in fb[0]
    assert author_simulation_hits("Это различение позволяет спросить, ради чего эти дела.") == []
    assert "author_simulation" in VIOLATIONS and "предложил бы" in VALIDATOR_PROMPT


# ------------------------------------------------------------------ G. emotional prescription


@legacy_card_only
def test_emotional_prescription_fails(fragments, tmp_path):
    sentence = "Можно спокойно принять эту потерю и разобраться в ней."
    w = AuditWriter({"perspective": base.written()["perspective"] + " " + sentence})
    v = ScriptedValidator([("спокойно принять", "emotional_prescription")])
    s, view, fb = run(fragments, tmp_path, w, v)
    assert fb and "как человеку следует чувствовать" in fb[0] and sentence not in json.dumps(view, ensure_ascii=False)


# ------------------------------------------------------------------ H. question to self: no forced choice


@legacy_card_only
def test_forced_choice_question_is_rewritten(fragments, tmp_path):
    q = "За что именно мне стыдно перед друзьями? За мои поступки или за то, что у меня больше нет прежнего места?"
    w = AuditWriter({"reflection_question": q})
    v = ScriptedValidator([("За мои поступки или за то", "forced_choice")])
    s, view, fb = run(fragments, tmp_path, w, v)
    assert fb and "закрывает другие" in fb[0]
    assert view["perspectives"][0]["reflection_question"] != q
    assert "Вопрос к себе проверяет гипотезу открыто" in WRITER_PROMPT


# ------------------------------------------------------------------ I. «Подробнее» only


@legacy_card_only
def test_violation_only_inside_the_detail_is_caught(fragments, tmp_path):
    sentence = "Значит, стыдно вам именно из-за чужой жалости."
    w = AuditWriter({"perspective": base.written()["perspective"] + " " + sentence})
    v = ScriptedValidator([(sentence, "hypothesis_as_fact")])
    s, view, fb = run(fragments, tmp_path, w, v)
    assert fb and "«Подробнее»" in fb[0]
    assert all(sentence not in p["details"] for p in view["perspectives"])
    # the validator is given all six fields, not only the application
    assert set(v.seen[0]["текст_карточки"]) == {"заголовок", "что говорит источник", "применение к вопросу",
                                                  "вопрос к себе", "«Что имеется в виду?»", "«Подробнее»"}


# ------------------------------------------------------------------ targeted rewrite, limits, internal fields


@legacy_card_only
def test_only_the_failing_card_is_rewritten_and_revalidated(fragments, tmp_path):
    sel = base.Selector()
    w = AuditWriter({"applied_insight": "Вы пишете, что друзьям сказать стыдно. " + SHAME_FACT})
    v = ScriptedValidator([(SHAME_FACT, "hypothesis_as_fact")])
    s = base.session(fragments, tmp_path, narrative=base.LAYOFF, selector=sel, writer=w, experiences=["Растерянность"])
    s.services.validator = v
    s.compose()
    cards = s.composition.meta.usage["writer"]["cards"]
    assert sel.calls == 1 and sorted(w.calls.values()) == [1, 1, 2]
    assert sorted(len(c["validation"]) for c in cards) == [1, 1, 2]  # the rewritten card is validated again
    assert any(t["stage"].startswith("independent validation") for t in s.timings)


@legacy_card_only
def test_card_that_keeps_failing_is_dropped_after_the_limit(fragments, tmp_path):
    class AlwaysBad(ScriptedValidator):
        def complete(self, material):
            out, u = super().complete(material)
            if material["текст_карточки"]["заголовок"].startswith("Признать"):  # card 0 in every attempt
                out["sentences"][0]["label"] = "hypothesis_as_fact"
            return out, u

    w = base.Writer()
    s, view, fb = run(fragments, tmp_path, w, AlwaysBad(), narrative=base.SON, experiences=("Беспомощность",))
    assert len(view["perspectives"]) == 2 and s.composition.meta.usage["writer"]["dropped"]
    assert max(w.calls.values()) == 3  # bounded: no endless loop


def test_made_up_quote_by_the_validator_is_ignored():
    card = {"applied_insight": "Вы пишете, что стыдно."}
    out = {"sentences": [{"field": "applied_insight", "sentence": "Этого предложения нет в карточке.",
                          "label": "hypothesis_as_fact", "reason": "r"}]}
    assert violations_of(out, card) == []
    m = validation_material({"рассказ": "x"}, {"ход_текста": "y"}, {k: "t" for k in
                            ("title", "main_idea", "applied_insight", "reflection_question", "question_explanation",
                             "perspective")})
    assert set(m["текст_карточки"]) and "grounding" not in json.dumps(m, ensure_ascii=False)


def test_internal_effect_and_frame_describe_a_possibility():
    assert "описывают ВОЗМОЖНОСТЬ увидеть вопрос иначе, а не новый факт о человеке" in SYSTEM_PROMPT


def test_without_validator_the_pipeline_is_unchanged(fragments, tmp_path):
    w = base.Writer()
    s = base.session(fragments, tmp_path, writer=w)
    s.compose()
    assert all(c["validation"] == [] for c in s.composition.meta.usage["writer"]["cards"])

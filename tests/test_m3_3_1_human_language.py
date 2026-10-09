"""M3.3.1 human-language correction: regression tests for the CLASSES of errors found in the manual M3.3 test.

They check structure that can be checked reliably (sentence count, unnamed feelings / specialists, bare pronoun
in a second question, false chapter/verse precision, the writer pipeline covering the expandable fields, copy
text, invariants). Whether Russian sounds natural is judged by the real control runs, not by these tests.
No live model."""

from __future__ import annotations

from corpus_snapshot import legacy_card_only

from corpus_snapshot import load_test_fragments

import hashlib
import json
from pathlib import Path

import pytest

from navigator.composition.composer import SYSTEM_PROMPT, compose
from navigator.composition.writer import WRITER_PROMPT
from navigator.interpretation.interpreter import interpret
from navigator.models.fragment import Fragment
from navigator.models.interpretation import InterpretationInput
from navigator.models.vocabularies import SOURCE_ROUTE_STATUS
from navigator.prototype.flow import Services, Session, copy_text
from navigator.providers.fake import FakeEmbeddingClient
from navigator.retrieval.engine import CandidateRetriever

ROOT = Path(__file__).resolve().parents[1]
SON = ("У моего сына невроз - я не знаю как реагировать. Хочу ему запретить - но это не улучшит ситуацию. "
       "У меня тоже в детстве было такое. Не знаю что делать (понятное дело, что я пойду к неврологу с ним), "
       "но не хочу проблематизировать - надеюсь что это возратсное")
LAYOFF = ("Меня сократили. 12 лет в одной компании, я там был не последний человек. Деньги пока есть. Но я каждое "
          "утро просыпаюсь и не знаю куда себя деть. Друзьям вообще не сказал, стыдно, хотя я понимаю что это не моя вина.")


@pytest.fixture(scope="module")
def fragments():
    return load_test_fragments()


def interp_out(question):
    return {"sufficient": True, "insufficiency_reason": None,
            "reading_notes": [{"kind": "tension", "note": "желание запретить и понимание, что это не поможет"}],
            "working_hypotheses": ["возможно, запрет кажется единственным действием", "принятие путается со смирением"],
            "proposed_question": question, "coordinates": ["принятие / сопротивление", "отношение к другому"],
            "canonical_tensions": ["действие ↔ принятие"], "free_tensions": [], "ambiguity_notes": []}


class Interp:
    name, model = "scripted", None

    def __init__(self, outputs):
        self.outputs, self.feedback = list(outputs), []

    def complete(self, inp, feedback=None):
        self.feedback.append(feedback)
        return self.outputs.pop(0), {}


GOOD_Q = ("С сыном сейчас происходит то, что было и у меня в детстве. Хочется запретить, но я понимаю, что это не поможет. "
          "Как быть рядом с ним, если мне трудно принять, что сейчас всё так?")


_AUTHORS: dict[str, str] = {}


def pick(pkg, n):
    """The first ``n`` pool cards; for a final-corpus package the first ``n`` of DIFFERENT authors, as the real selector
    must (temporary MVP rule: one final card per author). Legacy packages: unchanged."""
    pool = [c["card_id"] for c in pkg["candidates"]]
    if not pkg.get("corpus_version"):
        return pool[:n]
    if not _AUTHORS:
        from navigator.corpus.final_corpus import load_final_active

        _AUTHORS.update({c.card_id: c.author for c in load_final_active()})
    ids, seen = [], set()
    for cid in pool:
        if _AUTHORS[cid] not in seen:
            ids.append(cid)
            seen.add(_AUTHORS[cid])
    return ids[:n]


class Selector:
    """Selection-only composer (M3.3.1 format)."""
    name, model = "scripted", None

    def __init__(self, n=3, reason=None):
        self.n, self.reason, self.calls = n, reason, 0

    def complete(self, pkg, feedback=None):
        self.calls += 1
        ids = pick(pkg, self.n)
        persp = [{"card_id": i, "role": "ход", "distinction": f"Помогает различить одно и другое ({k}).",
                  "perspective_effect": f"человек видит свой вопрос иначе, способ {k}",
                  "source_point": "источник говорит простую вещь", "user_point": "это касается вопроса",
                  "why_selected": "ясное различение"} for k, i in enumerate(ids)]
        top = pkg["q1_top_card_id"]
        return {"perspectives": persp, "fewer_than_three_reason": self.reason if self.n == 2 else None,
                "rejected": [], "q1_top": {"card_id": top, "decision": "selected" if top in ids else "rejected",
                                            "reason": "r"}}, {}


def written(k=0, **over):
    c = {"title": ["Признать, что не справляешься, ещё не значит сдаться", "Хотеть помочь и помочь — не одно и то же",
                   "Принять не значит ничего не делать"][k % 3],
         "main_idea": "Моисей в какой-то момент прямо говорит: одному мне это не поднять. Но дело он не бросает.",
         "applied_insight": "Вы пишете, что хочется запретить, но это не поможет. Когда близкому плохо, хочется сразу "
                            "что-то сделать. Но не всякое действие ему помогает.",
         "reflection_question": "Что я делаю для сына в обычный день? И что из этого ему правда помогает?",
         "question_explanation": "Речь о простых делах. Например, разговор перед сном или совместный ужин.",
         "perspective": "Моисей не делает вид, что справится один. Он прямо говорит, что сил не хватает, и зовёт других. "
                        "Дело от этого не останавливается, а идёт по-другому. Так и здесь: признать, что всё сразу "
                        "не исправить, ещё не значит опустить руки."}
    c.update(over)
    return c


class Writer:
    """Per-card writer: ``bad`` maps call index (per card, 0-based) to field overrides for that attempt."""
    name, model = "scripted", None

    def __init__(self, bad=None, always_bad_for=None, extra=None):
        self.bad, self.always_bad_for, self.extra = bad or {}, always_bad_for, extra or {}
        self.calls: dict[str, int] = {}
        self.feedback: dict[str, list] = {}

    def complete(self, brief, feedback=None):
        key = brief["различение_карточки"]
        n = self.calls.get(key, 0)
        self.calls[key] = n + 1
        self.feedback.setdefault(key, []).append(feedback)
        k = int(key.split("(")[1][0])
        if brief.get("формат_карточки") == "final-mvp":  # MVP pass 1: the final-corpus card has three text fields
            out = final_written(k, **({**self.bad.get(n, {})} if k == 0 else {}))
            out.setdefault("grounding", honest_grounding(brief, final=True))
            out.update(self.extra)
            return out, {}
        out = written(k, **({**self.bad.get(n, {})} if k == 0 else {}))
        if self.always_bad_for is not None and k == self.always_bad_for:
            out = written(k, reflection_question="Какое дело я тяну одна? Что в нём можно устроить иначе?")
        out.setdefault("grounding", honest_grounding(brief))
        out.update(self.extra)
        return out, {}


def honest_grounding(brief, final=False):
    """A provenance audit (M3.3.2) that quotes the brief verbatim: one user fact and one source fact."""
    words = (brief["слова_человека"]["рассказ"] or "").split()
    move = (brief["источник"]["ход_текста"] or brief["источник"]["описание_в_корпусе_учёным_языком_не_переносить_слова"]).split()
    return [{"field": "applied_insight", "claim": "Вы пишете о своей ситуации.", "kind": "user_fact",
             "evidence": " ".join(words[:4])},
            {"field": "main_idea", "claim": "Источник говорит о своём.", "kind": "source_fact",
             "evidence": " ".join(move[:4])}]


def final_written(k=0, **over):
    """The final-corpus MVP card (comment on the quote / application / ONE question)."""
    c = {"main_idea": ["Автор отделяет то, что человек может сделать, от того, что ему неподвластно.",
                       "Здесь различаются желание помочь и сама помощь.",
                       "Автор разводит принятие и бездействие."][k % 3],
         "applied_insight": "Вы пишете, что хочется запретить, но это не поможет. Когда близкому плохо, хочется сразу "
                            "что-то сделать. Но не всякое действие ему помогает.",
         "reflection_question": "Что из моих действий рядом с сыном ему правда помогает?",
         "quote_excerpt": "", "metaphor_words": []}
    c.update({k_: v for k_, v in over.items() if k_ in c or k_ in ("grounding",)})
    return c


def session(fragments, tmp_path, narrative=SON, question=GOOD_Q, selector=None, writer=None, experiences=None):
    svc = Services(fragments, Interp([interp_out(question)]), selector or Selector(),
                   lambda: CandidateRetriever(fragments, FakeEmbeddingClient(), cache_root=tmp_path / "c"),
                   writer=writer or Writer())
    s = Session(svc, None)
    s.submit("Семья / дети / родители", experiences or ["Беспомощность"], "Мне трудно принять происходящее", narrative)
    s.confirm("confirmed")
    return s


# ------------------------------------------------------------------ 1. proposed question: 2–3 sentences, enforced


def test_proposed_question_with_four_sentences_is_repaired():
    four = ("С сыном что-то происходит. Мне хочется запретить. Я понимаю, что это не поможет. "
            "Как быть рядом с ним?")
    it = Interp([interp_out(four), interp_out(GOOD_Q)])
    res = interpret(InterpretationInput(topic="t", experiences=[], difficulty_center="c", free_narrative=SON), it)
    assert res.proposed_question == GOOD_Q and res.trace.attempts == 2 and "4 sentences" in it.feedback[1]
    assert res.trace.usage["repairs"] and "at most 3" in res.trace.usage["repairs"][0]


def test_proposed_question_with_unnamed_feeling_is_repaired():
    feared = "Меня сократили. Почему мне страшно рассказать друзьям?"
    it = Interp([interp_out(feared), interp_out("Меня сократили. Как быть с тем, что мне стыдно говорить друзьям?")])
    res = interpret(InterpretationInput(topic="t", experiences=["Растерянность"], difficulty_center="c",
                                        free_narrative=LAYOFF), it)
    assert res.trace.attempts == 2 and "страх" in it.feedback[1]


# ------------------------------------------------------------------ 2–5. writer pipeline


@legacy_card_only
def test_two_linked_questions_and_all_fields_through_writer(fragments, tmp_path):
    s = session(fragments, tmp_path)
    view = s.compose()
    assert len(view["perspectives"]) == 3
    for p in view["perspectives"]:
        assert p["reflection_question"].count("?") == 2 and p["question_explanation"] and p["details"]
        assert "?" not in p["title"]
    assert all(r["attempts"] == 1 for r in s.composition.meta.usage["writer"]["cards"])


@legacy_card_only
@pytest.mark.parametrize("bad,reason", [
    ({"applied_insight": "Любовь к сыну не сомнительна. Но не всякое действие помогает."}, "did not name"),
    ({"question_explanation": "Можно обсудить это с детским психологом."}, "did not name"),
    ({"reflection_question": "Какую картину своего положения я боюсь увидеть в глазах друзей?"}, "did not name"),
])
def test_unnamed_feeling_love_or_specialist_is_rewritten(bad, reason, fragments, tmp_path):
    w = Writer(bad={0: bad})
    s = session(fragments, tmp_path, writer=w)
    s.compose()
    fb = [f for fs in w.feedback.values() for f in fs if f]
    assert fb and reason in fb[0]
    assert all(bad[k] not in getattr(p, k) for p in s.composition.perspectives for k in bad)


def test_named_feeling_is_allowed(fragments, tmp_path):
    w = Writer(bad={0: {"applied_insight": "Вы пишете, что вам стыдно сказать друзьям. Стыд и вина — разные вещи."}})
    s = session(fragments, tmp_path, narrative=LAYOFF, writer=w, experiences=["Растерянность"])
    s.compose()
    assert all(r["attempts"] == 1 for r in s.composition.meta.usage["writer"]["cards"])


@legacy_card_only
def test_bare_pronoun_in_second_question_is_rewritten(fragments, tmp_path):
    w = Writer(bad={0: {"reflection_question": "Что я могу сказать в пользу запрета? Что в нём можно устроить иначе?"}})
    s = session(fragments, tmp_path, writer=w)
    s.compose()
    fb = [f for fs in w.feedback.values() for f in fs if f]
    assert "pronoun" in fb[0]


@legacy_card_only
@pytest.mark.parametrize("field,text,reason", [
    ("perspective", "В 22-й главе Дао дэ цзин говорится, что нехватка не всегда поражение. " * 3, "chapter/verse"),
    ("main_idea", "В Коране (65:7) расходы связаны с достатком.", "chapter/verse"),
    ("perspective", "Гита предлагает посмотреть на способ участия в действии, а не на то, сколько сделано. " * 3,
     "meta-language"),
    ("question_explanation", "На самом деле вам страшно не справиться.", "unconfirmed hypothesis"),
])
def test_expandable_fields_go_through_the_same_checks(field, text, reason, fragments, tmp_path):
    w = Writer(bad={0: {field: text}})
    s = session(fragments, tmp_path, writer=w)
    s.compose()
    fb = [f for fs in w.feedback.values() for f in fs if f]
    assert fb and reason in fb[0]
    assert all(text not in getattr(p, field) for p in s.composition.perspectives)


@legacy_card_only
def test_only_the_failing_card_is_rewritten(fragments, tmp_path):
    sel = Selector()
    w = Writer(bad={0: {"title": "Можно ли признать предел?"}})
    s = session(fragments, tmp_path, selector=sel, writer=w)
    s.compose()
    assert sel.calls == 1  # selection is not repeated for a text problem
    assert sorted(w.calls.values()) == [1, 1, 2]


def test_writer_prompt_covers_expandable_fields_and_voice():
    for needle in ("question_explanation", "«Подробнее»", "ВСЕ шесть полей", "Местоимения", "учёным языком",
                   "не называй номера глав", "Моисей в какой-то момент прямо говорит"):
        assert needle in WRITER_PROMPT, needle
    assert "title" not in json.dumps(SYSTEM_PROMPT.split("Для каждой выбранной карточки")[1][:400])  # selector writes no text


# ------------------------------------------------------------------ 6. copy


@legacy_card_only
def test_copy_text_contains_the_full_card(fragments, tmp_path):
    s = session(fragments, tmp_path)
    view = s.compose()
    p = view["perspectives"][0]
    assert view["copy_text"] == copy_text(view["confirmed_question"], view["perspectives"])
    expected_card = "\n".join([
        f"1. {p['title']}", p["source"], "", p["main_idea"], "", p["applied_insight"], "",
        f"Вопрос к себе: {p['reflection_question']}", "",
        f"Что имеется в виду? {p['question_explanation']}", "",
        f"Подробнее: {p['details']}",
    ])
    assert view["copy_text"].startswith(f"Мой вопрос\n{GOOD_Q}\n\nНа него можно посмотреть с нескольких сторон.\n\n")
    assert expected_card in view["copy_text"]
    assert view["copy_text"].endswith("\n\nИнструмент предназначен для самоанализа и не заменяет профессиональную помощь.")
    for internal in ("distinction", "Помогает различить", "why_selected", "C0"):
        assert internal not in view["copy_text"]


# ------------------------------------------------------------------ 7–10. invariants, quotes, SOURCE, two cards


def test_corpus_taxonomy_benchmark_files_unchanged():
    expected = {
        "data/corpus/fragments.jsonl": "5554aa8c0",
        "data/corpus/launch-manifest.json": "b7492177f",
        "data/eval/benchmarks/m2_1-retrieval-benchmark-v0.1.json": "08d4cf65f",
        "data/eval/interpretation/m2_6-interpretation-benchmark-v0.1.json": "5bd817f92",
        "TAXONOMY-philosophical-navigator-v1.1.md": "7b3ee62b8",
        "M2.1-RETRIEVAL-BENCHMARK-v0.1.md": "ca3c9474c",
    }
    for path, prefix in expected.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest().startswith(prefix), path


def test_retrieval_is_still_the_m24_candidate_union(fragments, tmp_path):
    s = session(fragments, tmp_path)
    r = s.retrieve() and s.retrieval
    q1 = {h.card_id for h in r.q1_meaning.hits}
    st = {h.card_id for h in r.structure.hits}
    assert {c.card_id for c in r.candidate_union} == q1 | st


def test_source_route_stays_disabled():
    assert SOURCE_ROUTE_STATUS == "disabled_pending_full_fragment_text"


def test_writer_cannot_supply_a_quote(fragments, tmp_path):
    w = Writer(extra={"quote": "«цитата по памяти»", "verified_quote": {"text": "x"}})
    s = session(fragments, tmp_path, writer=w)
    view = s.compose()
    assert all(p.verified_quote is None for p in s.composition.perspectives)
    assert "цитата по памяти" not in json.dumps(view, ensure_ascii=False)


def test_two_cards_allowed_by_selection(fragments, tmp_path):
    s = session(fragments, tmp_path, selector=Selector(n=2, reason="третья слабее"))
    assert len(s.compose()["perspectives"]) == 2 and s.composition.fewer_than_three_reason == "третья слабее"


@legacy_card_only
def test_card_that_cannot_be_written_clearly_is_dropped_not_shown(fragments, tmp_path):
    s = session(fragments, tmp_path, writer=Writer(always_bad_for=2))
    view = s.compose()
    assert len(view["perspectives"]) == 2 and s.composition.fewer_than_three_reason
    assert "Что в нём" not in view["copy_text"]
    assert s.composition.meta.usage["writer"]["dropped"]


def test_writer_is_grounded_in_card_data_only():
    assert "НЕ добавляй сюжетных подробностей" in WRITER_PROMPT
    assert "ложную видимость" in WRITER_PROMPT


def test_writer_effort_flag_is_passed(monkeypatch):
    import subprocess

    from navigator.composition import writer as wmod

    seen = {}

    class P:
        stdout = json.dumps({"structured_output": {f: "x" for f in wmod.USER_FIELDS}, "usage": {}})

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return P()

    monkeypatch.setattr(subprocess, "run", fake_run)
    wmod.ClaudeCodeCLIWriter(effort="medium").complete({"x": 1})
    i = seen["cmd"].index("--effort")
    assert seen["cmd"][i + 1] == "medium"

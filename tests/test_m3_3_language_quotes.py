"""M3.3 language + quote readiness: multi-sentence proposed question, two-part reflection question,
declarative titles kept, reference voice in the prompts, source-reference formatting, and quotes that
can never come from the model or be "verified" without a local source. No live model."""

from __future__ import annotations

from corpus_snapshot import blocked_ids, expected_eligible, legacy_only, load_test_fragments

import hashlib
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from navigator.composition import composer as comp_mod
from navigator.composition.references import display_reference
from navigator.interpretation import interpreter as interp_mod
from navigator.interpretation.interpreter import confirm, interpret
from navigator.language import LANGUAGE_RULES, REFERENCE_VOICE
from navigator.models.fragment import Fragment
from navigator.models.interpretation import InterpretationInput
from navigator.prototype.flow import Services, Session
from navigator.prototype.server import App, make_handler
from navigator.providers.fake import FakeEmbeddingClient
from navigator.quotes import QuoteNotVerified, QuoteProvenance, VerifiedQuote, audit, quote_for_card, verify_quote
from navigator.retrieval.engine import CandidateRetriever

ROOT = Path(__file__).resolve().parents[1]
MULTI = ("Я хочу быть продуктивной, но снова упираюсь в пределы своих возможностей. "
         "Как понять, где мои реальные границы, а где стоит продолжать пытаться? "
         "И чем бережность к себе отличается от отказа от себя?")
NARRATIVE = ("Хочу быть продуктивной, но постоянно упираюсь в свои пределы: сил не хватает, я устаю и бросаю. "
             "Не понимаю, где мне себя пожалеть, а где это уже отказ от себя.")


@pytest.fixture(scope="module")
def fragments():
    return load_test_fragments()


class Interp:
    name, model = "scripted", None

    def __init__(self, question=MULTI):
        self.question = question

    def complete(self, inp, feedback=None):
        return {"sufficient": True, "insufficiency_reason": None,
                "reading_notes": [{"kind": "tension", "note": "желание продуктивности и предел сил"}],
                "working_hypotheses": ["возможно, бережность смешивается с отказом", "предел сил переживается как поражение"],
                "proposed_question": self.question,
                "coordinates": ["принятие / сопротивление", "отношение к себе"],
                "canonical_tensions": ["действие ↔ принятие"], "free_tensions": [], "ambiguity_notes": []}, {}


def card(cid, k, **over):
    c = {"card_id": cid, "role": "ход",
         "distinction": ["Помогает различить признание предела и отказ от дела.",
                         "Помогает различить уступку и поражение.",
                         "Помогает увидеть настрой работы, а не только её объём."][k % 3],
         "title": ["Признать, что не справляешься, ещё не значит сдаться", "Уступить не всегда значит проиграть",
                   "Важно не сколько сделано, а с каким настроем"][k % 3],
         "main_idea": "Моисей в какой-то момент прямо говорит: одному ему это не поднять. Но дело он не бросает.",
         "applied_insight": "Вы спрашиваете, смириться с пределами или дальше пытаться. Можно честно сказать, что сил не хватает, и работать иначе.",
         "reflection_question": "Как я отношусь к себе, когда работаю? И как отношусь к тому, что у меня получится?",
         "question_explanation": "Речь о том, что вы чувствуете к себе во время работы. Например, спокойствие или постоянное недовольство.",
         "perspective": "Моисей признаёт, что один не справляется. Он не бросает дело, а зовёт других. "
                        "Так признание предела становится началом другой работы, а не концом.",
         "why_selected": "ясное различение"}
    c.update(over)
    return c


class Comp:
    name, model = "scripted", None

    def __init__(self, first=None, extra=None):
        self.first, self.extra, self.feedback = first, extra or {}, []

    def complete(self, pkg, feedback=None):
        self.feedback.append(feedback)
        ids = [c["card_id"] for c in pkg["candidates"]][:3]
        persp = [card(i, k) for k, i in enumerate(ids)]
        if self.first and feedback is None:
            persp[0] = card(ids[0], 0, **self.first)
        for p in persp:
            p.update(self.extra)
        top = pkg["q1_top_card_id"]
        return {"perspectives": persp, "fewer_than_three_reason": None, "rejected": [],
                "q1_top": {"card_id": top, "decision": "selected" if top in ids else "rejected", "reason": "r"}}, {}


def session(fragments, tmp_path, composer=None, quote_source=None, question=MULTI):
    svc = Services(fragments, Interp(question), composer or Comp(),
                   lambda: CandidateRetriever(fragments, FakeEmbeddingClient(), cache_root=tmp_path / "c"),
                   quote_source=quote_source)
    s = Session(svc, None)
    s.submit("Работа / дело / деньги", ["Усталость"], "Я не понимаю, где мои пределы", NARRATIVE)
    return s


# ------------------------------------------------------------------ proposed question


def test_proposed_question_may_have_several_sentences():
    res = interpret(InterpretationInput(topic="t", experiences=[], difficulty_center="c", free_narrative=NARRATIVE), Interp())
    assert res.proposed_question == MULTI and res.proposed_question.count(".") >= 1
    c = confirm(res, action="confirmed", source="user")
    assert c.confirmed_question == MULTI
    assert "НЕ обязан быть одним предложением" in interp_mod.SYSTEM_PROMPT


def test_multi_sentence_question_through_http_confirmation(fragments, tmp_path):
    svc = Services(fragments, Interp(), Comp(),
                   lambda: CandidateRetriever(fragments, FakeEmbeddingClient(), cache_root=tmp_path / "c"))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(App(svc, None)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def post(path, body):
        req = urllib.request.Request(base + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    try:
        v = post("/api/interpret", {"topic": "t", "experiences": [], "difficulty_center": "c", "narrative": NARRATIVE})
        assert v["proposed_question"] == MULTI
        c = post("/api/confirm", {"session_id": v["session_id"], "action": "confirmed"})
        assert c["confirmed_question"] == MULTI
        a = post("/api/compose", {"session_id": v["session_id"]})
        assert a["state"] == "answered" and a["confirmed_question"] == MULTI
    finally:
        httpd.shutdown()


# ------------------------------------------------------------------ cards


def test_declarative_titles_and_two_part_reflection_question(fragments, tmp_path):
    s = session(fragments, tmp_path)
    s.confirm("confirmed")
    view = s.compose()
    assert all("?" not in p["title"] for p in view["perspectives"])
    assert all(p["reflection_question"].count("?") == 2 for p in view["perspectives"])


@pytest.mark.parametrize("rq", [
    "Что в моих делах можно делать по-другому? Не больше и не меньше, а именно по-другому.",
    "Где я заставляю себя идти напролом, хотя можно было бы обойти?",
])
def test_reference_style_questions_are_accepted(rq, fragments, tmp_path):
    comp = Comp(first={"reflection_question": rq})
    s = session(fragments, tmp_path, comp)
    s.confirm("confirmed")
    s.compose()
    assert s.composition.meta.attempts == 1


def test_question_title_is_still_repaired(fragments, tmp_path):
    comp = Comp(first={"title": "Можно ли признать предел и не сдаться?"})
    s = session(fragments, tmp_path, comp)
    s.confirm("confirmed")
    s.compose()
    assert s.composition.meta.attempts == 2 and "declarative" in comp.feedback[1]


def test_new_meta_language_is_repaired(fragments, tmp_path):
    comp = Comp(first={"main_idea": "Гита предлагает посмотреть на способ участия в действии."})
    s = session(fragments, tmp_path, comp)
    s.confirm("confirmed")
    s.compose()
    assert s.composition.meta.attempts == 2 and "meta-language" in comp.feedback[1]


def test_reference_voice_and_language_rules_in_prompts():
    from navigator.composition.writer import WRITER_PROMPT  # M3.3.1: the card text is written here

    guide = (ROOT / "LANGUAGE-GUIDE.md").read_text(encoding="utf-8")
    for text in REFERENCE_VOICE:
        assert text in WRITER_PROMPT  # the model that writes the text sees the user's reference cards
        for para in text.split("\n\n"):  # and they are identical to the source-of-truth guide
            assert para in guide, para[:60]
    assert LANGUAGE_RULES in WRITER_PROMPT and LANGUAGE_RULES in interp_mod.SYSTEM_PROMPT
    assert "НЕ копируй" in WRITER_PROMPT


# ------------------------------------------------------------------ references


@pytest.mark.parametrize("work,loc,expected", [
    ("Тора / Пятикнижие", "Чис 11:14", "Ветхий Завет, Числа 11:14"),
    ("Тора / Пятикнижие", "Чис 11:10–17", "Ветхий Завет, Числа 11:10–17"),
    ("Евангелия", "Мф 20:1–16", "Новый Завет, Матфея 20:1–16"),
    ("Книга Иова и Экклезиаст", "Еккл 1:2–11", "Ветхий Завет, Екклесиаст 1:2–11"),
    ("Бхагавад-гита", "БГ 4.16–23", "Бхагавад-гита, 4.16–23"),
    ("Коран", "65:7", "Коран, 65:7"),
    ("Дао дэ цзин", "Чжан 22", "Дао дэ цзин, глава 22"),
    ("Диалоги Платона", "Федон 67c–d", "Платон, Федон 67c–d"),
    ("Дхаммапада", "1", "Дхаммапада, стих 1"),
    ("Дхаммапада", "360–367", "Дхаммапада, стихи 360–367"),
])
def test_display_reference(work, loc, expected):
    assert display_reference(work, loc) == expected


def test_public_view_uses_reader_friendly_reference(fragments, tmp_path):
    s = session(fragments, tmp_path)
    s.confirm("confirmed")
    view = s.compose()
    by_id = {f.id: f for f in fragments}
    for p, internal in zip(view["perspectives"], s.composition.perspectives):
        assert internal.source == ", ".join(x for x in (by_id[internal.card_id].author, by_id[internal.card_id].work,
                                                      by_id[internal.card_id].location) if x)  # grounding unchanged
        assert "Чис " not in p["source"] and "БГ " not in p["source"] and "Мф " not in p["source"]


# ------------------------------------------------------------------ quotes


def test_model_can_never_supply_a_quote(fragments, tmp_path):
    fake_quote = {"card_id": "C0957", "text": "одному мне не поднять", "reference": "Чис 11:14",
                  "provenance": {"method": "local_source_match", "source_file": "data/sources/x.txt",
                                 "source_sha256": "0" * 64, "char_start": 0, "char_end": 5,
                                 "translator": "x", "edition": "x"}}
    s = session(fragments, tmp_path, Comp(extra={"verified_quote": fake_quote, "quote": "«цитата по памяти»"}))
    s.confirm("confirmed")
    view = s.compose()
    assert all(p.verified_quote is None for p in s.composition.perspectives)
    assert "quote" not in json.dumps(view, ensure_ascii=False).lower()


def _quote(tmp_path, text="одному мне это не поднять", body=None):
    src = tmp_path / "data/sources/bible.txt"
    src.parent.mkdir(parents=True, exist_ok=True)
    content = body if body is not None else f"Числа 11:14 {text}. Дальше."
    src.write_text(content, encoding="utf-8")
    start = content.find(text)
    return VerifiedQuote(card_id="C0957", text=text, reference="Ветхий Завет, Числа 11:14",
                         provenance=QuoteProvenance(method="local_source_match", source_file="data/sources/bible.txt",
                                                    source_sha256=hashlib.sha256(content.encode()).hexdigest(),
                                                    char_start=max(start, 0), char_end=max(start, 0) + len(text),
                                                    translator="т", edition="и"))


def test_quote_verified_only_against_local_source(tmp_path):
    q = _quote(tmp_path)
    assert verify_quote(q, tmp_path) is q
    (tmp_path / "data/sources/bible.txt").write_text("изменённый текст", encoding="utf-8")
    with pytest.raises(QuoteNotVerified):
        verify_quote(q, tmp_path)


def test_quote_without_local_file_or_outside_sources_is_rejected(tmp_path):
    q = _quote(tmp_path)
    (tmp_path / "data/sources/bible.txt").unlink()
    with pytest.raises(QuoteNotVerified):
        verify_quote(q, tmp_path)
    outside = q.model_copy(update={"provenance": q.provenance.model_copy(update={"source_file": "Архив/x.md"})})
    with pytest.raises(QuoteNotVerified):
        verify_quote(outside, tmp_path)


def test_quote_for_card_requires_ready_row(tmp_path):
    q = _quote(tmp_path)
    row = {"category": "PARTIAL", "verified_quote": q.model_dump()}
    assert quote_for_card("C0957", {"cards": {"C0957": row}}, tmp_path) is None
    assert quote_for_card("C0957", {"cards": {"C0957": {**row, "category": "READY"}}}, tmp_path) == q
    assert quote_for_card("C0957", None, tmp_path) is None


@legacy_only
def test_audit_counts_and_no_ready_without_local_text(fragments):
    inv = audit(fragments, ROOT)
    c = inv["counts"]
    assert inv["total_eligible"] == 113 and c["READY"] + c["PARTIAL"] + c["NOT_READY"] == 113
    if not inv["local_source_files"]:
        assert c["READY"] == 0  # nothing can be READY without a local full source text
    for row in inv["cards"].values():
        assert row["verified_quote"] is None or row["category"] == "READY"
        if row["candidate_excerpt"] is None:
            assert row["category"] == "NOT_READY"


@legacy_only
def test_recorded_inventory_matches_audit(fragments):
    p = ROOT / "data/quotes/QUOTE-READINESS-INVENTORY.json"
    if not p.exists():
        pytest.skip("inventory not written")
    assert json.loads(p.read_text(encoding="utf-8"))["counts"] == audit(fragments, ROOT)["counts"]


def test_na_samom_dele_guard_only_for_claims_about_the_person():
    from navigator.models.interpretation import amplification_hits

    assert not amplification_hits("Эпиктет показывает, что на самом деле любовь ещё не доказывает правоту.")
    assert amplification_hits("Вы на самом деле боитесь провала.")
    assert amplification_hits("На самом деле вам страшно.")

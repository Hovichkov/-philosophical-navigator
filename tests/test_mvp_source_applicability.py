"""Source-to-question applicability at selection (2026-10-22), final corpus only.

The selector must keep the source's subject (what it is about), agent (whose it is) and sense when it applies a card to
the confirmed question; a generic phrase is not a perspective; one strong card is a full answer and an empty selection
is the honest outcome. These are contract/structure checks with invented, nonidentifying examples — they do not prove
the quality of live model choices."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import test_m3_3_1_human_language as base
import test_mvp_story_flow as story

from navigator.composition import composer as cmp
from navigator.composition.composer import (
    DECISIONS,
    FINAL_OUTPUT_SCHEMA,
    OUTPUT_SCHEMA,
    SYSTEM_PROMPT,
    NoApplicablePerspective,
    check_selection,
    compose,
    rejected_from,
)
from navigator.corpus.final_corpus import FINAL_CORPUS_VERSION
from navigator.composition.composer import ComposerUnavailable
from navigator.prototype.flow import USER_ERROR_COMPOSE_CHECK, USER_ERROR_MODEL, USER_ERROR_NO_FIT, user_message_for

ROOT = Path(__file__).resolve().parents[1]
fragments = base.fragments  # module fixture

# Invented case: a beekeeper asks whether selling honey changes why they keep bees. Card ids are placeholders.
QUESTION = "Изменится ли для меня смысл пасеки, если я начну продавать мёд?"
POOL = ["C9001", "C9002", "C9003"]


def package(final: bool = True) -> dict:
    return {"item_id": "fiction-bees", "retrieval_run_id": "fiction", "confirmed_question": QUESTION,
            "candidates": [{"card_id": c} for c in POOL], "q1_top_card_id": POOL[0],
            **({"corpus_version": FINAL_CORPUS_VERSION} if final else {})}


def card(cid: str, fit: str = "Источник говорит о плате за труд у работающего; в вопросе о том же: продажа мёда") -> dict:
    return {"card_id": cid, "perspective_effect": "плата за дело и смысл дела можно рассматривать отдельно",
            "perspective_frame": "чем измеряется ценность занятия", "distinction": "Помогает различить плату и смысл",
            "role": "разводит меры", "source_point": "s", "user_point": "u", "why_selected": "w", "fit": fit}


class Scripted:
    name, model = "scripted", None

    def __init__(self, output):
        self.output, self.calls = output, 0

    def complete(self, pkg, feedback=None):
        self.calls += 1
        return self.output, {}


def test_prompt_states_subject_agent_sense_and_generic_rules():
    assert "ПРЕДМЕТ" in SYSTEM_PROMPT and "СУБЪЕКТ" in SYSTEM_PROMPT and "СМЫСЛ" in SYSTEM_PROMPT
    assert "Общая фраза сама по себе не перспектива" in SYSTEM_PROMPT
    assert "не отвергай сильную перспективу за другую обстановку" in SYSTEM_PROMPT  # no overstrict filter
    assert "пустой список perspectives" in SYSTEM_PROMPT
    assert {"subject_shift", "generic_only"} <= set(DECISIONS)
    assert cmp.PROMPT_VERSION == "composition-prompt/0.12.0"


def test_prompt_count_is_consistent_for_final_and_legacy():
    head = SYSTEM_PROMPT[:SYSTEM_PROMPT.index("Главное правило продукта")]
    assert "свой вопрос: 2 или 3" not in SYSTEM_PROMPT  # the old unconditional count is gone
    assert "НЕТ поля corpus_version: 2 или 3" in head and "corpus_version ЕСТЬ (финальный корпус): 1, 2 или 3" in head
    assert "ни одной" in head
    assert "Без corpus_version пустой список и одна карточка недопустимы" in SYSTEM_PROMPT
    assert "при 1 — почему второй нет; при 0 — почему не подошла ни одна" in SYSTEM_PROMPT
    assert "2 и 3 — равноправные" not in SYSTEM_PROMPT


def test_schemas_final_accepts_zero_and_requires_fit_legacy_unchanged():
    fin, leg = FINAL_OUTPUT_SCHEMA["properties"]["perspectives"], OUTPUT_SCHEMA["properties"]["perspectives"]
    assert fin["minItems"] == 0 and fin["maxItems"] == 3 and "fit" in fin["items"]["required"]
    assert leg["minItems"] == 2 and "fit" not in leg["items"]["properties"]


def test_one_strong_card_with_fit_is_a_valid_final_selection():
    assert [p["card_id"] for p in check_selection(package(), {"perspectives": [card("C9002")]})] == ["C9002"]


def test_empty_fit_is_sent_back_for_repair():
    with pytest.raises(ValueError, match="empty fit"):
        check_selection(package(), {"perspectives": [card("C9002", fit="  ")]})


def test_a_card_marked_subject_shift_cannot_also_be_selected():
    out = {"perspectives": [card("C9001")],
           "considered": [{"card_id": "C9001", "decision": "subject_shift", "duplicate_of": None,
                           "perspective_effect": "e", "perspective_frame": "f",
                           "reason": "источник о своём прошлом теле, вопрос о другом человеке"}]}
    with pytest.raises(ValueError, match="subject_shift"):
        check_selection(package(), out)


def test_rejected_reasons_name_subject_shift_and_generic_only():
    out = {"considered": [
        {"card_id": "C9001", "decision": "selected", "duplicate_of": None, "reason": "r"},
        {"card_id": "C9002", "decision": "subject_shift", "duplicate_of": None, "reason": "о нравственном пути, не о мёде"},
        {"card_id": "C9003", "decision": "generic_only", "duplicate_of": None, "reason": "подошло бы к любому вопросу"}]}
    reasons = {r.card_id: r.reason for r in rejected_from(out, ["C9001"])}
    assert reasons["C9002"].startswith("предмет или субъект источника подменён")
    assert reasons["C9003"].startswith("общая фраза без различения")


def test_empty_final_selection_is_an_honest_outcome_without_retries():
    sel = Scripted({"perspectives": [], "count_reason": "ни один источник не говорит о продаже плодов своего дела",
                    "q1_top": {"card_id": "C9001", "decision": "rejected", "reason": "r"}})
    with pytest.raises(NoApplicablePerspective, match="продаже плодов"):
        compose(package(), [], sel, max_attempts=3, writer=object())
    assert sel.calls == 1  # not treated as a contract violation, no extra model calls
    assert user_message_for(NoApplicablePerspective("x"), "composition") == USER_ERROR_NO_FIT != USER_ERROR_COMPOSE_CHECK


def test_legacy_corpus_still_rejects_an_empty_selection_as_a_contract_error():
    with pytest.raises(ValueError, match="select 2–3"):
        check_selection(package(final=False), {"perspectives": []})


def test_no_fit_message_is_exact_and_does_not_claim_the_corpus_is_empty():
    assert USER_ERROR_NO_FIT.startswith("Не удалось подобрать подходящую перспективу к этому вопросу.")
    assert "В корпусе не нашлось" not in USER_ERROR_NO_FIT and "Попробуйте ещё раз" not in USER_ERROR_NO_FIT
    assert user_message_for(ComposerUnavailable("timeout"), "composition") == USER_ERROR_MODEL  # ordinary retry path


class EmptyThenSelects(base.Selector):
    """First selection: nothing applicable (empty list); later: an ordinary scripted selection."""

    def complete(self, pkg, feedback=None):
        if self.calls == 0:
            self.calls += 1
            return {"perspectives": [], "count_reason": "ни одна карточка не говорит о предмете вопроса",
                    "considered": [], "q1_top": {"card_id": pkg["q1_top_card_id"], "decision": "rejected",
                                                 "reason": "r"}}, {}
        return super().complete(pkg, feedback)


def test_empty_selection_then_edited_question_gets_a_new_answer_keeping_story_and_feelings(fragments, tmp_path,
                                                                                         monkeypatch):
    """Scenario over the real HTTP handler: empty selection → «Изменить вопрос» → new answer. Only the final contract
    allows an empty selection, so it is switched on for the first selection over the small test corpus."""
    from http.server import ThreadingHTTPServer

    from navigator.prototype.server import App, make_handler

    svc, it, _ = story.services(fragments, tmp_path, [story.out()])
    sel = svc.composer = EmptyThenSelects()
    # the final contract applies to the empty first selection; the new answer uses the test corpus as it is
    monkeypatch.setattr(cmp, "is_final_package", lambda pkg: sel.calls == 1)
    app = App(svc, tmp_path / "traces")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}"

    def post(path, body):
        req = urllib.request.Request(url + path, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    try:
        code, v = post("/api/interpret", {"experiences": ["Беспомощность", "Тревогу"], "narrative": story.SON,
                                          "auto_confirm": True})
        sid = v["session_id"]
        assert post("/api/retrieve", {"session_id": sid})[0] == 200
        code, e = post("/api/compose", {"session_id": sid})
        assert code == 422 and e == {"error": USER_ERROR_NO_FIT, "no_fit": True}
        assert sel.calls == 1  # no automatic repeat of the selection
        s = app.get(sid)
        story_text, feelings = s.input.free_narrative, list(s.input.experiences)
        edited = "Как мне понять, что сыну сейчас нужно от меня?"
        code, c = post("/api/confirm", {"session_id": sid, "action": "edited", "text": edited})
        assert code == 200 and c["confirmed_question"] == edited
        code, a = post("/api/compose", {"session_id": sid})
        assert code == 200
        assert a["confirmed_question"] == edited and a["perspectives"]
        assert sel.calls == 2 and it.calls == 1  # one new selection, the story is not read again
        assert s.input.free_narrative == story_text and s.input.experiences == feelings == ["Беспомощность", "Тревогу"]
    finally:
        httpd.shutdown()


def test_page_offers_edit_question_on_no_fit_and_keeps_retry_for_failures():
    page = (ROOT / "src/navigator/prototype/static/index.html").read_text(encoding="utf-8")
    catch = page[page.index("if (e.noFit)"):page.index("// ---- result (M3.1")]
    assert catch.index("showNoFit(") < catch.index("fail(e.message, () => exclusive(() => answer(")  # retry kept
    no_fit = page[page.index("function showNoFit"):page.index("// ---- result (M3.1")]
    assert '$("edit-q-link").hidden = false' in no_fit and "renderOtherQuestions(" in no_fit
    assert "api(" not in no_fit and "answer(" not in no_fit  # nothing is re-sent automatically
    assert 'err.noFit = data.no_fit === true' in page and 'id="no-fit"' in page

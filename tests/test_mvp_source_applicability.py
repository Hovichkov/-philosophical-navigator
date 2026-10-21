"""Source-to-question applicability at selection (2026-10-22), final corpus only.

The selector must keep the source's subject (what it is about), agent (whose it is) and sense when it applies a card to
the confirmed question; a generic phrase is not a perspective; one strong card is a full answer and an empty selection
is the honest outcome. These are contract/structure checks with invented, nonidentifying examples — they do not prove
the quality of live model choices."""

from __future__ import annotations

import pytest

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
from navigator.prototype.flow import USER_ERROR_COMPOSE_CHECK, USER_ERROR_NO_FIT, user_message_for

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
    assert cmp.PROMPT_VERSION == "composition-prompt/0.11.0"


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

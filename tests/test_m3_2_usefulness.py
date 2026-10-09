"""M3.2 usefulness + accessibility: card contract, 2-instead-of-weak-3, reference cases from the two real
user tests (property checks, no exact-text snapshots), staged answer API, UI elements. No live model."""

from __future__ import annotations

from corpus_snapshot import load_test_fragments

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from pydantic import ValidationError

from navigator.composition.composer import SYSTEM_PROMPT, compose
from navigator.composition.quality import failed, property_checks
from navigator.interpretation import interpreter as interp_mod
from navigator.models.composition import Perspective
from navigator.models.fragment import Fragment
from navigator.models.interpretation import INTERNAL_CLAIM_RULE
from navigator.prototype.flow import Services, Session
from navigator.prototype.server import App, make_handler
from navigator.providers.fake import FakeEmbeddingClient
from navigator.retrieval.engine import CandidateRetriever

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "src/navigator/prototype/static/index.html"
CASES = {c["id"]: c for c in json.loads((ROOT / "tests/fixtures/m3_2_reference_cases.json").read_text(encoding="utf-8"))["cases"]}


@pytest.fixture(scope="module")
def fragments():
    return load_test_fragments()


def good_card(cid, k=0, **over):
    c = {"card_id": cid, "role": "ход",
         "distinction": ["Помогает различить ценность работы и её цену.",
                         "Помогает различить пользу другим и обязанность отдавать последнее.",
                         "Помогает увидеть, что любовь к делу не требует сохранять его форму."][k % 3],
         "title": ["Цена работы и её ценность — разные вещи", "Помогать можно в меру своих сил",
                   "Любить дело не значит держаться за его форму"][k % 3],
         "main_idea": "Текст говорит, что оценка со стороны не решает, чего стоит дело.",
         "applied_insight": "Вы пишете, что работа приносит людям пользу. Мало денег — это другой вопрос. Их можно рассмотреть отдельно.",
         "reflection_question": "Сколько я сейчас могу вкладывать в дело, не залезая в новые долги?",
         "question_explanation": "Речь о ваших реальных пределах сейчас: времени, деньгах и силах.",
         "perspective": "Мы привыкли мерить ценность дела тем, сколько за него платят. Текст разводит эти вещи. "
                        "Плата зависит от многих внешних причин. Ценность дела — от того, что оно делает для людей.",
         "why_selected": "ясное различение"}
    c.update(over)
    return c


class Comp:
    name, model = "scripted", None

    def __init__(self, n=3, first=None, second_ok=True):
        self.n, self.first, self.feedback = n, first, []

    def complete(self, pkg, feedback=None):
        self.feedback.append(feedback)
        ids = [c["card_id"] for c in pkg["candidates"]][: self.n]
        persp = [good_card(i, k) for k, i in enumerate(ids)]
        if self.first and feedback is None:
            persp[0] = good_card(ids[0], 0, **self.first)
        top = pkg["q1_top_card_id"]
        return {"perspectives": persp,
                "fewer_than_three_reason": None if self.n == 3 else "третий кандидат не даёт ясного различения",
                "rejected": [], "q1_top": {"card_id": top, "decision": "selected" if top in ids else "rejected", "reason": "r"}}, {}


class Interp:
    name, model = "scripted", None

    def __init__(self, question):
        self.question = question

    def complete(self, inp, feedback=None):
        return {"sufficient": True, "insufficiency_reason": None,
                "reading_notes": [{"kind": "tension", "note": "ценность дела и его оплата"}],
                "working_hypotheses": ["возможно, оплата переживается как оценка себя", "долги давят на выбор"],
                "proposed_question": self.question,
                "coordinates": ["принятие / сопротивление", "контроль"],
                "canonical_tensions": ["действие ↔ принятие"], "free_tensions": [], "ambiguity_notes": []}, {}


def session_for(case, fragments, tmp_path, composer):
    svc = Services(fragments, Interp(case["confirmed_question"]), composer,
                   lambda: CandidateRetriever(fragments, FakeEmbeddingClient(), cache_root=tmp_path / "c"))
    s = Session(svc, None)
    s.submit(case["topic"], case["experiences"], case["difficulty_center"], case["free_narrative"])
    s.confirm("confirmed")
    return s


# ------------------------------------------------------------------ prompts


def test_prompt_has_usefulness_and_one_read_rules():
    from navigator.composition.writer import WRITER_PROMPT

    # M3.3.1: selection rules live in the selection prompt, text rules in the card-writer prompt
    for needle in ("полезное различение", "КАЧЕСТВО ВАЖНЕЕ КОЛИЧЕСТВА", "Не достраивай проблему", "НЕ традицией или автором"):
        assert needle in SYSTEM_PROMPT, needle
    for needle in ("Правило одного прочтения", "заголовок-вывод", "question_explanation", "«Подробнее»"):
        assert needle in WRITER_PROMPT, needle
    assert INTERNAL_CLAIM_RULE in SYSTEM_PROMPT and INTERNAL_CLAIM_RULE in interp_mod.SYSTEM_PROMPT
    assert INTERNAL_CLAIM_RULE in WRITER_PROMPT
    # the reference distinctions are examples of level, the real test answers are not hardcoded
    # (M3.3: the user's reference voice names Дао дэ цзин / chapter 22 on purpose; the case-B places must not appear)
    for prompt in (SYSTEM_PROMPT, WRITER_PROMPT):
        assert "Мф 20" not in prompt and "Чжан 13" not in prompt and "65:7" not in prompt


# ------------------------------------------------------------------ reference cases (property checks)


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_reference_case_properties(case_id, fragments, tmp_path):
    case = CASES[case_id]
    s = session_for(case, fragments, tmp_path, Comp())
    view = s.compose()
    assert view["confirmed_question"] == case["confirmed_question"]
    checks = property_checks(s.composition, fragments, case["not_in_user_words"])
    assert not failed(checks), failed(checks)
    for p in view["perspectives"]:
        assert "distinction" not in p and "why_selected" not in p  # internal formula never shown


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_weak_third_may_be_omitted(case_id, fragments, tmp_path):
    s = session_for(CASES[case_id], fragments, tmp_path, Comp(n=2))
    assert len(s.compose()["perspectives"]) == 2 and s.composition.fewer_than_three_reason


def test_invented_comparison_is_flagged_by_case_checks(fragments, tmp_path):
    case = CASES["B-meaningful-work-money-debt"]
    s = session_for(case, fragments, tmp_path, Comp())
    s.compose()
    bad = s.composition.perspectives[0].model_copy(update={"applied_insight": "Вы сравниваете себя с теми, у кого доходы выше."})
    res = s.composition.model_copy(update={"perspectives": [bad, *s.composition.perspectives[1:]]})
    assert any("nothing the user did not say" in c["check"] for c in failed(property_checks(res, fragments, case["not_in_user_words"])))


# ------------------------------------------------------------------ deterministic structure → repair


@pytest.mark.parametrize("over,needle", [
    ({"title": "От чьей оценки зависит ценность моего дела?"}, "declarative"),
    ({"reflection_question": "Сколько я могу отдавать? Что я получаю? И зачем?"}, "one or two short questions"),
    ({"reflection_question": "Где для меня, если честно, проходит граница, за которой, как мне кажется, я отдаю больше?"}, "too complex"),
    ({"question_explanation": "Как вы думаете, что здесь важно?"}, "must not ask"),
    ({"applied_insight": "Если долг перед миром измерять тем, что у вас есть, и если при этом считать, что польза другим важнее, "
                         "то вопрос о деньгах начинает выглядеть совсем иначе, чем раньше казалось вам самим."}, "first reading"),
    ({"main_idea": "Текст вскрывает скрытую предпосылку вопроса о цене."}, "meta-language"),
    ({"distinction": "Карточка про деньги."}, "distinction must say"),
])
def test_structure_violations_are_repaired(over, needle, fragments, tmp_path):
    comp = Comp(first=over)
    s = session_for(CASES["B-meaningful-work-money-debt"], fragments, tmp_path, comp)
    s.compose()
    assert s.composition.meta.attempts == 2 and needle in comp.feedback[1]
    assert needle in s.composition.meta.usage["repairs"][0]


def test_distinction_and_explanation_come_together():
    base = {**good_card("C0013"), "source": "x"}
    with pytest.raises(ValidationError):
        Perspective(**{**base, "question_explanation": None})


def test_m31_results_still_load(fragments):
    for f in sorted((ROOT / "reports/m3_1-control-run/sessions").glob("*.json"))[:3]:
        comp = json.loads(f.read_text(encoding="utf-8"))["composition"]
        if comp:
            from navigator.models.composition import CompositionResult
            assert CompositionResult.model_validate(comp).schema_version == "composition/0.2.0"


# ------------------------------------------------------------------ staged answer API + UI


def test_staged_retrieve_then_compose_over_http(fragments, tmp_path):
    case = CASES["A-son-guilt-control"]
    svc = Services(fragments, Interp(case["confirmed_question"]), Comp(),
                   lambda: CandidateRetriever(fragments, FakeEmbeddingClient(), cache_root=tmp_path / "c"))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(App(svc, None)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def post(path, body):
        req = urllib.request.Request(base + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    try:
        sid = post("/api/interpret", {"topic": case["topic"], "experiences": case["experiences"],
                                      "difficulty_center": case["difficulty_center"], "narrative": case["free_narrative"]})["session_id"]
        post("/api/confirm", {"session_id": sid, "action": "confirmed"})
        r = post("/api/retrieve", {"session_id": sid})
        assert r["state"] == "retrieved" and "perspectives" not in r
        c = post("/api/compose", {"session_id": sid})
        assert c["state"] == "answered" and all(p["question_explanation"] for p in c["perspectives"])
    finally:
        httpd.shutdown()


def test_ui_staged_loading_explanation_details_copy():
    html = INDEX.read_text(encoding="utf-8")
    # MVP pass 1: honest stage text (cards arrive together, so not «первую перспективу») + elapsed time
    for needle in ('"Что имеется в виду?"', '"Подробнее"', "Ищем философские перспективы…", "/api/retrieve", "/api/compose",
                   'id="copy"', 'id="share"', "navigator.share", 'class="skeleton"'):
        assert needle in html, needle
    # M3.3.1 reverses the M3.2 rule: the clipboard now carries the full card (built by the server, flow.copy_text)
    text_fn = html[html.index("function resultText()"):html.index("async function copyText")]
    assert "RESULT.copyText" in text_fn
    assert "<footer>Инструмент предназначен для самоанализа и не заменяет профессиональную помощь.</footer>" in html

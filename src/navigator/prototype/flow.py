"""Prototype session flow (M3): a thin state machine over the existing core.

    input → interpret (M2.6) → proposed
    proposed → confirm(confirmed | edited | replaced) → confirmed
    MVP flow (story → feelings → question → answer): with ``auto_confirm`` ONE clear question is confirmed at once
    (no extra step, no model call); several independent questions → the person chooses one (``choose``), the others
    stay in the session and can be chosen later; an unclear story → one short clarifying question (insufficient).
    confirmed → retrieve (M2.4, fast) → retrieved → compose (selection + card writers) → answered
    answered → reflect (M3.4: the chosen perspective and/or the person's own words) → reflected

Nothing in the core is re-implemented: interpretation, confirmation, query building,
retrieval and composition are the existing functions. ``public_view`` is the only data
the browser UI receives; ``debug_view`` exposes the full internal trace for developers.
"""

from __future__ import annotations

import datetime as dt
import json
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from navigator.composition.composer import build_package, compose
from navigator.composition.references import display_label, fragment_reference
from navigator.models.composition import FINAL_CARD_FORMAT
from navigator.interpretation.interpreter import confirm, interpret, to_query_representation
from navigator.models.interpretation import InsufficientInterpretation, InterpretationInput, InterpretationResult
from navigator.corpus.policy import excluded_ids_for

USER_ERROR = "Не получилось обработать запрос. Попробуйте ещё раз."
USER_ERROR_COMPOSITION = "Не получилось подобрать перспективы. Попробуйте ещё раз."
# MVP stabilization: the person always learns WHAT happened (the technical cause stays in the session trace)
USER_ERROR_LIMIT = ("Сейчас исчерпан лимит запросов к языковой модели. Подождите немного и попробуйте ещё раз — "
                    "ваш текст сохранён.")
USER_ERROR_MODEL = "Языковая модель сейчас не ответила. Попробуйте ещё раз — ваш текст сохранён."
USER_ERROR_INTERPRET = ("Не получилось сформулировать вопрос по этому рассказу. Попробуйте ещё раз или опишите "
                        "ситуацию немного иначе — ваш текст сохранён.")
USER_ERROR_COMPOSE_CHECK = ("Не получилось подготовить ясный ответ: проверки текста не прошли. Попробуйте ещё раз — "
                            "иногда со второй попытки получается.")
USER_ERROR_BUSY = "Этот запрос уже обрабатывается. Дождитесь ответа, пожалуйста."
MAX_EXPERIENCES = 3  # MVP: at most three feelings — the ones that matter most


def user_message_for(exc: Exception, stage: str) -> str:
    """A human explanation of a failure, by its cause (never a traceback)."""
    text = str(exc).lower()
    if any(k in text for k in ("429", "session limit", "rate limit", "usage limit", "hit your", "overloaded")):
        return USER_ERROR_LIMIT
    if any(k in text for k in ("cli error", "timeout", "timed out", "non-json", "no such file", "not found: 'claude'")) \
            or type(exc).__name__.endswith("Unavailable"):
        return USER_ERROR_MODEL
    if stage == "interpret":
        return USER_ERROR_INTERPRET
    if stage == "composition" and ("validation" in text or "could not be written" in text):
        return USER_ERROR_COMPOSE_CHECK
    return USER_ERROR_COMPOSITION if stage == "composition" else USER_ERROR


DISCLAIMER = "Инструмент предназначен для самоанализа и не заменяет профессиональную помощь."
OPENING = "На него можно посмотреть с нескольких сторон."
OPENING_ONE = "На него можно посмотреть так."  # final corpus: a single strong card is a valid answer
NEXT_ROUND = "Следующий круг будет строиться от этой мысли."  # M3.4: the entry point; the round itself is not built yet
MAX_REFLECTION_CHARS = 2000
SHORT_QUOTE_WORDS = 40  # final-corpus test mode: a longer verified quote goes into «Подробнее», whole (never cut)


def copy_text(question: str, perspectives: list[dict]) -> str:
    """What «Скопировать» / «Поделиться» put on the clipboard (M3.3.1): the full content of every card,
    including «Что имеется в виду?» and «Подробнее» whether or not they are open on screen."""
    lines = ["Мой вопрос", question, "", OPENING if len(perspectives) != 1 else OPENING_ONE]
    for i, p in enumerate(perspectives, 1):
        if p.get("format") == FINAL_CARD_FORMAT:  # MVP pass 1: quote → comment → application → one question
            q = p["quote"]
            lines += ["", f"{i}. «{q['full'] or q['text']}»", p["source"], "", p["comment"], "", p["application"],
                      "", f"Вопрос на подумать: {p['question']}"]
            continue
        lines += ["", f"{i}. {p['title']}", p["source"], ""]
        q = p.get("quote")
        if p.get("main_idea"):
            lines += [p["main_idea"]]
            if q and q["in_main"]:
                lines += ["", f"«{q['text']}» — {q['work']}, {q['location']}"]
            lines += ["", p["applied_insight"]]
        else:  # older result format
            lines += [p.get("details") or ""]
        lines += ["", f"Вопрос к себе: {p['reflection_question']}"]
        if p.get("question_explanation"):
            lines += ["", f"Что имеется в виду? {p['question_explanation']}"]
        if p.get("main_idea") and p.get("details"):
            lines += ["", f"Подробнее: {p['details']}"]
            if q and not q["in_main"]:
                lines += ["", f"«{q['text']}» — {q['work']}, {q['location']}"]
            if q:
                lines += ["", f"Перевод: {q['translator']}. Издание: {q['edition']}"]
    lines += ["", DISCLAIMER]
    return "\n".join(lines)


class _Release:
    def __init__(self, lock):
        self.lock = lock

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.lock.release()
        return False


class FlowError(RuntimeError):
    """An error with a human-readable message for the UI."""

    def __init__(self, user_message: str, detail: str = ""):
        super().__init__(detail or user_message)
        self.user_message = user_message


@dataclass
class Services:
    """Injected core components (real in the prototype, fakes in tests)."""

    fragments: list
    interpreter: Any
    composer: Any
    retriever_factory: Any  # callable → CandidateRetriever (lazy: model load is slow)
    quote_source: Any = None  # M3.3: card_id → VerifiedQuote | None, from READY local-source inventory rows only
    writer: Any = None  # M3.3.1: card writer (one call per card, parallel); None = one-call composer format
    validator: Any = None  # M3.4.2: independent grounding validator of each written card; None = not run
    show_quotes: bool = False  # final-corpus test mode: show the verified quote with work + exact location
    _retriever: Any = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    # one retrieval at a time: the embedding model and the query-vector cache are shared by all sessions
    retrieve_lock: threading.Lock = field(default_factory=threading.Lock)

    def retriever(self):
        with self._lock:
            if self._retriever is None:
                self._retriever = self.retriever_factory()
            return self._retriever


@dataclass
class Session:
    services: Services
    trace_dir: Path | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_utc: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
    state: str = "new"  # new | insufficient | proposed | confirmed | retrieved | answered | reflected
    input: InterpretationInput | None = None
    interpretation: InterpretationResult | None = None
    insufficient: InsufficientInterpretation | None = None
    confirmation: Any = None
    query: Any = None
    retrieval: Any = None
    composition: Any = None
    errors: list[dict] = field(default_factory=list)
    timings: list[dict] = field(default_factory=list)  # M3.3.1 latency breakdown per stage
    reflection: dict | None = None  # M3.4: what the person took from the result (entry point of the next round)
    questions: list[str] = field(default_factory=list)  # MVP flow: every independent question found in the story
    auto_confirmed: bool = False  # MVP flow: the one clear question was taken without a confirmation step
    _busy: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def _guard(self):
        """MVP stabilization: a second request for the same session while one runs (double submit) is refused
        with a clear message instead of running the model twice and racing on the session state."""
        if not self._busy.acquire(blocking=False):
            raise FlowError(USER_ERROR_BUSY, "concurrent request for the same session")
        return _Release(self._busy)

    # ---------------------------------------------------------------- steps
    def submit(self, topic: str, experiences: list[str], difficulty_center: str, narrative: str,
               auto_confirm: bool = False) -> dict:
        with self._guard():
            return self._submit(topic, experiences, difficulty_center, narrative, auto_confirm)

    def _submit(self, topic: str, experiences: list[str], difficulty_center: str, narrative: str,
                auto_confirm: bool = False) -> dict:
        feelings = list(dict.fromkeys(e.strip() for e in experiences if e.strip()))[:MAX_EXPERIENCES]
        self.input = InterpretationInput(
            topic=topic.strip() or "Другое", experiences=feelings,
            difficulty_center=difficulty_center.strip() or "Другое", free_narrative=narrative.strip(),
        )
        self.interpretation = self.insufficient = self.confirmation = None
        self.query = self.retrieval = self.composition = None
        self.questions, self.auto_confirmed = [], False
        t0 = time.monotonic()
        try:
            outcome = interpret(self.input, self.services.interpreter)
        except Exception as exc:
            self._time("interpretation", t0, ok=False)
            self._fail("interpret", exc)
            raise FlowError(user_message_for(exc, "interpret"), str(exc)) from exc
        usage = outcome.trace.usage or {}
        self._time("interpretation", t0, llm_calls=len(usage.get("calls", [])), retries=max(outcome.trace.attempts - 1, 0),
                   retry_reasons=usage.get("repairs", []), calls=usage.get("calls", []))
        if isinstance(outcome, InsufficientInterpretation):
            self.insufficient, self.state = outcome, "insufficient"
        else:
            self.interpretation, self.state = outcome, "proposed"
            self.questions = [outcome.proposed_question, *outcome.other_questions]
            if auto_confirm and len(self.questions) == 1:  # one clear question: no confirmation step
                self.auto_confirmed = True
                return self._confirm("confirmed")
        self._save()
        return self.public_view()

    def choose(self, index: int) -> dict:
        """MVP flow: take one of the questions found in the story (also later, from the answer screen: the others stay
        in the session). No model call — the interpretation of the story is reused; the answer is built anew."""
        with self._guard():
            if self.interpretation is None or self.state in ("new", "insufficient"):
                raise FlowError(USER_ERROR, f"cannot choose a question in state {self.state}")
            if not (isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(self.questions)):
                raise FlowError(USER_ERROR, f"unknown question {index}")
            chosen = self.questions[index]
            self.interpretation = self.interpretation.model_copy(update={
                "proposed_question": chosen, "other_questions": [q for q in self.questions if q != chosen]})
            self.retrieval = self.composition = self.reflection = None
            self.state = "proposed"
            return self._confirm("confirmed")

    def confirm(self, action: str, text: str | None = None) -> dict:
        with self._guard():
            return self._confirm(action, text)

    def _confirm(self, action: str, text: str | None = None) -> dict:
        if self.state not in ("proposed", "confirmed") or self.interpretation is None:
            raise FlowError(USER_ERROR, f"cannot confirm in state {self.state}")
        if action not in ("confirmed", "edited", "replaced"):
            raise FlowError(USER_ERROR, f"unknown action {action}")
        own = (text or "").strip() or None
        if action != "confirmed" and not own:
            raise FlowError("Пожалуйста, напишите формулировку вопроса.", "empty edited/replaced text")
        try:
            self.confirmation = confirm(self.interpretation, action=action, source="user", edited_text=own)
            self.query = to_query_representation(self.interpretation, self.confirmation)
        except Exception as exc:
            self._fail("confirm", exc)
            raise FlowError(USER_ERROR, str(exc)) from exc
        self.state = "confirmed"
        self._save()
        return self.public_view()

    def retrieve(self) -> dict:
        """Stage 1 of the answer (fast, local): M2.4 candidate retrieval for the confirmed question."""
        with self._guard():
            return self._retrieve()

    def _retrieve(self) -> dict:
        if self.state not in ("confirmed", "retrieved", "answered") or self.query is None:
            raise FlowError(USER_ERROR, f"cannot retrieve in state {self.state}")
        t0 = time.monotonic()
        try:
            retriever = self.services.retriever()
            with self.services.retrieve_lock:
                self.retrieval = retriever.retrieve(self.query, f"proto-{self.id}")
        except Exception as exc:
            self._fail("retrieval", exc)
            raise FlowError(user_message_for(exc, "retrieval"), str(exc)) from exc
        self._time("retrieval", t0, llm_calls=0)
        self.state = "retrieved"
        self._save()
        return self.public_view()

    def compose(self) -> dict:
        """Stage 2 of the answer (slow, one model call): M2.5/M3.2 composition over the candidate union."""
        with self._guard():
            return self._compose()

    def _compose(self) -> dict:
        if self.state == "confirmed":
            self._retrieve()
        if self.state not in ("retrieved", "answered") or self.retrieval is None:
            raise FlowError(USER_ERROR, f"cannot compose in state {self.state}")
        t0 = time.monotonic()
        try:
            trace = {"item_id": f"proto-{self.id}", "run_id": f"prototype-{self.id}",
                     "candidate_retrieval": self.retrieval.model_dump(mode="json")}
            # 3 attempts in the prototype: a failed check costs the person the whole wait, a retry only ~40 s.
            self.composition = compose(build_package(trace, self.services.fragments), self.services.fragments,
                                       self.services.composer, max_attempts=3, quote_source=self.services.quote_source,
                                       writer=self.services.writer, validator=self.services.validator)
        except Exception as exc:
            self._time("composition", t0, ok=False)
            self._fail("composition", exc)
            raise FlowError(user_message_for(exc, "composition"), str(exc)) from exc
        self._record_composition_timings(t0)
        leaked = {p.card_id for p in self.composition.perspectives} & excluded_ids_for(self.retrieval.corpus_version)
        if leaked:  # defence in depth; the contracts already forbid it
            raise FlowError(USER_ERROR_COMPOSITION, f"unresolved in result: {leaked}")
        self.state = "answered"
        self._save()
        return self.public_view()

    def reflect(self, chosen: int | None, text: str | None) -> dict:
        """M3.4: after reading, the person picks the perspective that mattered and/or writes in their own words
        what they now see differently. Saved with the question and the shown cards; no model call."""
        if self.state not in ("answered", "reflected") or self.composition is None:
            raise FlowError(USER_ERROR, f"cannot reflect in state {self.state}")
        own = (text or "").strip()[:MAX_REFLECTION_CHARS] or None
        cards = self.public_view()["perspectives"]
        if chosen is not None and not (isinstance(chosen, int) and 0 <= chosen < len(cards)):
            raise FlowError(USER_ERROR, f"unknown perspective {chosen}")
        if chosen is None and own is None:
            raise FlowError("Выберите мысль или напишите несколько слов своими словами.", "empty reflection")
        pick = self.composition.perspectives[chosen] if chosen is not None else None
        self.reflection = {
            "utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "question": self.confirmation.confirmed_question,
            "shown_perspectives": cards,
            "chosen_index": chosen,
            "chosen_card_id": pick.card_id if pick else None,
            "chosen_title": (pick.title or pick.main_idea) if pick else None,
            "own_text": own,
        }
        self.state = "reflected"
        self._save()
        return self.public_view()

    def answer(self) -> dict:
        """Both stages in one call (kept for the single-request API and tests)."""
        with self._guard():
            if self.state not in ("confirmed", "retrieved", "answered") or self.query is None:
                raise FlowError(USER_ERROR, f"cannot answer in state {self.state}")
            self._retrieve()
            return self._compose()

    # ---------------------------------------------------------------- views
    def public_view(self) -> dict:
        """Only what the user may see: no hypotheses, taxonomy labels, scores, card IDs or trace."""
        view: dict[str, Any] = {"session_id": self.id, "state": self.state}
        if self.state == "insufficient" and self.insufficient:
            view["clarification"] = self.insufficient.clarification_prompt
        if self.interpretation is not None:
            view["proposed_question"] = self.interpretation.proposed_question
            if len(self.questions) > 1:  # MVP flow: several independent questions — the person picks one
                view["questions"] = list(self.questions)
        if self.confirmation is not None:
            view["confirmed_question"] = self.confirmation.confirmed_question
        if self.state in ("answered", "reflected") and self.composition is not None:
            # Card: Title / Source / Main Idea / Applied Insight / Reflection Question;
            # collapsed: «Что имеется в виду?» = question_explanation (M3.2), «Подробнее» = details (M3.1).
            # Internal fields (distinction, role, why_selected, card_id) are never sent. M3.3: ``source`` is the
            # reader-friendly reference built by code; verified quotes are NOT shown yet (0 READY cards, see
            # reports/validation/M3.3-QUOTE-READINESS-REPORT.md).
            view["perspectives"] = [
                self._final_card(p) if p.card_format == FINAL_CARD_FORMAT else
                {"title": p.title, "source": self._reference(p), "main_idea": p.main_idea,
                 "applied_insight": p.applied_insight,
                 "reflection_question": p.reflection_question, "question_explanation": p.question_explanation,
                 "details": p.perspective, **self._quote(p.card_id)}
                for p in self.composition.perspectives
            ]
            view["copy_text"] = copy_text(view["confirmed_question"], view["perspectives"])
        if self.state == "reflected" and self.reflection is not None:
            view["reflection"] = {"chosen_index": self.reflection["chosen_index"],
                                  "chosen_title": self.reflection["chosen_title"],
                                  "own_text": self.reflection["own_text"], "next": NEXT_ROUND}
        return view

    def _quote(self, card_id: str) -> dict:
        """Final-corpus test mode: the verified verbatim quote (never altered or cut), with work and exact location;
        translator / edition belong in «Подробнее». The quote is not the card: the distinction stays the main content."""
        if not self.services.show_quotes:
            return {}
        f = next((f for f in self.services.fragments if f.id == card_id), None)
        if f is None or f.technical.corpus_status != "final_2026_10_07" or not f.fragment:
            return {}
        return {"quote": {"text": f.fragment, "work": f.work, "location": f.location,
                          "in_main": len(f.fragment.split()) <= SHORT_QUOTE_WORDS,
                          "translator": f.translation, "edition": f.source}}

    def _final_card(self, p) -> dict:
        """MVP pass 1, final corpus: the four-part card. Internal fields never leave the server. The quote is the
        verified text, never rewritten; a long one is shown as a verbatim excerpt with the whole quote one tap away."""
        f = next(x for x in self.services.fragments if x.id == p.card_id)
        excerpt = p.quote_excerpt
        quote = {"text": excerpt or f.fragment, "excerpt": bool(excerpt),
                 "starts": not excerpt or f.fragment.lstrip().startswith(excerpt[:30]),
                 "ends": not excerpt or f.fragment.rstrip().endswith(excerpt[-30:]),
                 "full": f.fragment if excerpt else None, "translator": f.translation, "edition": f.source}
        return {"format": FINAL_CARD_FORMAT, "title": p.main_idea, "source": display_label(f), "quote": quote,
                "comment": p.main_idea, "application": p.applied_insight, "question": p.reflection_question}

    def _reference(self, p) -> str:
        f = next((f for f in self.services.fragments if f.id == p.card_id), None)
        return fragment_reference(f) if f is not None else p.source

    def debug_view(self) -> dict:
        def dump(obj):
            return json.loads(obj.model_dump_json()) if obj is not None else None

        return {
            "session_id": self.id, "created_utc": self.created_utc, "state": self.state,
            "interpretation_input": dump(self.input),
            "interpretation": dump(self.interpretation),
            "insufficient": dump(self.insufficient),
            "confirmation": dump(self.confirmation),
            "query_representation": dump(self.query),
            "retrieval": dump(self.retrieval),
            "composition": dump(self.composition),
            "errors": self.errors,
            "timings": self.timings,
            "reflection": self.reflection,
            "questions": self.questions,
            "auto_confirmed": self.auto_confirmed,
        }

    # ---------------------------------------------------------------- internals
    def _time(self, stage: str, t0: float, **extra) -> None:
        self.timings.append({"stage": stage, "seconds": round(time.monotonic() - t0, 2), **extra})

    def _record_composition_timings(self, t0: float) -> None:
        usage = self.composition.meta.usage or {}
        calls = usage.get("calls", [])
        for c in calls:
            self.timings.append({"stage": f"selection attempt {c.get('attempt')}", "seconds": c.get("call_seconds"),
                                 "llm_calls": 1, "validation_seconds": c.get("validation_seconds"),
                                 "output_tokens": c.get("output_tokens"), "thinking_tokens": c.get("thinking_tokens")})
        repairs = usage.get("repairs", [])
        w = usage.get("writer", {})
        if w:
            self.timings.append({"stage": "card writing (parallel, wall)", "seconds": w.get("seconds"),
                                 "llm_calls": sum(e.get("attempts", 0) for e in w.get("cards", [])),
                                 "dropped_cards": w.get("dropped", [])})
        vcalls = [v for e in w.get("cards", []) for v in e.get("validation", [])]
        if vcalls:
            self.timings.append({"stage": "independent validation (sum of calls)",
                                 "seconds": round(sum(v.get("call_seconds") or 0 for v in vcalls), 2),
                                 "llm_calls": len(vcalls),
                                 "rejected_by_validator": sum(1 for v in vcalls if v.get("violations"))})
        for e in w.get("cards", []):
            self.timings.append({"stage": f"  writer {e.get('card_id')}", "seconds": e.get("seconds"),
                                 "llm_calls": e.get("attempts"), "retries": max(e.get("attempts", 1) - 1, 0),
                                 "retry_reasons": e.get("repairs", []), "fallback_to_draft": e.get("fallback")})
        self._time("composition total", t0, llm_calls=len(calls) + len(vcalls) + sum(e.get("attempts", 0) for e in w.get("cards", [])),
                   retries=len(repairs) + sum(len(e.get("repairs", [])) for e in w.get("cards", [])),
                   retry_reasons=repairs + [r for e in w.get("cards", []) for r in e.get("repairs", [])])

    def _fail(self, stage: str, exc: Exception) -> None:
        self.errors.append({"stage": stage, "error": str(exc)[:2000], "traceback": traceback.format_exc()[-4000:],
                            "utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
        self._save()

    def _save(self) -> None:
        if self.trace_dir is None:
            return
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        (self.trace_dir / f"{self.id}.json").write_text(
            json.dumps(self.debug_view(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

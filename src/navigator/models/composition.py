"""Composition contract (M2.5, experimental).

From the M2.4 candidate union, 2–3 philosophical perspectives are selected and
written for a human. The composer (LLM) produces title / perspective / reflection
question and selection reasons; the SOURCE of every perspective is filled by code
from corpus metadata, never by the model.

Hard rules enforced here:
- 2 or 3 perspectives (never 4–5). Up to composition/0.4.0 two cards needed a fewer_than_three_reason;
  from 0.5.0 (M3.4) 2 and 3 are equal results: a third card appears only with its own strong effect;
- selected cards come only from the candidate pool, are unique and never unresolved;
- source string equals the corpus metadata of the card;
- every perspective has a reflection question;
- the fixed opening line; no concluding advice.
There is no tradition/author diversity requirement.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

from navigator.models.quote import VerifiedQuote
from navigator.models.vocabularies import UNRESOLVED_IDS

NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]
FragmentId = Annotated[str, Field(pattern=r"^C\d{4}$")]

COMPOSITION_SCHEMA_VERSION = "composition/0.5.0"  # M3.4; 0.1.0 (M2.5) … 0.4.0 (M3.3) still load
ONE_CALL_SCHEMA_VERSION = "composition/0.4.0"  # the older one-call composer format (benchmark / scripted tests)
OPENING_LINE = "Ваш вопрос можно рассмотреть с нескольких сторон."

# Phrases that turn a perspective into advice or a verdict (M2.5 §1, §7). Heuristic guard.
ADVICE_PATTERNS = (
    r"\bвам следует\b", r"\bвам нужно\b", r"\bвы должны\b", r"\bвам надо\b", r"\bправильное решение\b",
    r"\bправильный выбор\b", r"\bтаким образом, вам\b", r"\bглавное понять\b", r"\bобязательно\s+(?:уйдите|простите|оставьте|уезжайте)",
)


def advice_hits(text: str) -> list[str]:
    return [p for p in ADVICE_PATTERNS if re.search(p, text, flags=re.IGNORECASE)]


# M3.1 result clarity: plain-language card (Title / Main Idea / Applied Insight / Reflection Question,
# with the longer ``perspective`` behind «Подробнее»). Upper bounds; the prompt asks for less.
WORD_LIMITS = {"title": 14, "main_idea": 45, "applied_insight": 55, "perspective": 150}
# Internal/technical vocabulary that must not reach the user in the new card fields.
JARGON_PATTERNS = (
    r"карточк", r"\bфрагмент\w*\s+(?:показывает|утверждает|предлагает|говорит)", r"\bфилософск\w+\s+операц",
    r"\bкоординат\w*", r"\bтаксоном\w*",
)


# M3.2 usefulness + one-read rule. Only structural checks that are reliable; meaning is the prompt's job.
M32_LIMITS = {"title": 12, "reflection_question": 30, "question_explanation": 40}  # M3.3: question may be two short ones
MAX_SENTENCE_WORDS = 25  # gross one-read bound for main idea / applied insight / explanation / question
# Gross bounds only (prompt asks for 1–2 / 1–3 / 1–2): one-read writing favours short sentences, so the
# count limit leaves one sentence of slack instead of rejecting a card for splitting a thought in two.
MAX_SENTENCES = {"main_idea": 4, "applied_insight": 4, "question_explanation": 3}  # M3.3: short-sentence voice
# Philosophical meta-language that must not appear in the main card (allowed in «Подробнее» only if explained).
META_PATTERNS = (
    r"\bпредпосылк\w*", r"\bдихотоми\w*", r"\bонтолог\w*", r"\bэпистем\w*", r"\bимманент\w*",
    r"\bтрансцендент\w*", r"\bразличени\w*", r"\bрамк\w*\s+(?:вопроса|ситуации)",
    # M3.3 (LANGUAGE-GUIDE §5): reliable multi-word meta-phrases
    r"\bспособ\w*\s+участи\w*", r"\bструктур\w*\s+отношени\w*", r"\bизменени\w*\s+рамк\w*",
    r"\bоптик\w*\s+текст\w*", r"\bпроблематизир\w*", r"\bустройств\w*\s+действи\w*",
)


def sentences(text: str) -> list[str]:
    return [x for x in re.split(r"(?<=[.!?…])\s+", text.strip()) if x]


def meta_hits(text: str) -> list[str]:
    return [p for p in META_PATTERNS if re.search(p, text, flags=re.IGNORECASE)]


def word_count(text: str) -> int:
    return len(re.findall(r"[\w«»-]+", text))


def jargon_hits(text: str) -> list[str]:
    return [p for p in JARGON_PATTERNS if re.search(p, text, flags=re.IGNORECASE)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


FINAL_CARD_FORMAT = "final-mvp"  # MVP pass 1, final corpus: quote → comment → application → one question
FINAL_LIMITS = {"main_idea": 45, "applied_insight": 55, "reflection_question": 22}
FINAL_MAX_SENTENCES = {"main_idea": 3, "applied_insight": 4}


class Perspective(_Strict):
    card_id: FragmentId
    role: NonEmptyStr  # the philosophical move this card makes in the answer
    title: NonEmptyStr | None = None  # legacy cards only (required there); the final MVP card has no title
    source: NonEmptyStr  # filled from corpus metadata by code
    perspective: NonEmptyStr | None = None  # legacy «Подробнее» (required there); not in the final MVP card
    reflection_question: NonEmptyStr
    why_selected: NonEmptyStr
    main_idea: NonEmptyStr | None = None  # M3.1: what the source thinks, in plain words
    applied_insight: NonEmptyStr | None = None  # M3.1: how it can touch this question
    distinction: NonEmptyStr | None = None  # M3.2, internal: «помогает различить X и Y» / «помогает увидеть …»
    perspective_effect: NonEmptyStr | None = None  # M3.4, internal: what the person sees differently in their question
    perspective_frame: NonEmptyStr | None = None  # M3.4.1, internal: which frame of their question the person explores
    question_explanation: NonEmptyStr | None = None  # M3.2: «Что имеется в виду?» under the reflection question
    # M3.3: attached by CODE only from a READY local-source inventory row (navigator.quotes); never by the model.
    verified_quote: VerifiedQuote | None = None
    # MVP pass 1, final corpus: card format and a VERBATIM excerpt of a long verified quote (checked by code)
    card_format: Literal["final-mvp"] | None = None
    quote_excerpt: NonEmptyStr | None = None

    @field_validator("reflection_question")
    @classmethod
    def _question(cls, v: str) -> str:
        # M3.3: one question, two short linked questions, or a question plus a short clarifying sentence.
        v = v.strip()
        if not 1 <= v.count("?") <= 2:
            raise ValueError("reflection_question must contain one or two short questions")
        return v

    @model_validator(mode="after")
    def _no_advice(self):
        if self.card_format == FINAL_CARD_FORMAT:
            return self._final_checks()
        if self.title is None or self.perspective is None:
            raise ValueError("a legacy card needs title and perspective («Подробнее»)")
        texts = [self.title, self.perspective, self.reflection_question, self.main_idea or "", self.applied_insight or ""]
        hits = advice_hits(" ".join(texts))
        if hits:
            raise ValueError(f"perspective reads as advice/verdict: {hits}")
        if (self.main_idea is None) != (self.applied_insight is None):
            raise ValueError("main_idea and applied_insight come together")
        if self.main_idea is not None:  # M3.1 plain-language card
            for name, limit in WORD_LIMITS.items():
                n = word_count(getattr(self, name))
                if n > limit:
                    raise ValueError(f"{name} is too long for a plain card: {n} words > {limit}")
            jargon = jargon_hits(" ".join([self.title, self.main_idea, self.applied_insight, self.perspective,
                                          self.reflection_question]))
            if jargon:
                raise ValueError(f"internal/technical vocabulary in user-facing card: {jargon}")
        if (self.distinction is None) != (self.question_explanation is None):
            raise ValueError("distinction and question_explanation come together")
        if self.question_explanation is not None:
            self._m32_checks()
        return self

    def _final_checks(self):
        """Final MVP card: comment on the quote, application, exactly ONE short question. No title, no «Подробнее»."""
        if not (self.main_idea and self.applied_insight):
            raise ValueError("the final card needs a comment on the quote (main_idea) and an application")
        rq = self.reflection_question
        if rq.count("?") != 1 or not rq.rstrip().endswith("?") or len(sentences(rq)) != 1:
            raise ValueError("reflection_question must be exactly ONE short question with one «?» — not two questions")
        body = " ".join([self.main_idea, self.applied_insight, rq])
        for check, why in ((advice_hits, "reads as advice/verdict"), (jargon_hits, "internal/technical vocabulary"),
                           (meta_hits, "philosophical meta-language")):
            hits = check(body)
            if hits:
                raise ValueError(f"final card {why}: {hits}")
        for name, limit in FINAL_LIMITS.items():
            n = word_count(getattr(self, name))
            if n > limit:
                raise ValueError(f"{name} is too long: {n} words > {limit}")
        for name, limit in FINAL_MAX_SENTENCES.items():
            if len(sentences(getattr(self, name))) > limit:
                raise ValueError(f"{name} has more than {limit} sentences")
        for name in ("main_idea", "applied_insight"):
            for sent in sentences(getattr(self, name)):
                if word_count(sent) > MAX_SENTENCE_WORDS:
                    raise ValueError(f"{name}: sentence too long to understand on first reading ({word_count(sent)} words)")
        return self

    def _m32_checks(self) -> None:
        """M3.2 structure: declarative title, one simple question, short sentences, no meta-language."""
        if self.main_idea is None:
            raise ValueError("M3.2 card requires main_idea and applied_insight")
        if not re.search(r"различ|увидеть", self.distinction, flags=re.IGNORECASE):
            raise ValueError("distinction must say what the person can distinguish («различить … и …») or see («увидеть …»)")
        if "?" in self.title:
            raise ValueError("title must be a declarative insight, not a question")
        rq = self.reflection_question
        if not 1 <= rq.count("?") <= 2 or len(sentences(rq)) > 2:
            raise ValueError("reflection_question: at most two short sentences with one or two questions")
        if rq.count(",") > 3:
            raise ValueError("reflection_question is syntactically too complex (more than three commas)")
        if "?" in self.question_explanation:
            raise ValueError("question_explanation explains the question; it must not ask new questions")
        for name, limit in M32_LIMITS.items():
            n = word_count(getattr(self, name))
            if n > limit:
                raise ValueError(f"{name} is too long: {n} words > {limit}")
        for name, limit in MAX_SENTENCES.items():
            n = len(sentences(getattr(self, name)))
            if n > limit:
                raise ValueError(f"{name} has {n} sentences > {limit}")
        for name in ("main_idea", "applied_insight", "question_explanation", "reflection_question"):
            for sent in sentences(getattr(self, name)):
                if word_count(sent) > MAX_SENTENCE_WORDS:
                    raise ValueError(f"{name}: sentence too long to understand on first reading ({word_count(sent)} words)")
        meta = meta_hits(" ".join([self.title, self.main_idea, self.applied_insight, self.reflection_question,
                                   self.question_explanation]))
        if meta:
            raise ValueError(f"philosophical meta-language in the main card: {meta}")


class CandidateDecision(_Strict):
    card_id: FragmentId
    reason: NonEmptyStr


class Q1TopDecision(_Strict):
    card_id: FragmentId
    decision: Literal["selected", "rejected"]
    reason: NonEmptyStr


class ComposerMeta(_Strict):
    composer: NonEmptyStr
    model: NonEmptyStr | None = None
    prompt_version: NonEmptyStr
    package_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    attempts: int = Field(ge=1)
    usage: dict[str, Any] = Field(default_factory=dict)


class CompositionResult(_Strict):
    schema_version: Literal["composition/0.1.0", "composition/0.2.0", "composition/0.3.0", "composition/0.4.0",
                            "composition/0.5.0"] = COMPOSITION_SCHEMA_VERSION
    item_id: NonEmptyStr
    retrieval_run_id: NonEmptyStr
    confirmed_question: NonEmptyStr
    candidate_pool: list[FragmentId] = Field(min_length=1)
    opening: Literal["Ваш вопрос можно рассмотреть с нескольких сторон."] = OPENING_LINE
    perspectives: list[Perspective] = Field(min_length=1, max_length=3)  # 1 only for the final corpus (validator)
    fewer_than_three_reason: NonEmptyStr | None = None
    count_reason: NonEmptyStr | None = None  # M3.4, internal: why 2 or why 3 (no burden of proof on 2)
    corpus_version: NonEmptyStr | None = None  # set for the final corpus: its package decides what is excluded
    rejected: list[CandidateDecision] = Field(default_factory=list)
    q1_top: Q1TopDecision
    meta: ComposerMeta

    @model_validator(mode="after")
    def _invariants(self):
        ids = [p.card_id for p in self.perspectives]
        if len(set(ids)) != len(ids):
            raise ValueError("selected cards must be distinct")
        from navigator.corpus.final_corpus import FINAL_CORPUS_VERSION

        if len(ids) < 2 and self.corpus_version != FINAL_CORPUS_VERSION:
            raise ValueError("2 or 3 perspectives are required (a single card is allowed only for the final corpus)")
        pool = set(self.candidate_pool)
        outside = sorted(set(ids) - pool)
        if outside:
            raise ValueError(f"selected cards outside the candidate pool: {outside}")
        from navigator.corpus.policy import excluded_ids_for

        leaked = sorted((set(ids) | {r.card_id for r in self.rejected} | pool) & excluded_ids_for(self.corpus_version))
        if leaked:
            raise ValueError(f"unresolved cards in composition: {leaked}")
        if sorted({r.card_id for r in self.rejected} - pool):
            raise ValueError("rejected cards must come from the candidate pool")
        if set(ids) & {r.card_id for r in self.rejected}:
            raise ValueError("a card cannot be both selected and rejected")
        if self.q1_top.card_id not in pool:
            raise ValueError("q1_top card must be in the candidate pool")
        if (self.q1_top.decision == "selected") != (self.q1_top.card_id in ids):
            raise ValueError("q1_top decision contradicts the selection")
        if self.schema_version != "composition/0.1.0" and any(p.main_idea is None for p in self.perspectives):
            raise ValueError("composition/0.2.0 requires main_idea and applied_insight in every perspective")
        if self.schema_version in ("composition/0.3.0", "composition/0.4.0", "composition/0.5.0") and any(
                p.question_explanation is None and p.card_format is None for p in self.perspectives):
            raise ValueError("composition/0.3.0 requires distinction and question_explanation in every perspective")
        if len(ids) == 2 and not self.fewer_than_three_reason and self.schema_version != "composition/0.5.0":
            raise ValueError("returning 2 perspectives requires fewer_than_three_reason")
        return self

    def user_text(self) -> str:
        parts = [self.opening, ""]
        for i, p in enumerate(self.perspectives, 1):
            if p.main_idea:
                parts += [f"**{i}. {p.title or p.source}**", f"*{p.source}*", "", p.main_idea, "", p.applied_insight,
                          "", f"→ {p.reflection_question}", ""]
            else:
                parts += [f"**{i}. {p.title}**", f"*{p.source}*", "", p.perspective, "", f"→ {p.reflection_question}", ""]
        return "\n".join(parts).rstrip() + "\n"

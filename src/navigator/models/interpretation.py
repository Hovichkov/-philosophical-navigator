"""Interpretation layer contract (M2.6).

Turns simple structured input + a free narrative into a PROPOSED question,
2–4 internal working hypotheses and a semantic annotation for the existing
QueryRepresentation. Natural language carries the meaning; coordinates and
tensions are an annotation added afterwards, never the other way round.

Boundaries enforced here:
- ``proposed_question`` is never a confirmed question. A question becomes
  confirmed only through an explicit ``Confirmation`` (user action, or a
  clearly marked benchmark simulation).
- working hypotheses are internal retrieval material, not shown to the user and
  not facts about the person.
- there is no diagnosis field and no advice field (``extra="forbid"``).
- coordinates / canonical tensions come only from TAXONOMY v1.1; other
  tensions go to ``free_tensions`` and never extend the taxonomy.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

from navigator.models.vocabularies import COORDINATES, TENSIONS

NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]

INTERPRETATION_SCHEMA_VERSION = "interpretation/0.1.0"
MIN_NARRATIVE_WORDS = 8

# Clinical / psychologizing labels that must not be asserted about the person or others
# unless the user used the word themselves (heuristic guard, M2.6 §2, §14).
DIAGNOSTIC_TERMS = (
    "расстройств", "диагноз", "гиперопек", "гиперконтрол", "созависим", "нарцисс", "депресси",
    "невроз", "невротич", "травм", "патолог", "психопат", "биполяр", "паническ",
)
ADVICE_PATTERNS = (
    r"\bвам следует\b", r"\bвам нужно\b", r"\bвы должны\b", r"\bвам надо\b", r"\bправильное решение\b",
    r"\bобратитесь к\b", r"\bсходите к\b", r"\bпопробуйте\b", r"\bрекомендую\b", r"\bлечени",
)


def diagnostic_hits(text: str, narrative: str) -> list[str]:
    low, nar = text.lower(), narrative.lower()
    return [t for t in DIAGNOSTIC_TERMS if t in low and t not in nar]


def advice_hits(text: str) -> list[str]:
    return [p for p in ADVICE_PATTERNS if re.search(p, text, flags=re.IGNORECASE)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InterpretationInput(_Strict):
    topic: NonEmptyStr
    experiences: list[NonEmptyStr] = Field(default_factory=list)
    difficulty_center: NonEmptyStr  # free text; no closed global list is assumed
    free_narrative: StrictStr = ""


class ReadingNote(_Strict):
    """What the interpreter noticed in the narrative, before any hypothesis."""

    kind: Literal["representation", "expectation", "tension", "boundary", "ambiguity", "context"]
    note: NonEmptyStr


class InterpretationTrace(_Strict):
    interpreter: NonEmptyStr
    model: NonEmptyStr | None = None
    prompt_version: NonEmptyStr
    input_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    reading_notes: list[ReadingNote] = Field(default_factory=list)
    attempts: int = Field(ge=0)
    usage: dict[str, Any] = Field(default_factory=dict)


class InterpretationResult(_Strict):
    schema_version: Literal["interpretation/0.1.0"] = INTERPRETATION_SCHEMA_VERSION
    status: Literal["interpreted"] = "interpreted"
    input: InterpretationInput
    proposed_question: NonEmptyStr  # shown to the user for confirmation
    other_questions: list[NonEmptyStr] = Field(default_factory=list, max_length=2)  # MVP flow: independent ones
    working_hypotheses: list[NonEmptyStr] = Field(min_length=2, max_length=4)  # internal only
    coordinates: list[NonEmptyStr] = Field(default_factory=list)
    canonical_tensions: list[NonEmptyStr] = Field(default_factory=list)
    free_tensions: list[NonEmptyStr] = Field(default_factory=list)
    ambiguity_notes: list[NonEmptyStr] = Field(default_factory=list)
    trace: InterpretationTrace

    @field_validator("coordinates")
    @classmethod
    def _coords(cls, v):
        bad = [c for c in v if c not in COORDINATES]
        if bad or len(set(v)) != len(v):
            raise ValueError(f"coordinates must be distinct TAXONOMY v1.1 values: {bad}")
        return v

    @field_validator("canonical_tensions")
    @classmethod
    def _canon(cls, v):
        bad = [t for t in v if t not in TENSIONS]
        if bad or len(set(v)) != len(v):
            raise ValueError(f"canonical_tensions must be distinct TAXONOMY v1.1 tensions: {bad}")
        return v

    @field_validator("free_tensions")
    @classmethod
    def _free(cls, v):
        if any(t in TENSIONS for t in v):
            raise ValueError("canonical tensions must not be listed as free_tensions")
        if any("↔" not in t for t in v):
            raise ValueError("free tensions follow the 'A ↔ B' convention")
        return v

    @model_validator(mode="after")
    def _guards(self):
        q = self.proposed_question.strip()
        if not q.endswith("?"):
            raise ValueError("proposed_question must be a question")
        text = " ".join([q, *self.working_hypotheses])
        diag = diagnostic_hits(text, self.input.free_narrative + " " + self.input.difficulty_center)
        if diag:
            raise ValueError(f"diagnostic/clinical labels not used by the user: {diag}")
        adv = advice_hits(text)
        if adv:
            raise ValueError(f"advice/recommendation phrasing: {adv}")
        if not self.coordinates:
            raise ValueError("at least one coordinate is required for STRUCTURE retrieval")
        return self


class InsufficientInterpretation(_Strict):
    """Explicit outcome when the input does not allow an honest interpretation."""

    schema_version: Literal["interpretation/0.1.0"] = INTERPRETATION_SCHEMA_VERSION
    status: Literal["insufficient_input"] = "insufficient_input"
    input: InterpretationInput
    reason: NonEmptyStr
    clarification_prompt: NonEmptyStr  # neutral request for more detail, not a hypothesis
    trace: InterpretationTrace


class Confirmation(_Strict):
    """The only way a proposed question becomes a confirmed question."""

    # confirmed: «Да, это мой вопрос»; edited: «Частично» (user edits the proposal);
    # replaced: «Нет, мой вопрос о другом» + the user's own question; rejected: no question yet.
    action: Literal["confirmed", "edited", "replaced", "rejected"]
    source: Literal["user", "benchmark_simulation"]
    proposed_question: NonEmptyStr
    confirmed_question: NonEmptyStr | None = None
    edited_text: NonEmptyStr | None = None

    @model_validator(mode="after")
    def _consistent(self):
        if self.action == "confirmed" and self.confirmed_question != self.proposed_question:
            raise ValueError("a confirmed question equals the proposed question")
        if self.action in ("edited", "replaced"):
            if not self.edited_text or self.confirmed_question != self.edited_text:
                raise ValueError(f"an {self.action} confirmation uses the user's own text")
        if self.action == "rejected" and self.confirmed_question is not None:
            raise ValueError("a rejected proposal yields no confirmed question")
        return self


# ------------------------------------------------------------------ amplification guard (M3)
# INTERNAL working hypotheses may be bold. USER-FACING text (proposed question, composed
# perspectives) must keep them hypotheses: no unconfirmed claim about the person's motive,
# attitude or hidden reason stated as fact. Heuristic patterns; the prompt is the main guard.
AMPLIFICATION_PATTERNS = (
    # M3.3: only when addressed to the person («вы на самом деле…», «на самом деле вам…»); the conversational
    # voice uses «на самом деле» about sources too («Эпиктет показывает, что на самом деле…»).
    r"\b(?:вы|вам|вас|ваш\w*)\b[^.?!]{0,40}на самом деле|на самом деле[^.?!]{0,40}\b(?:вы|вам|вас|ваш\w*)\b",
    r"за этим (?:стоит|скрывается|прячется)",
    r"\bвы (?:просто |лишь |всего лишь )?(?:отмахиваетесь|избегаете|прячетесь|убегаете|цепляетесь|"
    r"пытаетесь контролировать|не хотите видеть|не готовы признать)",
    r"\bвам невыносимо\b",
    r"\bпотому что вам (?:страшно|невыносимо|стыдно)\b",
    r"\bне отмахиваясь\b",
)

AMPLIFICATION_RULE = (
    "Внутренние рабочие гипотезы могут быть смелыми. Но в тексте, который увидит человек, не превращай "
    "неподтверждённую гипотезу в факт о нём, его мотиве или отношении. Держи её гипотезой: "
    "«Можно исследовать, какую роль для вас играет надежда, что это пройдёт» — допустимо; "
    "«Вы отмахиваетесь надеждой, что это пройдёт» — нельзя. "
    "«Можно проверить, связано ли желание вмешаться ещё и с тем, насколько трудно вам выдерживать происходящее» — допустимо; "
    "«Вам невыносимо происходящее, поэтому вы пытаетесь контролировать» — нельзя. "
    "Не приписывай человеку оценок его собственных слов (например, не называй его надежду «отмахиванием»), "
    "которых он сам не делал."
)


# M3.1: user-facing text must not explain the psychological FUNCTION of the person's feeling
# or reaction ("вина помогает сделать происходящее понятным", "даёт ощущение контроля"),
# even hedged with «может», «возможно», «если». Such readings stay internal hypotheses.
_FEELINGS = (r"(?:вин[аыуе]|чувств\w* вины|страх\w*|тревог\w*|стыд\w*|гнев\w*|злост\w*|обид\w*|"
             r"надежд\w*|желани\w*|реакци\w*|беспокойств\w*|забот\w*|контрол\w*)")
PSYCH_FUNCTION_PATTERNS = (
    r"\bспособом\s+(?:сделать|избежать|не\s|удержать|сохранить|вернуть|почувствовать|защитить|"
    r"справиться|объяснить|пережить|заглушить)",
    r"\b(?:может|могут|могла бы|мог бы|могло бы)\s+(?:оказаться|быть|служить|стать)\s+[^.?!]{0,40}?"
    r"(?:способом|попыткой|защитой|формой контроля|опорой)\b",
    r"\bда[её]т\s+(?:вам\s+)?(?:ощущение|чувство|иллюзию)\s+(?:контроля|причастности|влияния|власти|безопасности|опоры)",
    r"\bиллюзи\w+\s+контроля\b",
    r"\bпопытк\w+\s+(?:вернуть|удержать|сохранить|обрести)\s+контрол",
    r"\bчтобы\s+не\s+(?:чувствовать|видеть|признавать|сталкиваться|замечать)",
    r"\b" + _FEELINGS + r"\s+[^.?!]{0,40}?\b(?:служит|помогает вам|позволяет вам|защищает вас|работает как|"
    r"выполняет (?:роль|функцию)|нужн\w* (?:вам|чтобы))",
)

PSYCH_FUNCTION_RULE = (
    "Не объясняй в пользовательском тексте психологическую функцию чувства или реакции человека — зачем она ему, "
    "что она ему даёт, от чего защищает, — даже через «может», «возможно» или «если». "
    "Нельзя: «вина может оказаться способом сделать происходящее понятным», «вина даёт ощущение контроля», "
    "«тревога помогает вам не чувствовать беспомощность». Такие толкования остаются внутренними гипотезами. "
    "Можно: опереться на слова человека («вы пишете: „мне кажется, я виновата“») и показать, что говорит источник, "
    "оставив вывод человеку или задав вопрос."
)


# M3.2: one conceptual rule for every user-facing field (proposed question, title, main idea, applied
# insight, reflection question, question explanation, «Подробнее»). Enforced by the prompts, not by regex.
INTERNAL_CLAIM_RULE = (
    "Не утверждай о человеке как о факте того, чего он не сказал и не подтвердил: скрытый мотив, функцию чувства, "
    "внутреннюю потребность, непризнанную часть личности, зависимость самооценки, причину реакции, "
    "биографический факт, сравнение себя с другими, страх или желание. "
    "Новая философская рамка допустима; новый факт о человеке — нет. Не достраивай за человека конфликт, "
    "которого нет в его словах, даже если источник с таким конфликтом связан (например, не вводи сравнение "
    "с чужими доходами, если человек говорил только о своей работе и долгах). "
    "Формула «можно проверить, связано ли для вас X с Y» допустима, но не протаскивай через неё произвольную "
    "психологическую гипотезу. Приоритет: философское различение важнее психологического толкования."
)


def amplification_hits(text: str) -> list[str]:
    """Amplification (M3) and psychological-function (M3.1) patterns found in user-facing text."""
    return [p for p in (*AMPLIFICATION_PATTERNS, *PSYCH_FUNCTION_PATTERNS) if re.search(p, text, flags=re.IGNORECASE)]

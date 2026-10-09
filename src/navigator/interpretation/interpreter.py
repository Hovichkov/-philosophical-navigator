"""Interpretation engine (M2.6).

raw input → reading notes (representations / expectations / tensions) → 2–4 working
hypotheses → ONE proposed question → semantic annotation (coordinates, tensions).

Runtime: the local Claude Code CLI in headless mode (``claude -p``) under the user's
existing Claude login — the same mechanism as M2.5 composition; no API key, no new
service. Structured output via JSON schema, validated by ``InterpretationResult``;
one repair attempt with the validation error.

Deterministic pre-check: a narrative shorter than ``MIN_NARRATIVE_WORDS`` yields an
explicit ``InsufficientInterpretation`` without calling the model.

``confirm`` and ``to_query_representation`` keep the proposed/confirmed boundary:
only a Confirmation turns a proposed question into ``confirmed_question`` of the
existing ``QueryRepresentation``.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Protocol

from pydantic import ValidationError

from navigator.language import (
    LANGUAGE_RULES,
    added_causal_question,
    anchor_shift_hits,
    gendered_first_person_hits,
    person_gender,
    sentence_count,
    unnamed_person_claims,
)
from navigator.timing import cli_error_message, cli_usage
from navigator.models.interpretation import (
    AMPLIFICATION_RULE,
    PSYCH_FUNCTION_RULE,
    INTERNAL_CLAIM_RULE,
    MIN_NARRATIVE_WORDS,
    amplification_hits,
    Confirmation,
    InsufficientInterpretation,
    InterpretationInput,
    InterpretationResult,
    InterpretationTrace,
    ReadingNote,
)
from navigator.models.query import QueryProvenance, QueryRepresentation, UserContext
from navigator.models.vocabularies import COORDINATES, TENSIONS

PROMPT_VERSION = "interpretation-prompt/0.12.0"  # MVP flow: story first; other questions + one clarifying question
INTERPRETER_VERSION = "interpretation-layer/0.1.0"
DEFAULT_MODEL = "claude-opus-5-5"

CLARIFICATION_PROMPT = (
    "Расскажите, пожалуйста, чуть подробнее, что происходит и что в этом для вас самое трудное — "
    "так мы сможем точнее сформулировать ваш вопрос."
)


# MVP pass 1: the model could not understand the story at all (not merely «too short»)
UNCLEAR_PROMPT = ("Я не совсем понял, что именно вас беспокоит. Попробуйте описать ситуацию простыми словами: "
                  "что произошло и что в этом для вас трудно.")


def input_sha256(inp: InterpretationInput) -> str:
    return hashlib.sha256(inp.model_dump_json().encode("utf-8")).hexdigest()


SYSTEM_PROMPT = f"""Ты — слой интерпретации философского навигатора. Человек своими словами рассказал о ситуации и, возможно, отметил свои чувства (переживания). Тема и «центр трудности» могут быть не выбраны — тогда в них стоит «Другое», и центр трудности ты находишь в самом рассказе. Твоя задача — подготовить философское исследование его вопроса, а не решить его жизнь.

Принципы:
- Не бывает объективно «плохих» и «хороших» обстоятельств. Предмет исследования — отношение человека к обстоятельству, представления, через которые он его понимает, ожидания, напряжения между ценностями, обязанностями и желаниями, границы действия, контроля и принятия.
- Ты не ищешь «правильную психологическую причину». Ты видишь несколько возможных смысловых структур ситуации.
- Никаких диагнозов (ни человека, ни других людей), никаких клинических ярлыков, даже если человек сам их употребил. Никаких медицинских, юридических, финансовых рекомендаций. Если человек сообщил, что профессиональная помощь уже запланирована, не комментируй это.
- Не решай за человека спорные факты (например, «возрастное это или нет»). Не приписывай ему скрытых мотивов как факт («вы слишком контролируете»).
- Никаких советов.
- Чувства. Переживания (experiences), которые человек выбрал сам, — его собственное указание на то, что он чувствует; именно чувства приводят человека к такому вопросу. Рабочие гипотезы ОБЯЗАТЕЛЬНО учитывают названные чувства: с каким напряжением ситуации может быть связано каждое существенное из них (тревога — с неизвестностью, злость — с нарушенным ожиданием и т. п. — только как возможность, не как диагноз). Не вставляй чувства в вопрос механически; если чувство центрально, его можно назвать его же словом.
- Смысл важнее гладкости. Сохраняй значимые детали рассказа, особенно эмоционально заряженные, даже если человек пишет разговорно, грубо или неровно: оценку другого человека, сравнение себя с кем-то, обидное слово, ощущение несправедливости. Такую деталь передай нейтрально или его же словами в кавычках (например: «она говорит, что любит другого, а он, по-моему, “чувырло”»). Не объясняй её и не называй за человека психологическим словом («ревность», «зависть»), если он сам так не сказал; в рабочих гипотезах её смысл можно рассмотреть как возможность.
- Граница «внутреннее / пользовательское»: working_hypotheses — внутренние, proposed_question — пользовательский текст. {AMPLIFICATION_RULE} {PSYCH_FUNCTION_RULE} {INTERNAL_CLAIM_RULE}

Порядок работы (естественный язык — главный носитель смысла):
1. reading_notes: 3–6 коротких наблюдений о рассказе — какие представления, ожидания, напряжения, границы, неоднозначности в нём видны. Только то, что опирается на текст.
2. working_hypotheses: 2–4 коротких рабочих гипотезы для поиска философских текстов. Это внутренний материал, человек их не увидит. Формулируй как возможности («возможно, …», «забота может переживаться как …»), они могут противоречить друг другу.
3. proposed_question: ОДНА основная формулировка вопроса, которую человек увидит как свой вопрос перед философским ответом. Требования:
   - узнаваемая для человека и сохраняет конкретику его ситуации (кто участвует, что происходит), если она важна;
   - поднимает ситуацию до исследуемого вопроса: называет центральное напряжение или предел (например, между заботой и контролем, между желанием и долгом, между действием и тем, что от меня не зависит, между собственной оценкой и чужим взглядом);
   - если центр трудности выбран (не «Другое»), это собственное указание человека, в чём именно трудность: его смысл ОБЯЗАТЕЛЬНО должен присутствовать в вопросе, но перефразированным и встроенным в конкретную ситуацию, а не дословной копией;
   - не спрашивает «что мне делать», «как мне реагировать», «как решить» — это запрос решения, а не исследование;
   - если в рассказе есть близкий человек, сохраняет отношение к нему (как быть с ним, рядом с ним, по отношению к нему);
   - не абстрактный лозунг, не подсказывает решение, не диагностирует, не приписывает мотив, не содержит клинических слов и медицинских вопросов.
   Плохо: «Как научиться отпускать контроль?» — слишком общо и уже предполагает диагноз и решение. Лучше: «Как действовать в ситуации, где от меня многое зависит, но я не могу гарантировать результат?» — но с конкретикой человека, когда она важна.
   Пиши от первого лица человека, обычным разговорным русским. Вопрос НЕ обязан быть одним предложением: если в нём несколько связанных частей, раздели их на 2–3 коротких предложения (одно может описывать ситуацию, остальные — вопросы). НИКОГДА не больше трёх предложений: четыре и больше — ошибка, ответ будет отклонён. Удерживай главный конфликт и смысл вопроса самого человека; не подменяй его новой философской рамкой; не пересказывай всю историю, но значимую эмоционально заряженную деталь не выбрасывай (см. «Смысл важнее гладкости»). Не добавляй чувств, которых человек не называл (если он пишет «стыдно», не пиши «страшно»), и не упоминай специалистов, если он о них не писал. Не добавляй новых фактов ни о человеке, ни о других людях из рассказа: их мотивов, мыслей, способностей, «свободного выбора», а также вариантов действия, которых человек не называл. Вопрос может собирать, уточнять, структурировать и делать явным то, что уже есть в словах человека, но НЕ добавляет новой исследовательской задачи: если человек назвал чувство или обстоятельство («стыдно», «боюсь»), но не спрашивал о причине, не превращай это в «почему мне стыдно?», «из-за чего…», «что заставляет меня…», «на самом ли деле я…». Если человек сам спросил «почему» — сохрани. Если пол человека не виден из его слов, пиши без форм, зависящих от рода («я готов», «я решила» — нельзя; перестрой фразу, без «готов(а)»). Сохраняй опорные слова человека, если замена меняет смысл: выбрал «трудно принять» — не пиши «трудно смириться». Напряжение называй его собственными словами: если он пишет «ученик идёт в отказ», не превращай это в выбор «помогать или уважать его отказ», пока сам человек так вопрос не ставил. Последнее предложение оканчивается «?».
   Плохо (слишком тяжело читать): «Когда я хочу быть продуктивной, но снова и снова упираюсь в пределы своих возможностей, как понять, какая я — где мои границы, с которыми стоит примириться, а где то, ради чего стоит продолжать пытаться, — и чем тогда отличается бережность к себе от отказа от себя?»
   Лучше (это пример принципа, а не шаблон): «Я хочу быть продуктивной, но снова упираюсь в пределы своих возможностей. Как понять, где мои реальные границы, а где стоит продолжать пытаться? И чем бережность к себе отличается от отказа от себя?»
3a. other_questions: если в рассказе есть ещё 1–2 САМОСТОЯТЕЛЬНЫХ вопроса — о другом предмете или другой трудности, которые нельзя честно соединить с основным в одну формулировку, — запиши их сюда по тем же требованиям, что и proposed_question (proposed_question — главный, о котором человек говорит больше всего). Части одного вопроса, уточнения и связанные стороны одной трудности — НЕ самостоятельные вопросы: они остаются в proposed_question. В большинстве рассказов вопрос один — тогда other_questions пустой.
4. Семантическая разметка — только после вопроса:
   - coordinates: 2–5 значений строго из списка: {", ".join(sorted(COORDINATES))};
   - canonical_tensions: 0–3 строго из списка: {"; ".join(sorted(TENSIONS))};
   - free_tensions: 0–3 важных напряжения вне списка, в формате «A ↔ B».
5. ambiguity_notes: 0–3 заметки о неоднозначностях ввода (например, центр трудности расходится с рассказом).

{LANGUAGE_RULES}

Понятен ли рассказ. Проверка: можешь ли ты обычными словами, БЕЗ бессмысленных или шуточных слов из рассказа, сказать, что происходит (чего человек хочет, что случилось, кто участвует) и в чём для него трудность?
- Да, хотя часть рассказа непонятна или написана неровно, грубо, с опечатками → sufficient=true. Достаточно, если обычными словами названо, чего человек хочет ИЛИ что произошло, и видна трудность (например, ясно сказано «хочу быть с нею», а она отвечает «нет»). Строй вопрос только по этой понятной части, непонятное не додумывай и отметь в ambiguity_notes.
- Нет: ни желание человека, ни событие не названы обычными словами; понятны лишь обрывки реплик и общая эмоция; вопрос пришлось бы строить на самих бессмысленных словах → sufficient=false. Никогда не вставляй бессмысленные слова из рассказа в вопрос.
При sufficient=false коротко объясни insufficiency_reason и задай в clarifying_question ОДИН короткий уточняющий вопрос человеку (на «вы», одно предложение, оканчивается «?»), опираясь на понятную часть рассказа, если она есть; бессмысленные слова в него не вставляй. Остальные поля заполни минимально. При sufficient=true clarifying_question = null.

Пиши по-русски. Отвечай строго по JSON-схеме."""

MAX_OTHER_QUESTIONS = 2  # MVP flow: at most three independent questions in one story

OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["sufficient", "insufficiency_reason", "reading_notes", "working_hypotheses", "proposed_question",
                 "coordinates", "canonical_tensions", "free_tensions", "ambiguity_notes", "other_questions",
                 "clarifying_question"],
    "properties": {
        "sufficient": {"type": "boolean"},
        "insufficiency_reason": {"type": ["string", "null"]},
        "reading_notes": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False, "required": ["kind", "note"],
                "properties": {
                    "kind": {"type": "string", "enum": ["representation", "expectation", "tension", "boundary", "ambiguity", "context"]},
                    "note": {"type": "string"},
                },
            },
        },
        "working_hypotheses": {"type": "array", "items": {"type": "string"}, "minItems": 0, "maxItems": 4},
        "proposed_question": {"type": "string"},
        "coordinates": {"type": "array", "items": {"type": "string", "enum": sorted(COORDINATES)}},
        "canonical_tensions": {"type": "array", "items": {"type": "string", "enum": sorted(TENSIONS)}},
        "free_tensions": {"type": "array", "items": {"type": "string"}},
        "ambiguity_notes": {"type": "array", "items": {"type": "string"}},
        "other_questions": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_OTHER_QUESTIONS},
        "clarifying_question": {"type": ["string", "null"]},
    },
}


class InterpreterUnavailable(RuntimeError):
    pass


class Interpreter(Protocol):
    name: str
    model: str | None

    def complete(self, inp: InterpretationInput, feedback: str | None = None) -> tuple[dict, dict]:
        ...


@dataclass
class ClaudeCodeCLIInterpreter:
    model: str = DEFAULT_MODEL
    timeout_s: int = 600
    name: str = "claude-code-cli"

    def complete(self, inp: InterpretationInput, feedback: str | None = None) -> tuple[dict, dict]:
        user = "Ввод пользователя (JSON):\n" + inp.model_dump_json(indent=1)
        if feedback:
            user += "\n\nПредыдущий ответ не прошёл проверку контракта. Исправь и ответь заново. Ошибка:\n" + feedback
        cmd = [
            "claude", "-p", "--safe-mode", "--tools", "", "--strict-mcp-config", "--no-session-persistence",
            "--model", self.model, "--system-prompt", SYSTEM_PROMPT,
            "--output-format", "json", "--json-schema", json.dumps(OUTPUT_SCHEMA, ensure_ascii=False),
        ]
        t0 = time.monotonic()
        try:
            proc = subprocess.run(cmd, input=user, capture_output=True, text=True, timeout=self.timeout_s)
            payload = json.loads(proc.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            raise InterpreterUnavailable(str(exc)[:500]) from exc
        if payload.get("is_error") or not isinstance(payload.get("structured_output"), dict):
            raise InterpreterUnavailable(cli_error_message(payload))
        return payload["structured_output"], cli_usage(payload, time.monotonic() - t0)


def user_words(inp: InterpretationInput) -> str:
    """Everything the person said or chose — the only ground for claims about them."""
    return " ".join([inp.topic, inp.difficulty_center, *inp.experiences, inp.free_narrative])


def _word_count(text: str) -> int:
    return len(re.findall(r"\w+", text))


def interpret(inp: InterpretationInput, interpreter: Interpreter, max_attempts: int = 2
              ) -> InterpretationResult | InsufficientInterpretation:
    sha = input_sha256(inp)
    if _word_count(inp.free_narrative) < MIN_NARRATIVE_WORDS:
        return InsufficientInterpretation(
            input=inp,
            reason=f"free narrative has fewer than {MIN_NARRATIVE_WORDS} words (deterministic pre-check)",
            clarification_prompt=CLARIFICATION_PROMPT,
            trace=InterpretationTrace(interpreter="deterministic-precheck", prompt_version=PROMPT_VERSION,
                                      input_sha256=sha, attempts=0),
        )
    feedback = None
    calls: list[dict] = []
    repairs: list[str] = []  # M3.3.1: why each earlier attempt was rejected
    for attempt in range(1, max_attempts + 1):
        out, usage = interpreter.complete(inp, feedback)
        calls.append(usage)
        try:
            notes = [ReadingNote(**n) for n in out.get("reading_notes", [])]
            trace = InterpretationTrace(
                interpreter=interpreter.name, model=interpreter.model, prompt_version=PROMPT_VERSION,
                input_sha256=sha, reading_notes=notes, attempts=attempt,
                usage={"calls": calls, "repairs": list(repairs)},
            )
            if not out.get("sufficient", True):
                return InsufficientInterpretation(
                    input=inp, reason=(out.get("insufficiency_reason") or "model reported insufficient input").strip(),
                    clarification_prompt=clarifying_question(out.get("clarifying_question")) or UNCLEAR_PROMPT,
                    trace=trace,
                )
            pq = out["proposed_question"].strip()
            others = list(dict.fromkeys(q.strip() for q in out.get("other_questions") or [] if q.strip()
                                        and q.strip() != pq))[:MAX_OTHER_QUESTIONS]
            check_question(pq, inp)
            # another independent question that breaks the contract is dropped (never a repair call for it)
            others = [q for q in others if _passes(q, inp)]
            return InterpretationResult(
                input=inp,
                proposed_question=pq,
                other_questions=others,
                working_hypotheses=[h.strip() for h in out["working_hypotheses"]],
                coordinates=list(dict.fromkeys(out["coordinates"])),
                canonical_tensions=list(dict.fromkeys(out["canonical_tensions"])),
                free_tensions=list(dict.fromkeys(t.strip() for t in out["free_tensions"])),
                ambiguity_notes=[a.strip() for a in out.get("ambiguity_notes", []) if a.strip()],
                trace=trace,
            )
        except (ValidationError, ValueError, KeyError, TypeError) as exc:
            feedback = str(exc)[:1500]
            repairs.append(feedback)
    raise ValueError(f"interpretation failed validation after {max_attempts} attempts: {feedback}")


def clarifying_question(text: str | None) -> str | None:
    """MVP flow: the model's ONE short clarifying question (shown as is); anything else → the generic prompt."""
    q = (text or "").strip()
    if not q or not q.endswith("?") or q.count("?") != 1 or sentence_count(q) > 2 or len(q) > 300:
        return None
    return q


def _passes(question: str, inp: InterpretationInput) -> bool:
    try:
        check_question(question, inp)
        return True
    except ValueError:
        return False


def check_question(pq: str, inp: InterpretationInput) -> None:
    """The contract of every question shown to the person (the main one and each other independent one)."""
    hits = amplification_hits(pq)
    if hits:
        raise ValueError(f"proposed_question states an unconfirmed hypothesis about the person as fact: {hits}")
    # M3.3.1: the 2–3 sentence rule is a contract, not only a prompt wish (R01 got 4 in M3.3).
    if sentence_count(pq) > 3:
        raise ValueError(f"proposed_question has {sentence_count(pq)} sentences; at most 3 short ones")
    unnamed = unnamed_person_claims(pq, user_words(inp))
    if unnamed:
        raise ValueError(f"proposed_question adds what the person did not name: {unnamed}")
    causal = added_causal_question(pq, user_words(inp))
    if causal:
        raise ValueError("proposed_question adds a causal question the person did not ask "
                         f"({[c.replace(chr(92) + 'b', '') for c in causal]}); keep their feeling as they said it, "
                         "without «почему / из-за чего»")
    if person_gender(user_words(inp)) is None and gendered_first_person_hits(pq):
        raise ValueError(f"the person's gender is unknown, but proposed_question uses gendered forms: "
                         f"{gendered_first_person_hits(pq)[:3]}; rephrase neutrally")
    shifted = anchor_shift_hits(pq, user_words(inp))
    if shifted:
        raise ValueError(f"proposed_question replaces the person's word {shifted} with a near-synonym that "
                         "changes the frame («принять» is not «смириться»); keep their word")


def confirm(result: InterpretationResult, action: str = "confirmed", source: str = "user",
            edited_text: str | None = None) -> Confirmation:
    confirmed = {"confirmed": result.proposed_question, "edited": edited_text, "replaced": edited_text,
                 "rejected": None}[action]
    return Confirmation(action=action, source=source, proposed_question=result.proposed_question,
                        confirmed_question=confirmed, edited_text=edited_text)


def to_query_representation(result: InterpretationResult, confirmation: Confirmation,
                            item_id: str | None = None) -> QueryRepresentation:
    """Only a confirmed/edited question enters retrieval (proposed ≠ confirmed)."""
    if confirmation.confirmed_question is None:
        raise ValueError("the proposed question was rejected; there is no confirmed question for retrieval")
    if confirmation.proposed_question != result.proposed_question:
        raise ValueError("confirmation belongs to another interpretation")
    simulated = confirmation.source == "benchmark_simulation"
    provenance = QueryProvenance(
        origin="benchmark_adapter" if simulated else "production",
        confirmed_question_source="benchmark_simulated_user_confirmation" if simulated else f"user_{confirmation.action}",
        interpretation_source=("benchmark_run_of_" if simulated else "") + INTERPRETER_VERSION.replace("/", "_"),
        benchmark_item_id=item_id if simulated else None,
        note="M2.6 interpretation layer; confirmation simulated for benchmark" if simulated else None,
    )
    inp = result.input
    return QueryRepresentation(
        confirmed_question=confirmation.confirmed_question,
        context=UserContext(circumstance=inp.topic, narrative=inp.free_narrative or None),
        experiences=inp.experiences,
        working_hypotheses=result.working_hypotheses,
        coordinates=result.coordinates,
        canonical_tensions=result.canonical_tensions,
        free_tensions=result.free_tensions,
        provenance=provenance,
    )

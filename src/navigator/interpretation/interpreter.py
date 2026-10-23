"""Interpretation engine (M2.6).

raw input → reading notes (representations / expectations / tensions) → 2–4 working
hypotheses for each proposed question → semantic annotation (coordinates, tensions).

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

PROMPT_VERSION = "interpretation-prompt/0.15.0"  # 2026-10-23: the visible question is the person's own, only split
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
- Чувства. Переживания (experiences), которые человек выбрал сам, — его собственное указание на то, что он чувствует; именно чувства приводят человека к такому вопросу. Рабочие гипотезы ОБЯЗАТЕЛЬНО учитывают названные чувства: с каким напряжением ситуации может быть связано каждое существенное из них (тревога — с неизвестностью, злость — с нарушенным ожиданием и т. п. — только как возможность, не как диагноз). Чувства — дополнительная информация для поиска, а НЕ часть вопроса: в proposed_question и other_questions их не вставляй.
- Смысл важнее гладкости. Сохраняй значимые детали рассказа, особенно эмоционально заряженные, даже если человек пишет разговорно, грубо или неровно: оценку другого человека, сравнение себя с кем-то, обидное слово, ощущение несправедливости. Такую деталь передай нейтрально или его же словами в кавычках (например: «она говорит, что любит другого, а он, по-моему, “чувырло”»). Не объясняй её и не называй за человека психологическим словом («ревность», «зависть»), если он сам так не сказал; в рабочих гипотезах её смысл можно рассмотреть как возможность.
- Граница «внутреннее / пользовательское»: working_hypotheses — внутренние, proposed_question — пользовательский текст. {AMPLIFICATION_RULE} {PSYCH_FUNCTION_RULE} {INTERNAL_CLAIM_RULE}

Порядок работы (естественный язык — главный носитель смысла):
1. reading_notes: 3–6 коротких наблюдений о рассказе — какие представления, ожидания, напряжения, границы, неоднозначности в нём видны. Только то, что опирается на текст.
2. working_hypotheses: 2–4 коротких рабочих гипотезы для поиска философских текстов именно по proposed_question. Это внутренний материал, человек их не увидит. Формулируй как возможности («возможно, …», «забота может переживаться как …»), они могут противоречить друг другу.
3. proposed_question: ОДНА основная формулировка вопроса, которую человек увидит как свой вопрос перед философским ответом.
   ГЛАВНОЕ: этот шаг не переформулирует вопрос, а только отделяет вопросы человека друг от друга. Если человек сам задал вопрос, proposed_question — ЕГО вопрос ЕГО словами: можно оставить одно предложение о ситуации, если без него вопрос непонятен, и убрать лишнее, но нельзя добавлять, обобщать, «поднимать» до напряжения, менять опорные слова и вставлять чувства. Если в его словах несколько РАЗНЫХ вопросов, первый — в proposed_question, остальные — в other_questions, каждый тоже его словами. Два связанных вопроса об одном (например, «как говорить с ним» и «как мне при этом держаться») — это один вопрос: не дели его.
   Требования ниже применяй ТОЛЬКО если человек сам не задал вопроса и его нужно сформулировать из рассказа:
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
3a. other_questions: ТОЛЬКО другие вопросы, которые человек сам задал или прямо поставил в своих словах и которые отделены от proposed_question (до трёх). Никаких новых ракурсов, альтернатив, «других сторон проблемы» и вопросов, которых он не задавал: обычно этот список пуст. Каждый вопрос — законченное грамматически правильное предложение, понятное без рассказа. Не выдавай скрытые мотивы за факт.
3b. other_question_hypotheses: для каждого вопроса из other_questions дай отдельные 2–4 поисковые гипотезы в том же порядке. Они должны поддерживать именно этот вопрос, а не копировать working_hypotheses. Если конкретная сторона истории не подтверждает гипотезу, не добавляй её.
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

MAX_OTHER_QUESTIONS = 3  # MVP flow: at most four distinct questions in one story

OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["sufficient", "insufficiency_reason", "reading_notes", "working_hypotheses", "proposed_question",
                 "coordinates", "canonical_tensions", "free_tensions", "ambiguity_notes", "other_questions",
                 "other_question_hypotheses",
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
        "other_question_hypotheses": {"type": "array", "items": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 4}, "maxItems": MAX_OTHER_QUESTIONS},
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

    def complete(self, inp: InterpretationInput, feedback: str | None = None,
                 fixed_questions: list[str] | None = None) -> tuple[dict, dict]:
        user = "Ввод пользователя (JSON):\n" + inp.model_dump_json(indent=1)
        if fixed_questions:
            user += FIXED_QUESTIONS_NOTE + json.dumps(fixed_questions, ensure_ascii=False)
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


def interpret(inp: InterpretationInput, interpreter: Interpreter, max_attempts: int = 2,
              fixed_questions: list[str] | None = None) -> InterpretationResult | InsufficientInterpretation:
    """``fixed_questions`` (2026-10-23): the person's own questions, already split by ``split_questions``. The call
    then only builds the search structure for them; the visible questions are kept exactly as given."""
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
        out, usage = (interpreter.complete(inp, feedback, fixed_questions=fixed_questions) if fixed_questions
                      else interpreter.complete(inp, feedback))
        calls.append(usage)
        try:
            notes = [ReadingNote(**n) for n in out.get("reading_notes", [])]
            trace = InterpretationTrace(
                interpreter=interpreter.name, model=interpreter.model, prompt_version=PROMPT_VERSION,
                input_sha256=sha, reading_notes=notes, attempts=attempt,
                usage={"calls": calls, "repairs": list(repairs)},
            )
            if fixed_questions:  # the split already decided sufficiency and the wording
                out = {**out, "sufficient": True, "proposed_question": fixed_questions[0],
                       "other_questions": list(fixed_questions[1:])}
            if not out.get("sufficient", True):
                return InsufficientInterpretation(
                    input=inp, reason=(out.get("insufficiency_reason") or "model reported insufficient input").strip(),
                    clarification_prompt=clarifying_question(out.get("clarifying_question")) or UNCLEAR_PROMPT,
                    trace=trace,
                )
            pq = out["proposed_question"].strip()
            others = list(dict.fromkeys(q.strip() for q in out.get("other_questions") or [] if q.strip()
                                        and q.strip() != pq))[:MAX_OTHER_QUESTIONS]
            raw_hypotheses = out.get("other_question_hypotheses") or []
            hypotheses_by_question = [
                [h.strip() for h in group if isinstance(h, str) and h.strip()] if isinstance(group, list) else []
                for group in raw_hypotheses[:len(others)]
            ]
            hypotheses_by_question = (hypotheses_by_question + [[] for _ in range(len(others))])[:len(others)]
            if not fixed_questions:  # the person's own words are not rewritten to fit the formulation rules
                check_question(pq, inp)
            # another independent question that breaks the contract is dropped (never a repair call for it)
            valid_pairs = [(q, hs) for q, hs in zip(others, hypotheses_by_question)
                           if fixed_questions or _passes(q, inp)]
            others = [q for q, _ in valid_pairs]
            hypotheses_by_question = [hs for _, hs in valid_pairs]
            return InterpretationResult(
                input=inp,
                proposed_question=pq,
                other_questions=others,
                other_question_hypotheses=hypotheses_by_question,
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


# ---------------------------------------------------------------- 2026-10-23: fast split of the person's own question
# The visible question step only separates the questions the person asked himself (seconds). The search structure
# (hypotheses, coordinates, tensions) is built afterwards by ``interpret(..., fixed_questions=...)``, in the background.

SPLIT_PROMPT_VERSION = "split-prompt/0.1.0"
FIXED_QUESTIONS_NOTE = ("\n\nВопросы человека уже выделены его словами (JSON-список ниже). proposed_question — ПЕРВЫЙ "
                        "из них дословно, other_questions — остальные дословно и в том же порядке; не меняй их. "
                        "Твоя задача — гипотезы и разметка для поиска именно по этим вопросам:\n")
SPLIT_PROMPT = """Ты выделяешь вопрос человека из его рассказа. Ты ничего не переформулируешь и не толкуешь.

1. Понятен ли рассказ: можно ли обычными словами сказать, чего человек хочет или что произошло и в чём трудность? Если нет — sufficient=false, в insufficiency_reason коротко почему, в clarifying_question ОДИН короткий уточняющий вопрос на «вы», без бессмысленных слов из рассказа. Иначе sufficient=true и clarifying_question = null.
2. asked: задал ли человек свой вопрос сам (вопросительной фразой или прямо: «не знаю, как…», «хочу понять…»). Если не задал — asked=false и questions пустой: вопрос сформулирует другой шаг.
3. questions (если asked=true): вопрос(ы) человека ЕГО словами. Можно взять одно его предложение о ситуации, если без него вопрос непонятен, и убрать лишнее. Нельзя: добавлять слова, обобщать, «поднимать» до напряжения, менять опорные слова, вставлять чувства (они не часть вопроса), придумывать вопросы, которых он не задавал. Несколько РАЗНЫХ вопросов — отдельные элементы списка (до четырёх). Связанные части одного вопроса — один элемент. Каждый элемент — законченное, грамматически правильное, понятное без рассказа; последнее предложение оканчивается «?».

Отвечай строго по JSON-схеме."""
SPLIT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["sufficient", "insufficiency_reason", "clarifying_question", "asked", "questions"],
    "properties": {
        "sufficient": {"type": "boolean"},
        "insufficiency_reason": {"type": ["string", "null"]},
        "clarifying_question": {"type": ["string", "null"]},
        "asked": {"type": "boolean"},
        "questions": {"type": "array", "items": {"type": "string"}, "maxItems": 1 + MAX_OTHER_QUESTIONS},
    },
}
MIN_OWN_WORDS_SHARE = 0.8  # a split question must be made of the person's own words


@dataclass
class ClaudeCodeCLISplitter:
    """One small, low-effort call: the person's own questions, nothing else."""
    model: str = DEFAULT_MODEL
    effort: str | None = "low"
    timeout_s: int = 120
    name: str = "claude-code-cli-split"

    def complete(self, inp: InterpretationInput, feedback: str | None = None) -> tuple[dict, dict]:
        user = "Рассказ человека:\n" + inp.free_narrative
        if feedback:
            user += "\n\nПредыдущий ответ не прошёл проверку. Исправь:\n" + feedback
        cmd = [
            "claude", "-p", "--safe-mode", "--tools", "", "--strict-mcp-config", "--no-session-persistence",
            "--model", self.model, "--system-prompt", SPLIT_PROMPT,
            "--output-format", "json", "--json-schema", json.dumps(SPLIT_SCHEMA, ensure_ascii=False),
            *(["--effort", self.effort] if self.effort else []),
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


def _stems(text: str) -> list[str]:
    # crude stems: Russian endings change between a story and a question taken from it
    return [w[:5] for w in re.findall(r"\w{3,}", (text or "").lower().replace("ё", "е"))]


def own_words_share(question: str, narrative: str) -> float:
    words, known = _stems(question), set(_stems(narrative))
    return sum(w in known for w in words) / len(words) if words else 0.0


NEGATIONS = frozenset({"не", "ни", "нет", "без", "никогда", "ничего", "нельзя", "никто", "нигде", "некогда"})
MAX_FOREIGN_SHARE = 0.2  # words of a question sentence that its source sentence lacks (connectives, «мне»…)


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", (text or "").lower().replace("ё", "е"))


def _sentences(text: str) -> list[str]:
    return [x for x in re.split(r"(?<=[.!?…])\s+", (text or "").strip()) if x.strip()]


def _neg_pairs(tokens: list[str]) -> list[tuple[str, str]]:
    return sorted((t, tokens[i + 1][:5] if i + 1 < len(tokens) else "") for i, t in enumerate(tokens) if t in NEGATIONS)


def _fits_sentence(q_tokens: list[str], s_tokens: list[str]) -> bool:
    """Content words of the question sentence appear in this story sentence in the same order (a few new ones are
    allowed, a word that is there but out of order is not), and the negations around them are exactly the same."""
    content = [t for t in q_tokens if len(t) >= 3 and t not in NEGATIONS]
    stems, s_stems = [t[:5] for t in content], [t[:5] for t in s_tokens]
    pos, matched, foreign = 0, [], 0
    for st in stems:
        try:
            pos = s_stems.index(st, pos)
        except ValueError:
            if st in s_stems:  # present, but not in this order: actors or direction changed
                return False
            foreign += 1
            continue
        matched.append(pos)
        pos += 1
    if not matched or foreign > MAX_FOREIGN_SHARE * len(stems):
        return False
    lo = matched[0] - 1 if matched[0] > 0 and s_tokens[matched[0] - 1] in NEGATIONS else matched[0]
    return _neg_pairs(q_tokens) == _neg_pairs(s_tokens[lo:matched[-1] + 1])


def own_question_problem(question: str, narrative: str) -> str | None:
    """Why a split question is not the person's own words, or None. A cheap guard, not a proof of meaning: it catches
    a lost or added negation and actors or words in another order (each sentence must follow one story sentence);
    it cannot see a change of meaning made with the same words in the same order or with short words such as
    pronouns."""
    if not question.endswith("?"):
        return "не оканчивается «?»"
    if own_words_share(question, narrative) < MIN_OWN_WORDS_SHARE:
        return "не из слов человека"
    story = [_tokens(x) for x in _sentences(narrative)]
    for sent in _sentences(question):
        if not any(_fits_sentence(_tokens(sent), st) for st in story):
            return f"«{sent}» не повторяет ни одно предложение рассказа (порядок слов, действующие лица или отрицание)"
    return None


def split_questions(inp: InterpretationInput, splitter, max_attempts: int = 2
                    ) -> tuple[list[str] | InsufficientInterpretation | None, dict]:
    """The person's own questions (list), an ``InsufficientInterpretation``, or ``None`` when he asked no question
    (then the full interpreter formulates one, as before). Questions not made of his words are rejected."""
    sha = input_sha256(inp)
    if _word_count(inp.free_narrative) < MIN_NARRATIVE_WORDS:
        return InsufficientInterpretation(
            input=inp, reason=f"free narrative has fewer than {MIN_NARRATIVE_WORDS} words (deterministic pre-check)",
            clarification_prompt=CLARIFICATION_PROMPT,
            trace=InterpretationTrace(interpreter="deterministic-precheck", prompt_version=SPLIT_PROMPT_VERSION,
                                      input_sha256=sha, attempts=0)), {"calls": []}
    feedback, calls = None, []
    for attempt in range(1, max_attempts + 1):
        out, usage = splitter.complete(inp, feedback)
        calls.append(usage)
        meta = {"calls": calls, "prompt_version": SPLIT_PROMPT_VERSION}
        if not out.get("sufficient", True):
            return InsufficientInterpretation(
                input=inp, reason=(out.get("insufficiency_reason") or "model reported insufficient input").strip(),
                clarification_prompt=clarifying_question(out.get("clarifying_question")) or UNCLEAR_PROMPT,
                trace=InterpretationTrace(interpreter=splitter.name, model=splitter.model,
                                          prompt_version=SPLIT_PROMPT_VERSION, input_sha256=sha, attempts=attempt,
                                          usage=meta)), meta
        if not out.get("asked"):
            return None, meta
        qs = list(dict.fromkeys(q.strip() for q in out.get("questions") or [] if q and q.strip()))
        bad = [f"{q} — {why}" for q in qs if (why := own_question_problem(q, inp.free_narrative))]
        if qs and not bad:
            return qs[:1 + MAX_OTHER_QUESTIONS], meta
        feedback = ("Вопросы должны быть словами человека из рассказа, в его порядке и с его отрицаниями, и "
                    "оканчиваться «?». Не прошли: " + "; ".join(bad or ["пустой список"]))
    return None, {"calls": calls, "prompt_version": SPLIT_PROMPT_VERSION, "fallback": feedback}

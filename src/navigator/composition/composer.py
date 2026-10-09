"""Experimental composition layer (M2.5).

Input package: deterministic JSON built from ONE retrieval trace (M2.4) and the
corpus cards of its candidate union — never the whole corpus.

Composer runtime: the locally installed Claude Code CLI in headless mode
(``claude -p``), authenticated by the user's existing Claude login — no API key,
no new service. Calls run with a short dedicated system prompt, no tools, no MCP,
safe mode, no session persistence, and a JSON schema for structured output.

The model writes title / main idea / applied insight / perspective («Подробнее») /
reflection question and selection reasons (M3.1 plain-language card). M3.2: selection by a
useful distinction (internal ``distinction`` field), declarative titles, one-read language and
a short ``question_explanation`` («Что имеется в виду?»); 2 strong cards beat 3 with a weak one.
Sources are filled by code from corpus metadata. Output is validated by
``CompositionResult``; one repair attempt with the validation error is allowed.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Protocol

from pydantic import ValidationError

from navigator.models.composition import (
    ONE_CALL_SCHEMA_VERSION,
    CandidateDecision,
    ComposerMeta,
    CompositionResult,
    Perspective,
    Q1TopDecision,
)
from navigator.corpus.final_corpus import FINAL_CORPUS_VERSION
from navigator.language import LANGUAGE_RULES, reference_voice_block
from navigator.timing import cli_error_message, cli_usage
from navigator.models.fragment import Fragment
from navigator.models.interpretation import (
    AMPLIFICATION_RULE,
    INTERNAL_CLAIM_RULE,
    PSYCH_FUNCTION_RULE,
    amplification_hits,
)

PACKAGE_VERSION = "composition-package/0.1.0"
PROMPT_VERSION = "composition-prompt/0.10.0"  # MVP pass 1: the person's chosen feelings inform the choice
DEFAULT_MODEL = "claude-opus-5-5"


def source_label(f: Fragment) -> str:
    """Source string strictly from corpus metadata (author, work, location — as present)."""
    parts = [p for p in (f.author, f.work, f.location) if p]
    return ", ".join(parts)


def build_package(trace: dict, fragments: list[Fragment]) -> dict:
    by_id = {f.id: f for f in fragments}
    cr = trace["candidate_retrieval"]
    q = cr["query"]
    candidates = []
    for c in cr["candidate_union"]:
        f = by_id[c["card_id"]]
        candidates.append(
            {
                "card_id": f.id,
                "source": source_label(f),
                "perspective": f.perspective,
                "philosophical_questions": f.philosophical_questions or [],
                "coordinates": f.coordinates or [],
                "tensions": f.tensions or [],
                "operation": f.philosophical_operation,
                # final corpus: the verified verbatim quote of the card (absent in legacy corpora → legacy packages unchanged)
                **({"verified_quote": f.fragment} if f.technical.corpus_status == "final_2026_10_07" and f.fragment else {}),
                "signals": {
                    "found_by": c["found_by"],
                    "meaning_rank": c["meaning_rank"],
                    "meaning_cosine": c["meaning_score"],
                    "structure_rank": c["structure_rank"],
                    "matched_coordinates": c["matched_coordinates"],
                    "matched_tensions": c["matched_tensions"],
                },
            }
        )
    q1_top = cr["q1_meaning"]["hits"][0]["card_id"]
    return {
        "package_version": PACKAGE_VERSION,
        "item_id": trace["item_id"],
        "retrieval_run_id": trace["run_id"],
        "confirmed_question": q["confirmed_question"],
        "context": {"circumstance": q["context"]["circumstance"], "narrative": q["context"]["narrative"]},
        "experiences": q["experiences"],
        "working_hypotheses": q["working_hypotheses"],
        "query_structure": {
            "coordinates": q["coordinates"],
            "canonical_tensions": q["canonical_tensions"],
            "free_tensions": q["free_tensions"],
        },
        "q1_top_card_id": q1_top,
        "candidates": candidates,
        # final corpus only (legacy packages and their hashes stay as they were)
        **({"corpus_version": cr["corpus_version"]} if cr.get("corpus_version") == FINAL_CORPUS_VERSION else {}),
    }


def package_sha256(package: dict) -> str:
    return hashlib.sha256(json.dumps(package, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


SYSTEM_PROMPT = f"""Ты — composer философского навигатора. Ты получаешь вопрос человека и ограниченный набор карточек-кандидатов из корпуса первоисточников. Ты не знаешь и не используешь ничего о философах и текстах сверх того, что написано в карточках.

Задача: вернуть МИНИМАЛЬНОЕ число сильных перспектив, достаточное, чтобы человек получил действительно РАЗНЫЕ способы увидеть свой вопрос: 2 или 3. Две сильные разные перспективы — полноценный хороший результат, а не неполный. Третья появляется, только если она даёт самостоятельный сильный взгляд. Текст для человека пишешь НЕ ты: его по твоему выбору напишет отдельный шаг.

Главное правило продукта: система не решает жизненную ситуацию. Она помогает увидеть различия, которых исходный вопрос пока не делает. Запрещены советы и вердикты («вам следует…», «вам нужно…», «вы должны…», «правильное решение…»). Запрещена психологическая диагностика. Рабочие гипотезы во входном пакете — внутренний материал системы, а не факты о человеке. {AMPLIFICATION_RULE} {PSYCH_FUNCTION_RULE} {INTERNAL_CLAIM_RULE}

Главный критерий выбора — полезное различение.
Для каждого кандидата сначала попробуй закончить фразу: «Эта перспектива помогает человеку различить ___ и ___» или «После неё человек сможет увидеть ___, чего его вопрос пока не различает». Уровень ясности, который нужен: «ценность работы ≠ её цена», «принять происходящее ≠ ничего не делать», «ответственность ≠ способность исправить всё самому». Это только примеры уровня — не подставляй их, если они не вытекают из карточки и вопроса.
Если ясное различение для кандидата не формулируется — не выбирай его, даже если он тематически близок или представляет другую традицию.

Эффект перспективы (perspective_effect) — главное, по чему ты сравниваешь кандидатов. Для каждого кандидата, которого всерьёз рассматриваешь, одной фразой ответь: что именно человек сможет увидеть в СВОЁМ вопросе иначе после этой перспективы? Например: «отсутствие гарантии не делает действие бессмысленным», «разные опасения получают вес из разных ценностей», «выбор не обязан быть окончательным прямо сейчас». Это примеры формы, не готовые ответы: эффект должен следовать из данных карточки и из вопроса. Ищи прежде всего перспективы, которые меняют саму постановку вопроса, а не только помогают лучше организовать исходную проблему. Не придумывай философскую позицию, которой нет в карточке. Не ищи противоположностей и «неожиданности» ради неожиданности: философам не нужно спорить.

Дубли определяются по мыслительной операции, а не по источнику, автору или словам. Разные философы, разные источники и разные вопросы к себе НЕ делают перспективы разными. Сравни эффекты попарно применительно к ЭТОМУ вопросу: если две перспективы выполняют одну функцию (например, «будущее неизвестно, но действия всё равно важны» и «отделите то, что зависит от вас, от того, что не зависит» — обе ведут от неизвестного будущего к тому, что в руках человека), это конкуренты: оставь более сильную, другую отметь как same_operation_as_selected.

Рамка перспективы (perspective_frame) — уровень выше эффекта. Одной фразой: какую рамку своего вопроса человек начинает исследовать благодаря этой перспективе, то есть в каком отношении он теперь смотрит на проблему (например, «как действовать без гарантий», «как соотносятся страх и выбор», «по какой мерке вообще сравнивать пути», «что было моим, а что мне давали»). Это формы, а не список ответов. Два разных эффекта могут лежать в одной рамке: тогда вторая карточка лишь уточняет первую или меняет критерий внутри той же работы — это НЕ самостоятельная перспектива. Сравнивай кандидатов и по эффекту, и по рамке. Для каждого следующего кандидата спроси: меняет ли он способ, которым человек рассматривает проблему, настолько, чтобы оправдать ещё одну карточку?
Проверь и применимость: если перспектива подходит к вопросу только через натянутый перенос (метафора источника, частный пример, который приходится растягивать на ситуацию человека, неверное описание того, о чём он спрашивает) — она слабее, даже если её эффект нов.
Нужен минимальный достаточный результат: не «обычно 2» и не «обычно 3».
perspective_effect и perspective_frame описывают ВОЗМОЖНОСТЬ увидеть вопрос иначе, а не новый факт о человеке. Плохо: «высокое положение и нынешний стыд — две стороны одного» (это утверждение о его стыде). Хорошо: «можно проверить, связан ли стыд с тем, как положение выглядит в чужих глазах». Не выбирай карточку за то, что она «объясняет» человека догадкой.

Третью перспективу НЕ включай, если она: повторяет операцию одной из первых; лишь уточняет одну из них; лежит в той же рамке, что одна из первых; меняет критерий внутри той же операции; требует натянутого применения источника; слабее привязана к вопросу; требует больше догадок о человеке; даёт только ещё один вопрос к себе без новой мысли; полезна, но не меняет картину. Никакого бонуса за количество нет.

Чувства. Переживания (experiences) человек выбрал сам: они показывают, что в вопросе для него живо, — именно чувства приводят к такому вопросу. Из перспектив одинаковой силы предпочитай ту, что работает с напряжением, из которого растут эти чувства. Перспектива не утешает, не «лечит» чувство и не называет его за человека.

Порядок критериев:
1. Relevance: карточка работает именно с подтверждённым вопросом. Проверяй направленность и субъекта действия: «мой поступок определяет меня» и «чужой поступок определяет мой ответ» — разные вопросы, даже если лексика похожа.
2. Ясность различения: его можно сказать одной простой фразой.
3. Польза: после различения человек видит свою ситуацию иначе. Тематического совпадения мало.
4. Разные ЭФФЕКТЫ: выбранные перспективы меняют понимание вопроса по-разному (см. выше); разнообразие определяется эффектом на вопрос, НЕ традицией или автором и не формулировкой различения. Не бери более слабую карточку ради другой традиции.
5. Grounding: всё, что ты приписываешь источнику, должно следовать из perspective / philosophical_questions карточки. Не добавляй идей, цитат, глав, стихов.
- КАЧЕСТВО ВАЖНЕЕ КОЛИЧЕСТВА. 2 и 3 — равноправные результаты. В count_reason одной фразой объясни выбранное число: при 3 — какой самостоятельный эффект даёт третья; при 2 — почему третьей нет. Никогда не добивай результат слабой карточкой. Никогда не больше 3.
- Перспектива может работать с одной важной частью вопроса; не требуй от неё охватить весь вопрос.
- Не достраивай проблему: карточка может ввести новое философское различение, но не новый факт о человеке, его мотив, сравнение, страх, желание или психологический механизм. Если карточка работает только при таком добавлении — не выбирай её. Этот запрет касается ТЕКСТА о человеке, а не выбора карточки: если карточка даёт полезное различение, но её легко применить через догадку о человеке, — всё равно рассматривай её и сформулируй различение как мысль о вещах («похвала и качество работы — разные вещи»), а не как утверждение о человеке («вы зависите от похвалы»). Не пиши в тексте «возможно, для вас…» про мотив или самооценку — называй различение и оставь вывод человеку.
- Ранги и cosine — лишь свидетельства. Карточку с первым рангом можно отвергнуть как ложное совпадение; карточку ниже можно выбрать, если она точнее.
- Карточки с шаблонным началом «Рассмотреть ситуацию через операцию, которую задаёт сам фрагмент:» описывают сюжет или ход текста — опирайся только на то, что после двоеточия.
- Если у кандидата есть verified_quote — это проверенный дословный текст источника. Опирайся на него вместе с ходом текста: он показывает, что источник действительно говорит. Выбирай по смыслу различения, а не по совпадению слов цитаты со словами человека.

Для каждой выбранной карточки (всё — внутренние поля, человек их не видит; пиши коротко):
- perspective_effect: что человек увидит в своём вопросе иначе (одна фраза, как выше).
- perspective_frame: какую рамку своего вопроса человек начинает исследовать (одна фраза, как выше).
- distinction: одна фраза: «Помогает различить X и Y» или «Помогает увидеть …, чего вопрос пока не различает».
- role: 2–5 слов — какой ход делает перспектива.
- source_point: одна простая фраза своими словами — что говорит или делает источник (не переписывай учёные обороты карточки).
- user_point: одна фраза — что это различение позволяет увидеть в вопросе человека, только из его слов, без догадок о нём и о других людях из его рассказа (их мотивах, мыслях, выборе).
- why_selected: одно короткое предложение, почему выбрана.

Также:
- considered: все кандидаты, которых ты всерьёз рассматривал (обычно 4–7), включая выбранные: card_id, perspective_effect, perspective_frame, decision (selected / same_operation_as_selected / same_frame_as_selected / weaker / strained_application / no_clear_distinction / needs_guess_about_person), duplicate_of (card_id выбранной карточки с той же операцией или рамкой, иначе null) и reason — одно короткое предложение.
- q1_top: решение по карточке q1_top_card_id (selected/rejected) и причина одним предложением.

Пиши по-русски. Отвечай строго по JSON-схеме."""

DECISIONS = ["selected", "same_operation_as_selected", "same_frame_as_selected", "weaker", "strained_application",
             "no_clear_distinction", "needs_guess_about_person"]
OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["perspectives", "considered", "q1_top", "count_reason"],
    "properties": {
        "perspectives": {
            "type": "array",
            "minItems": 2,
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["card_id", "perspective_effect", "perspective_frame", "distinction", "role", "source_point",
                             "user_point", "why_selected"],
                "properties": {
                    "card_id": {"type": "string"},
                    "perspective_effect": {"type": "string"},
                    "perspective_frame": {"type": "string"},
                    "distinction": {"type": "string"},
                    "role": {"type": "string"},
                    "source_point": {"type": "string"},
                    "user_point": {"type": "string"},
                    "why_selected": {"type": "string"},
                },
            },
        },
        "count_reason": {"type": "string"},
        # M3.4: every seriously considered candidate with its effect on the question (duplicates by operation)
        "considered": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["card_id", "perspective_effect", "perspective_frame", "decision", "duplicate_of", "reason"],
                "properties": {
                    "card_id": {"type": "string"},
                    "perspective_effect": {"type": "string"},
                    "perspective_frame": {"type": "string"},
                    "decision": {"type": "string", "enum": DECISIONS},
                    "duplicate_of": {"type": ["string", "null"]},
                    "reason": {"type": "string"},
                },
            },
        },
        "q1_top": {
            "type": "object",
            "additionalProperties": False,
            "required": ["card_id", "decision", "reason"],
            "properties": {
                "card_id": {"type": "string"},
                "decision": {"type": "string", "enum": ["selected", "rejected"]},
                "reason": {"type": "string"},
            },
        },
    },
}


# Final corpus (MVP demo): one strong card is a valid answer when no other author gives a good second one, so the
# selection schema accepts 1–3 there. Legacy corpora keep 2–3. The system prompt is unchanged.
FINAL_OUTPUT_SCHEMA = copy.deepcopy(OUTPUT_SCHEMA)
FINAL_OUTPUT_SCHEMA["properties"]["perspectives"]["minItems"] = 1


def is_final_package(package: dict) -> bool:
    return package.get("corpus_version") == FINAL_CORPUS_VERSION


def output_schema_for(package: dict) -> dict:
    return FINAL_OUTPUT_SCHEMA if is_final_package(package) else OUTPUT_SCHEMA


class ComposerUnavailable(RuntimeError):
    pass


class Composer(Protocol):
    name: str
    model: str | None

    def complete(self, package: dict, feedback: str | None = None) -> tuple[dict, dict]:
        """Return (structured output, usage/meta)."""
        ...


@dataclass
class ClaudeCodeCLIComposer:
    model: str = DEFAULT_MODEL
    timeout_s: int = 600
    name: str = "claude-code-cli"

    def complete(self, package: dict, feedback: str | None = None) -> tuple[dict, dict]:
        user = "Входной пакет (JSON):\n" + json.dumps(package, ensure_ascii=False, indent=1)
        if feedback:
            user += "\n\nПредыдущий ответ не прошёл проверку контракта. Исправь и ответь заново. Ошибка:\n" + feedback
        cmd = [
            "claude", "-p", "--safe-mode", "--tools", "", "--strict-mcp-config", "--no-session-persistence",
            "--model", self.model, "--system-prompt", SYSTEM_PROMPT,
            "--output-format", "json", "--json-schema", json.dumps(output_schema_for(package), ensure_ascii=False),
        ]
        t0 = time.monotonic()
        try:
            proc = subprocess.run(cmd, input=user, capture_output=True, text=True, timeout=self.timeout_s)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise ComposerUnavailable(str(exc)) from exc
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise ComposerUnavailable(f"non-JSON CLI output: {proc.stdout[:300]} {proc.stderr[:300]}") from exc
        if payload.get("is_error") or not isinstance(payload.get("structured_output"), dict):
            raise ComposerUnavailable(cli_error_message(payload))
        usage = cli_usage(payload, time.monotonic() - t0)
        return payload["structured_output"], usage


SELECTION_FIELDS = frozenset(OUTPUT_SCHEMA["properties"]["perspectives"]["items"]["properties"])
# One-call format (M3.2–M3.3: the composer also wrote the text). Still accepted, e.g. from scripted test composers.
MODEL_PERSPECTIVE_FIELDS = frozenset({"card_id", "role", "title", "main_idea", "applied_insight", "perspective",
                                      "reflection_question", "why_selected", "distinction", "question_explanation"})


def assemble_result(package: dict, output: dict, fragments: list[Fragment], meta: ComposerMeta,
                    quote_source=None) -> CompositionResult:
    """``quote_source(card_id) -> VerifiedQuote | None`` is the ONLY way a quote enters a result
    (M3.3: a READY row of the local-source inventory). The model never supplies quotes."""
    by_id = {f.id: f for f in fragments}
    pool = [c["card_id"] for c in package["candidates"]]
    perspectives = []
    for p in output["perspectives"]:
        # Only contract fields are read; anything else the model adds (a "source", a "quote") is ignored.
        p = {k: v for k, v in p.items() if k in MODEL_PERSPECTIVE_FIELDS}
        hits = amplification_hits(" ".join([p["title"], p["main_idea"], p["applied_insight"], p["perspective"],
                                            p["reflection_question"], p["question_explanation"]]))
        if hits:
            raise ValueError(f"perspective {p['card_id']} states an unconfirmed hypothesis about the person as fact: {hits}")
        cid = p["card_id"]
        if cid not in by_id or cid not in pool:
            raise ValueError(f"card {cid} is not in the candidate pool")
        perspectives.append(
            Perspective(
                card_id=cid, role=p["role"].strip(), title=p["title"].strip(), source=source_label(by_id[cid]),
                perspective=p["perspective"].strip(), reflection_question=p["reflection_question"].strip(),
                why_selected=p["why_selected"].strip(), main_idea=p["main_idea"].strip(),
                applied_insight=p["applied_insight"].strip(), distinction=p["distinction"].strip(),
                question_explanation=p["question_explanation"].strip(),
                verified_quote=quote_source(cid) if quote_source else None,
            )
        )
    return CompositionResult(
        schema_version=ONE_CALL_SCHEMA_VERSION,
        item_id=package["item_id"],
        retrieval_run_id=package["retrieval_run_id"],
        confirmed_question=package["confirmed_question"],
        candidate_pool=pool,
        perspectives=perspectives,
        fewer_than_three_reason=(output.get("fewer_than_three_reason") or None) if len(perspectives) == 2 else None,
        rejected=[CandidateDecision(card_id=r["card_id"], reason=r["reason"].strip()) for r in output.get("rejected", [])],
        q1_top=Q1TopDecision(**output["q1_top"]),
        meta=meta,
        corpus_version=package.get("corpus_version"),
    )


def check_selection(package: dict, output: dict) -> list[dict]:
    """Selection-stage contract (before any text is written). Raises ValueError for a repair attempt.
    M3.4: 2 and 3 are equal results (no reason is demanded for 2); every selected card states its
    ``perspective_effect``; the model's own comparison of effects (``considered``) must be consistent — a card it
    marks as the same thinking operation as a selected one cannot be selected too."""
    pool = [c["card_id"] for c in package["candidates"]]
    sel = [{k: v for k, v in p.items() if k in SELECTION_FIELDS} for p in output["perspectives"]]
    ids = [p["card_id"] for p in sel]
    low = 1 if is_final_package(package) else 2  # final corpus (MVP): one strong card is a valid answer
    if not low <= len(ids) <= 3:
        raise ValueError(f"select {low}–3 cards, got {len(ids)}")
    if len(set(ids)) != len(ids):
        raise ValueError("selected cards must be distinct")
    outside = sorted(set(ids) - set(pool))
    if outside:
        raise ValueError(f"selected cards outside the candidate pool: {outside}")
    for p in sel:
        missing = [f for f in ("distinction", "role", "why_selected", "perspective_effect") if not (p.get(f) or "").strip()]
        if missing:
            raise ValueError(f"card {p['card_id']}: empty {missing}")
        if not any(w in p["distinction"].lower() for w in ("различ", "увидеть")):
            raise ValueError("distinction must say what the person can distinguish («различить … и …») or see («увидеть …»)")
    effects = [" ".join(re.findall(r"\w+", p["perspective_effect"].lower())) for p in sel]
    if len(set(effects)) != len(effects):
        raise ValueError("two selected cards state the same perspective_effect: keep only the stronger one")
    frames = [" ".join(re.findall(r"\w+", (p.get("perspective_frame") or "").lower())) for p in sel]
    if all(frames) and len(set(frames)) != len(frames):
        raise ValueError("two selected cards open the same perspective_frame: they are one perspective, keep the stronger")
    considered = output.get("considered")
    if considered is not None:
        by = {c["card_id"]: c for c in considered}
        for cid in ids:
            c = by.get(cid)
            if c is not None and c.get("decision") != "selected":
                raise ValueError(f"{cid} is selected but marked «{c.get('decision')}» in considered; "
                                 "a duplicate of a selected card must be dropped, not shown")
        for c in considered:
            if c.get("decision") == "selected" and c["card_id"] not in ids:
                raise ValueError(f"{c['card_id']} is marked selected in considered but is not in perspectives")
            if c.get("decision") in ("same_operation_as_selected", "same_frame_as_selected") \
                    and c.get("duplicate_of") not in ids:
                raise ValueError(f"{c['card_id']}: duplicate_of must name the selected card with the same operation/frame")
    return sel


_DECISION_LABEL = {"same_operation_as_selected": "та же мыслительная операция, что у {dup}",
                   "same_frame_as_selected": "та же рамка вопроса, что у {dup}",
                   "strained_application": "натянутое применение к вопросу",
                   "weaker": "слабее", "no_clear_distinction": "нет ясного различения",
                   "needs_guess_about_person": "работает только через догадку о человеке"}


def rejected_from(output: dict, kept: list[str]) -> list[CandidateDecision]:
    """Not-selected candidates with their reason: M3.4 ``considered`` (effect-based), else the older ``rejected``."""
    out = []
    for c in output.get("considered") or []:
        if c["card_id"] in kept or c.get("decision") == "selected":
            continue
        label = _DECISION_LABEL.get(c.get("decision"), c.get("decision") or "").format(dup=c.get("duplicate_of"))
        out.append(CandidateDecision(card_id=c["card_id"], reason=f"{label}: {c['reason'].strip()}"))
    for r in output.get("rejected") or []:
        if r["card_id"] not in kept and r["card_id"] not in [x.card_id for x in out]:
            out.append(CandidateDecision(card_id=r["card_id"], reason=r["reason"].strip()))
    return out


SAME_AUTHOR_FEEDBACK = (
    "В одном ответе не может быть двух карточек одного автора: {pairs}. Оставь из них одну, более сильную. "
    "Вместо второй выбери следующую достаточно сильную перспективу ДРУГОГО автора из пула — только если она даёт "
    "самостоятельное ясное различение для этого вопроса. Если такой нет, верни одну карточку: одна сильная "
    "перспектива лучше, чем добавленная ради количества.")


def one_card_per_author(package: dict, sel: list[dict], by_id: dict, resolve: bool) -> tuple[list[dict], list[dict]]:
    """Final corpus (MVP demo): at most one final card per author (CSV ``author`` field, verbatim).
    ``resolve=False`` → ValueError with feedback, so the selector re-chooses a card of another author (the normal repair
    loop); ``resolve=True`` (last attempt) → keep the first selected card of each author and drop the rest, without
    padding. Returns (kept selection, dropped [{card_id, author, kept}]). Legacy packages pass through unchanged."""
    if not is_final_package(package):
        return sel, []
    first: dict[str, str] = {}
    kept, dropped = [], []
    for p in sel:
        author = by_id[p["card_id"]].author or ""
        if author in first:
            dropped.append({"card_id": p["card_id"], "author": author, "kept": first[author]})
        else:
            first[author] = p["card_id"]
            kept.append(p)
    if dropped and not resolve:
        pairs = "; ".join(f"{d['author']} — {d['kept']} и {d['card_id']}" for d in dropped)
        raise ValueError(SAME_AUTHOR_FEEDBACK.format(pairs=pairs))
    return kept, dropped


def compose_written(package: dict, output: dict, fragments: list[Fragment], meta: ComposerMeta, writer,
                    quote_source=None, max_writer_attempts: int = 3, validator=None,
                    resolve_same_author: bool = True) -> CompositionResult:
    """M3.3.1 two-step composition: the selection in ``output`` + one writer call per card (parallel).
    Final corpus: at most one card per author (``one_card_per_author``)."""
    from navigator.composition.writer import WRITER_PROMPT_VERSION, write_cards

    by_id = {f.id: f for f in fragments}
    sel = check_selection(package, output)
    sel, same_author = one_card_per_author(package, sel, by_id, resolve_same_author)
    t0 = time.monotonic()
    cards, records = write_cards(package, sel, fragments, lambda cid: source_label(by_id[cid]), writer,
                                 max_writer_attempts, validator)
    written = [(s, c) for s, c in zip(sel, cards) if c is not None]
    dropped = [s["card_id"] for s, c in zip(sel, cards) if c is None]
    # Each failed card was already repaired on its own by the writer (``max_writer_attempts``); the written ones are
    # never rewritten. Final corpus: one checked card is a valid answer, so a lost card does not re-run the whole
    # selection (MVP latency, sessions 84ec8453fdcf / 2090a85f0b59); only when none is written is the selection redone.
    if len(written) < (1 if is_final_package(package) else min(2, len(sel))):
        raise ValueError(f"cards could not be written clearly: {[r['repairs'][-1][:300] for r in records if r['fallback']]}")
    kept = [s["card_id"] for s, _ in written]
    rejected = [CandidateDecision(card_id=d["card_id"], reason=f"тот же автор, что у {d['kept']}: в ответе одна карточка автора")
                for d in same_author]
    rejected += [r for r in rejected_from(output, kept) if r.card_id not in [d["card_id"] for d in same_author]]
    rejected += [CandidateDecision(card_id=cid, reason="выбрана, но её текст не прошёл проверку понятности")
                 for cid in dropped if cid not in [r.card_id for r in rejected]]
    q1 = Q1TopDecision(**output["q1_top"])
    if q1.decision == "selected" and q1.card_id in dropped:
        q1 = Q1TopDecision(card_id=q1.card_id, decision="rejected",
                           reason="выбрана, но её текст не прошёл проверку понятности")
    if q1.decision == "selected" and q1.card_id in [d["card_id"] for d in same_author]:
        q1 = Q1TopDecision(card_id=q1.card_id, decision="rejected",
                           reason="тот же автор, что у другой выбранной карточки: в ответе одна карточка автора")
    count_reason = (output.get("count_reason") or output.get("fewer_than_three_reason") or "").strip() or None
    fewer = None
    if len(written) == 2:  # kept as a trace field; two cards are a full result and need no justification
        fewer = ("Третья перспектива не прошла проверку понятности текста и не показывается." if dropped
                 else count_reason)
    elif len(written) == 1 and dropped:  # final corpus only (legacy raises above)
        fewer = "Другие выбранные перспективы не прошли проверку текста и не показываются."
    meta = meta.model_copy(update={"usage": {**meta.usage, "writer": {
        "prompt_version": WRITER_PROMPT_VERSION, "seconds": round(time.monotonic() - t0, 2),
        "cards": records, "dropped": dropped, "selection": sel,
        "considered": output.get("considered"), "count_reason": output.get("count_reason"),
        **({"same_author_dropped": same_author} if same_author else {})}}})
    perspectives = [c.model_copy(update={"perspective_effect": s.get("perspective_effect"),
                                         "perspective_frame": s.get("perspective_frame"),
                                         **({"verified_quote": quote_source(c.card_id)} if quote_source else {})})
                    for s, c in written]
    return CompositionResult(
        item_id=package["item_id"], retrieval_run_id=package["retrieval_run_id"],
        confirmed_question=package["confirmed_question"], candidate_pool=[c["card_id"] for c in package["candidates"]],
        perspectives=perspectives, fewer_than_three_reason=fewer, count_reason=count_reason, rejected=rejected,
        q1_top=q1, meta=meta, corpus_version=package.get("corpus_version"),
    )


def _is_selection(output: dict) -> bool:
    return all("title" not in p for p in output.get("perspectives", []))


def compose(package: dict, fragments: list[Fragment], composer: Composer, max_attempts: int = 2,
            quote_source=None, writer=None, max_writer_attempts: int = 3, validator=None) -> CompositionResult:
    """Selection by ``composer``; with a ``writer`` the text is written per card (M3.3.1). A composer that
    returns the older one-call format (text included) is assembled directly."""
    feedback = None
    sha = package_sha256(package)
    usage_all: list[dict] = []
    repairs: list[str] = []  # why each earlier attempt was rejected (M3.1: which rule fired)
    for attempt in range(1, max_attempts + 1):
        t_call = time.monotonic()
        output, usage = composer.complete(package, feedback)
        usage = {**usage, "attempt": attempt, "call_seconds": round(time.monotonic() - t_call, 2)}
        usage_all.append(usage)
        meta = ComposerMeta(
            composer=composer.name, model=composer.model, prompt_version=PROMPT_VERSION,
            package_sha256=sha, attempts=attempt, usage={"calls": usage_all, "repairs": list(repairs)},
        )
        t_val = time.monotonic()
        try:
            if _is_selection(output):
                if writer is None:
                    raise RuntimeError("a selection-only composer output needs a card writer")
                result = compose_written(package, output, fragments, meta, writer, quote_source, max_writer_attempts,
                                         validator, resolve_same_author=attempt == max_attempts)
            else:
                result = assemble_result(package, output, fragments, meta, quote_source=quote_source)
            usage["validation_seconds"] = round(time.monotonic() - t_val, 3)
            return result
        except (ValidationError, ValueError, KeyError, TypeError) as exc:
            usage["validation_seconds"] = round(time.monotonic() - t_val, 3)
            feedback = str(exc)[:1500]
            repairs.append(feedback)
    raise ValueError(f"{package['item_id']}: composition failed validation after {max_attempts} attempts: "
                     + " || ".join(f"attempt {i}: {r}" for i, r in enumerate(repairs, 1)))

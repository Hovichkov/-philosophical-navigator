"""Independent grounding validation (M3.4.2).

Why a separate step. Since M3.3.2 the card writer labels its own claims (``grounding`` audit) and code checks the
verbatim evidence. That catches what the writer marked, but the writer also decides WHETHER a sentence is a hypothesis
about the person: a hypothesis it did not notice passes untouched. In M3.4.1 the «Подробнее» of a card ended with
«стыд … откликается не на поступок, а на перемену в чужом взгляде» — an explanation of this person's shame that the
writer had called a general distinction.

This validator is a separate model call per written card. It never sees the writer's audit; it gets only
  - the person's own words (story, confirmed question, chosen feelings, topic),
  - the source material the writer was given (corpus description, move of the text, reference),
  - the final user-facing text of the card (all six fields),
and classifies every sentence itself. A sentence in a violating class fails the card; the writer rewrites THIS card
only, with the exact sentences and the reason (``writer.write_card``). Deterministic checks for obvious patterns
(invented time horizons, «Конфуций предложил бы») run before it in ``writer.check_card``.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass

from navigator.timing import cli_error_message, cli_usage

VALIDATOR_PROMPT_VERSION = "grounding-validator-prompt/0.1.0"
FIELD_NAMES = {"title": "заголовок", "main_idea": "что говорит источник", "applied_insight": "применение к вопросу",
               "reflection_question": "вопрос к себе", "question_explanation": "«Что имеется в виду?»",
               "perspective": "«Подробнее»"}

OK_LABELS = ("given", "source_frame", "open_hypothesis", "open_question", "general_distinction")
VIOLATIONS = {
    "hypothesis_as_fact": "гипотеза о человеке подана как факт (причина чувства, мотив, убеждение, механизм, "
                          "реакция или мысли других) — предложите её для проверки или уберите",
    "identity_decided": "система решает за человека, что было «ролью», а что «им самим», или отвечает на «кто я» "
                        "за него — оставьте различение предметом его исследования",
    "invented_specific": "придуманная конкретика ситуации (срок, горизонт, сцена, число, поведение), которой нет "
                         "в словах человека и которой не требует источник",
    "author_simulation": "историческому автору приписана реплика современному человеку («предложил бы вам…») — "
                         "источник даёт мысль, применяет её система",
    "emotional_prescription": "предписание, как человеку следует чувствовать или переживать («спокойно», «без "
                              "страха», «честно», «правильно»…)",
    "forced_choice": "вопрос подсовывает гипотезу как один из заранее заданных вариантов и закрывает другие "
                     "(«за X или за Y?»), хотя человек этого не говорил — спросите открыто",
    "source_beyond_data": "об источнике сказано то, чего нет в переданном материале источника",
}

VALIDATOR_PROMPT = """Ты — независимый проверяющий философского навигатора. Ты не писал эту карточку. Тебе даны три вещи: СЛОВА ЧЕЛОВЕКА (всё, что он сам сказал или выбрал), МАТЕРИАЛ ИСТОЧНИКА (то, что знал автор карточки об источнике) и ТЕКСТ КАРТОЧКИ, который увидит человек. Твоя задача — найти места, где карточка утверждает о человеке или его ситуации то, чего нет в его словах, или говорит об источнике то, чего нет в материале.

Главное правило продукта: философия может дать различение и из него — вопрос. Путь «источник → различение → гипотеза о человеке → гипотеза подана как факт» запрещён.

Разбери КАЖДОЕ предложение каждого поля (заголовок, что говорит источник, применение, вопрос к себе, «Что имеется в виду?», «Подробнее») и дай ему одну метку:
Допустимые:
- given — прямо опирается на слова человека («Вы пишете, что вам стыдно сказать друзьям»).
- source_frame — мысль, различение или ход источника, которые есть в материале источника; не утверждает нового факта о человеке («Лао-цзы связывает почёт и унижение с зависимостью от чужого отношения»). Различение источника можно формулировать уверенно.
- general_distinction — общая мысль о вещах, которая не служит в контексте объяснением именно этого человека («признать предел ещё не значит сдаться»).
- open_hypothesis — возможное применение различения к человеку, предложенное для проверки («Можно проверить, связан ли стыд с тем, как вы представляете разговор с друзьями»).
- open_question — вопрос, который оставляет человеку самому решить и не подсовывает готовый ответ.
Нарушения:
- hypothesis_as_fact — о человеке или другом человеке из рассказа утверждается как факт то, чего он не говорил: причина чувства, мотив, намерение, скрытое желание, ценность, убеждение, отношение, неназванный страх, реакция или мысли других, способность, черта, психологический механизм, будущее или последствия. ВНИМАНИЕ: общее предложение («стыд откликается на перемену в чужом взгляде») тоже нарушение, если в контексте карточки оно служит объяснением ЭТОГО человека.
- identity_decided — ответ за человека, кто он и что было «ролью», а что «им самим» («работа была ролью, а не частью вас», «потерять место не значит потерять себя» как ответ на его «кто я»).
- invented_specific — придуманная конкретика: срок или горизонт («через год», «на следующей неделе»), сцена, число, поведение, которых нет в его словах и которых не требует источник.
- author_simulation — автору приписана реплика современному человеку («Конфуций предложил бы…», «Эпиктет сказал бы вам…»).
- emotional_prescription — указание, как человеку следует чувствовать или переживать («можно спокойно принять», «без страха разобраться», «честно признать»); проверяй функцию в предложении, а не само слово.
- forced_choice — вопрос с заранее заданными вариантами, один из которых — гипотеза, которой человек не называл, а другие возможности исчезают («За поступки мне стыдно или за то, что у меня нет прежнего места?», если человек уже сказал, что не виноват).
- source_beyond_data — об источнике сказано то, чего нет в материале источника (подробности сюжета, «часто говорит», биография, знание из памяти).

Не будь придирчивым к языку и не требуй оговорок: уверенное различение источника и слова человека — это нормально. Нарушение — только там, где появляется НОВЫЙ факт о человеке или об источнике, решение за человека или предписание. Не выдумывай нарушений.
Для каждого предложения верни field (одно из: title, main_idea, applied_insight, reflection_question, question_explanation, perspective), sentence — ДОСЛОВНО как в тексте, label и reason (коротко). Отвечай по-русски, строго по JSON-схеме."""

VALIDATOR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["sentences"],
    "properties": {
        "sentences": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False, "required": ["field", "sentence", "label", "reason"],
                "properties": {
                    "field": {"type": "string", "enum": list(FIELD_NAMES)},
                    "sentence": {"type": "string"},
                    "label": {"type": "string", "enum": [*OK_LABELS, *VIOLATIONS]},
                    "reason": {"type": "string"},
                },
            },
        },
    },
}


class ValidatorUnavailable(RuntimeError):
    pass


@dataclass
class ClaudeCodeCLIValidator:
    model: str = "claude-opus-5-5"
    timeout_s: int = 300
    name: str = "claude-code-cli"
    effort: str | None = None

    def complete(self, material: dict) -> tuple[dict, dict]:
        user = "Материал для проверки (JSON):\n" + json.dumps(material, ensure_ascii=False, indent=1)
        cmd = [
            "claude", "-p", "--safe-mode", "--tools", "", "--strict-mcp-config", "--no-session-persistence",
            "--model", self.model, "--system-prompt", VALIDATOR_PROMPT,
            "--output-format", "json", "--json-schema", json.dumps(VALIDATOR_SCHEMA, ensure_ascii=False),
            *(["--effort", self.effort] if self.effort else []),
        ]
        t0 = time.monotonic()
        try:
            proc = subprocess.run(cmd, input=user, capture_output=True, text=True, timeout=self.timeout_s)
            payload = json.loads(proc.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            raise ValidatorUnavailable(str(exc)[:500]) from exc
        if payload.get("is_error") or not isinstance(payload.get("structured_output"), dict):
            raise ValidatorUnavailable(cli_error_message(payload))
        return payload["structured_output"], cli_usage(payload, time.monotonic() - t0)


def validation_material(user_words: dict, source_material: dict, card: dict) -> dict:
    """Exactly what the validator sees. No writer audit, no selection reasoning — only the three ground truths."""
    return {"слова_человека": user_words, "материал_источника": source_material,
            "текст_карточки": {FIELD_NAMES[k]: card[k] for k in FIELD_NAMES if card.get(k)}}


def _norm(t: str) -> str:
    return " ".join(re.findall(r"\w+", (t or "").lower().replace("ё", "е")))


def violations_of(output: dict, card: dict) -> list[dict]:
    """Violating sentences that really occur in the card (a quote the validator made up is ignored)."""
    out = []
    for s in output.get("sentences") or []:
        if s.get("label") not in VIOLATIONS:
            continue
        if _norm(s.get("sentence", "")) and _norm(s["sentence"]) in _norm(card.get(s.get("field"), "")):
            out.append(s)
    return out


def feedback_for(violations: list[dict]) -> str:
    lines = ["Независимая проверка нашла в карточке места, где сказано больше, чем известно. Исправь ТОЛЬКО эти "
             "предложения, остальное сохрани:"]
    for v in violations[:6]:
        lines.append(f"- [{FIELD_NAMES.get(v['field'], v['field'])}] «{v['sentence'][:220]}» — {VIOLATIONS[v['label']]}"
                     f" ({v.get('reason', '')[:160]})")
    return "\n".join(lines)

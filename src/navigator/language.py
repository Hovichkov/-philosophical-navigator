"""User-facing language rules and reference voice (M3.3).

Source of truth: ``LANGUAGE-GUIDE.md`` at the project root. This module carries the parts that go
into the Interpretation and Composition prompts; the reference texts must stay identical to the
guide (checked by tests).
"""

from __future__ import annotations

# The three cards the user rewrote by hand after M3.2 (verbatim from LANGUAGE-GUIDE.md).
REFERENCE_VOICE = (
    "Моисей в какой-то момент прямо говорит: одному мне это не поднять. Но дело он не бросает. "
    "Он зовёт других и делит груз с ними.\n\n"
    "Вы спрашиваете, смириться со своими пределами или дальше пытаться. Моисей поступает по-третьему: "
    "честно говорит, что сил не хватает, и поэтому начинает работать иначе. Признать, что не справляешься, "
    "ещё не значит сдаться.\n\n"
    "Вопрос к себе: что в моих делах можно делать по-другому? Не больше и не меньше, а именно по-другому.",

    "В Дао дэ цзин есть мысль, что неполное может стать целым, а кривое прямым. Нехватка не обязательно "
    "означает поражение. И сохранить себя иногда помогает гибкость, а не упорство.\n\n"
    "Вы спрашиваете, где кончается бережность к себе и начинается отказ от себя. Лао-цзы подсказывает, "
    "что уступить не всегда значит проиграть. Можно перестать давить на себя и всё равно остаться собой.\n\n"
    "Вопрос к себе: где я заставляю себя идти напролом, хотя можно было бы обойти?",

    "Для Бхагавад-гиты неважно, сколько человек успел или сидит ли он без дела. Важно, с каким настроем "
    "он делает то, что делает.\n\n"
    "Вы выбираете между дисциплиной и жалостью к себе. Но в обоих случаях вы судите себя по одной мерке: "
    "сколько сделано. Гита предлагает посмотреть, что происходит у вас внутри, пока вы работаете.\n\n"
    "Вопрос к себе: как я отношусь к себе, когда работаю? И как отношусь к тому, что у меня получится?",
)

import re

LANGUAGE_RULES = """ЯЗЫК (LANGUAGE-GUIDE проекта; касается ВСЕГО текста, который увидит человек):
- Правило одного прочтения: текст понятен с первого нормального чтения. Сложной может быть мысль, но не синтаксис.
- Нормальный разговорный литературный русский. Конкретные глаголы: «не поднять», «не хватает сил», «справляться», «давить на себя», «идти напролом», «обойти», «бросить дело», «позвать других», «делать иначе». Не заменяй глагол абстрактным существительным ради философского звучания.
- Без промежуточного концептуального языка — сначала скажи саму мысль. Плохо: «После признания предела меняется само устройство действия». Лучше: «Он признаёт, что один не справляется, и начинает работать иначе». Плохо: «Гита предлагает посмотреть на способ участия в действии». Лучше: «Гита предлагает посмотреть, что происходит у вас внутри, пока вы работаете».
- Один смысловой шаг — одно предложение. Короткие предложения естественно связаны с соседними; цель не рубить текст, а убрать разбор синтаксиса.
- Без философского метаязыка: «карточка утверждает», «фрагмент показывает», «текст проблематизирует», «способ участия», «структура отношения», «изменение рамки», «оптика текста», «различение», «предпосылка».
- Не додумывай человека: не утверждай мотив, функцию чувства, потребность, причину реакции, страх, зависимость самооценки, непринятую часть личности, биографию, сравнение с другими, если человек этого не сказал. «Возможно» не даёт права на психологическую гипотезу. Философия приносит новое различение, а не новую биографию человека.
- Проверка вслух: каждое предложение должно звучать так, как живой человек сказал бы его другу. Не как философский комментарий, академический пересказ, «умный» нейросетевой русский, психотерапевтическая формула или перевод с английского.
- Местоимения: у каждого «он, она, оно, они, его, её, в нём, в ней, это, там, так» есть очевидный предмет рядом. Если читатель может спросить «в нём — в чём?», «его — чего?», назови предмет снова."""


# ------------------------------------------------------------------ deterministic language checks (M3.3.1)
# Only checks that are reliable as structure, never a style blacklist of ordinary words.

# Feelings / people the person may name themselves. A group counts as "unnamed" if the text uses it while the
# person's own words (story, question, chosen experiences, difficulty) never do.
PERSON_CLAIM_GROUPS = {
    "страх": r"\bстрах\w*|\bстраш\w*|\bбоязн\w*|\bбо(?:юсь|ишься|ится|имся|итесь|ятся|ялся|ялась|ялись|язн\w*)\b|\bпуга\w*|\bопаса(?:ется|етесь|юсь)\b",
    "любовь": r"\bлюб(?:овь|ви|овью|лю|ишь|ит|им|ите|ят|ящ\w*|им\w*)\b",
    "стыд": r"\bстыд\w*|\bстыж\w*",
    "вина": r"\bвин(?:а|ы|у|ой|е)\b|\bвиноват\w*",
    "тревога": r"\bтревог\w*|\bтревож\w*",
    "гнев": r"\bгнев\w*|\bзлост\w*|\bзлит\w*|\bзлюсь\b",
    "обида": r"\bобид\w*",
    "зависть": r"\bзавид\w*|\bзависть\b",
    "одиночество": r"\bодиночеств\w*|\bодинок\w*",
    # each profession separately: a person who mentions a neurologist has not mentioned a psychologist
    "психолог": r"\bпсихолог\w*",
    "психотерапевт": r"\bпсихотерапевт\w*|\bтерапевт\w*",
    "психиатр": r"\bпсихиатр\w*",
    "невролог": r"\bневролог\w*",
    "специалист (общее слово)": r"\bспециалист\w*|\bврач\w*",
}
_ANY_SPECIALIST = r"\bпсихолог\w*|\bпсихотерапевт\w*|\bтерапевт\w*|\bпсихиатр\w*|\bневролог\w*|\bспециалист\w*|\bврач\w*"


def unnamed_person_claims(text: str, user_words: str) -> list[str]:
    """Feelings or outside specialists the text brings in although the person never named them."""
    out = []
    for g, pat in PERSON_CLAIM_GROUPS.items():
        if not re.search(pat, text, flags=re.IGNORECASE):
            continue
        ground = _ANY_SPECIALIST if g.startswith("специалист") else pat  # «врач» is fine if any specialist was named
        if not re.search(ground, user_words, flags=re.IGNORECASE):
            out.append(g)
    return out


# The corpus has no verified source text (quote readiness READY = 0): the card must not sound as if it had just
# read and checked a chapter / verse. The reference is shown separately, built by code.
FALSE_PRECISION = (r"\b\d+\s*[-–]?\s*(?:й|я|ой|ая|м|ом)?\s+глав", r"\bглав[аеуыой]+\s+\d", r"\b\d+\s*:\s*\d+",
                   r"\bстих\w*\s+\d", r"\bаят\w*\s+\d", r"§")


def false_precision_hits(text: str) -> list[str]:
    return [p for p in FALSE_PRECISION if re.search(p, text, flags=re.IGNORECASE)]


# Only the forms that pointed nowhere in the manual test: a pronoun after a preposition standing for a THING
# («что в нём можно устроить», «сказать в его пользу»). «Что ему нужно?» after «…сыну?» is clear and allowed;
# the general pronoun rule is in the prompts.
_POINTING_BACK = (r"\b(?:в|во|о|об|на|при)\s+(?:нём|нем|ней|них)\b", r"\bв\s+(?:его|её|ее|их)\s+пользу\b",
                  r"^\s*(?:и\s+)?(?:в\s+)?(?:нём|нем|ней|них)\b")


def ambiguous_second_question(question: str) -> bool:
    """Two-part question whose second part points back to the first with «в нём», «в его пользу» …"""
    parts = [p for p in re.split(r"(?<=[?.!])\s+", question.strip()) if p]
    return len(parts) >= 2 and any(re.search(p, parts[1], flags=re.IGNORECASE) for p in _POINTING_BACK)


def sentence_count(text: str) -> int:
    return len([p for p in re.split(r"(?<=[?.!…])\s+", text.strip()) if p])


# ------------------------------------------------------------------ M3.4 deterministic helpers

# Titles of works in running prose get «» (M3.4). Only the corpus works whose titles are not also ordinary words or
# a person's name; sacred scriptures (Библия, Завет, Евангелие, Коран, Тора) are not quoted in Russian usage.
# «Беседы» is quoted only when capitalised inside a sentence (the ordinary word «беседы» stays untouched).
_WORK_TITLES = (
    r"Бхагавад-гит\w*", r"(?<![-\w])Гит(?:а|е|ы|у|ой)\b", r"Дао\s+[дД]э\s+[цЦ]зин\w*", r"Дхаммапад\w*",
    r"Лунь\s+[юЮ]й\b", r"Письм(?:о|а|е|у|ом)\s+к\s+Менекею", r"Энхиридион\w*", r"Брихадараньяка-упанишад\w*",
    r"(?<=[\w,:;—–-] )Бесед(?:ы|ах|ам|ами|е|у)?\b",
)
_WORK_RE = re.compile(r"(?<!«)(" + "|".join(_WORK_TITLES) + r")(?!»)")


def quote_work_titles(text: str) -> str:
    """«Бхагавад-гита», в «Бхагавад-гите», «Беседы» … in prose. Already quoted titles are left as they are.
    Not applied to the separate reference line (it is built by code and stays bibliographic)."""
    return _WORK_RE.sub(lambda m: f"«{m.group(1)}»", text)


def _content_words(sentence: str) -> set[str]:
    return {w for w in re.findall(r"\w+", sentence.lower().replace("ё", "е")) if len(w) > 3}


def retold_sentences(detail: str, card_text: str, threshold: float = 0.6) -> list[str]:
    """Sentences of «Подробнее» that restate a sentence of the main card or of «Что имеется в виду?» (M3.4): a
    reliable signal of retelling. Similar ideas in new words are not caught — that is the prompt's and the reader's
    job."""
    base = [_content_words(x) for x in re.split(r"(?<=[.!?…])\s+", card_text) if x.strip()]
    out = []
    for sent in re.split(r"(?<=[.!?…])\s+", detail.strip()):
        w = _content_words(sent)
        if len(w) < 3:
            continue
        if any(b and len(w & b) / len(w | b) >= threshold for b in base):
            out.append(sent)
    return out


# The person's anchor words that must not be swapped for a near-synonym that changes the frame (M3.4). Each entry:
# (what the person's words contain, what the text must not introduce unless the person used it too).
ANCHOR_SHIFTS = (
    ("принять", r"\bприн(?:ять|имать|имаю|имает|яти\w*|ял\w*)", r"\bсмир(?:и|я|ен)\w*"),
)


def anchor_shift_hits(text: str, user_words: str) -> list[str]:
    out = []
    for name, anchor, swap in ANCHOR_SHIFTS:
        if (re.search(anchor, user_words, flags=re.IGNORECASE) and re.search(swap, text, flags=re.IGNORECASE)
                and not re.search(swap, user_words, flags=re.IGNORECASE)):
            out.append(name)
    return out


# ------------------------------------------------------------------ M3.4.1 deterministic helpers

# Grammatical gender of the person, only from their own words (a first-person past verb or short adjective).
# Unknown → the text must use gender-neutral forms for the person.
_PAST = r"\w{2,}(?:{end})\b"
_FEM = (r"\bя\b[^.?!]{0,40}?\b\w{2,}(?:ала|яла|ела|ила|ула|ыла|лась)\b",
        r"\bя\b[^.?!]{0,30}?\b(?:была|должна|готова|рада|уверена|согласна|сама|одна|способна)\b",
        r"\bбыть\s+\w+(?:ой|ей)\b(?=[^.?!]*\bя\b|)")
_MASC = (r"\bя\b[^.?!]{0,40}?\b\w{2,}(?:ал|ял|ел|ил|ул|ыл|лся)\b",
         r"\bя\b[^.?!]{0,30}?\b(?:был|должен|готов|рад|уверен|согласен|сам|один|способен)\b")


def person_gender(user_words: str) -> str | None:
    """'f' / 'm' from the person's own first-person forms; None when unknown or contradictory."""
    t = user_words.lower()
    f = any(re.search(p, t) for p in _FEM)
    m = any(re.search(p, t) for p in _MASC)
    return "f" if f and not m else "m" if m and not f else None


_GENDERED_FIRST_PERSON = (
    r"\bя\b[^.?!,]{0,40}?\b\w{2,}(?:ал|ял|ел|ил|ул|ыл|ала|яла|ела|ила|ула|ыла|лся|лась)\b",
    r"\bя\b[^.?!,]{0,30}?\b(?:был|была|должен|должна|готов|готова|рад|рада|уверен|уверена|согласен|согласна|"
    r"способен|способна|сам|сама|один|одна)\b",
)


def gendered_first_person_hits(text: str) -> list[str]:
    """Gendered first-person forms («я готов», «я решила») — wrong when the person's gender is unknown.
    Only first-person clauses: a gendered word about a known character of the source is not touched."""
    out = []
    for p in _GENDERED_FIRST_PERSON:
        out += [m.group(0) for m in re.finditer(p, text, flags=re.IGNORECASE)]
    return out


# An open hypothesis about the person must be written openly: a question, «возможно», «может быть», «если», «ли»,
# «проверить», «предлагает различить». The evidence is a verbatim sentence of the field, so this is checked on text.
OPEN_MARKERS = r"\?|\bвозможно\b|\bможет\s+быть\b|\bесли\b|\bли\b|\bпровер\w*|\bпредлага\w*"


def is_open_formulation(sentence: str) -> bool:
    return bool(re.search(OPEN_MARKERS, sentence, flags=re.IGNORECASE))


def stem_hits(words: list[str], text: str, stem_len: int = 4) -> list[str]:
    """Which listed words (by their first ``stem_len`` letters) occur in ``text``."""
    tw = re.findall(r"\w+", text.lower().replace("ё", "е"))
    out = []
    for w in words:
        w = (w or "").lower().replace("ё", "е").strip()
        if len(w) < 3:
            continue
        st = w[:stem_len] if len(w) > stem_len else w
        if any(t.startswith(st) for t in tw):
            out.append(w)
    return out


# Causal questions the interpretation must not add on its own (M3.4.1): the person mentions a feeling, the proposed
# question turns it into «почему …?». Kept when the person asked it themselves.
CAUSAL_QUESTION = (r"\bпочему\b", r"\bиз-за\s+чего\b", r"\bчто\s+заставляет\b", r"\bна\s+самом\s+ли\s+деле\b",
                   r"\bотчего\b", r"\bв\s+чём\s+причин\w*")


def added_causal_question(question: str, user_words: str) -> list[str]:
    return [p for p in CAUSAL_QUESTION
            if re.search(p, question, flags=re.IGNORECASE) and not re.search(p, user_words, flags=re.IGNORECASE)]


# ------------------------------------------------------------------ M3.4.2 deterministic helpers

# Invented time horizons: a concrete period the person never named («через год», «на следующей неделе»).
_HORIZONS = (r"\bчерез\s+(?:\d+\s+|пару\s+|несколько\s+|полгода|год\w*|месяц\w*|недел\w*|пять|два|три|десять)[\w\s]{0,12}?"
             r"(?:лет|год\w*|месяц\w*|недел\w*|дн\w*)?\b",
             r"\bна\s+следующ\w+\s+(?:недел\w*|месяц\w*|год\w*)", r"\bв\s+следующ\w+\s+(?:месяц\w*|году)\b",
             r"\bчерез\s+полгода\b")


def invented_horizon_hits(text: str, user_words: str) -> list[str]:
    out = []
    for p in _HORIZONS:
        for m in re.finditer(p, text, flags=re.IGNORECASE):
            span = m.group(0).strip()
            if not re.search(re.escape(span), user_words, flags=re.IGNORECASE):
                out.append(span)
    return out


# A historical author made to speak to a modern user: «Конфуций предложил бы…», «Эпиктет сказал бы вам…».
_AUTHOR_SIMULATION = r"\b(?:предложил|сказал|посоветовал|спросил|ответил|возразил|напомнил|подсказал|заметил)\w*\s+бы\b"


def author_simulation_hits(text: str) -> list[str]:
    return [m.group(0) for m in re.finditer(_AUTHOR_SIMULATION, text, flags=re.IGNORECASE)]


def reference_voice_block() -> str:
    parts = [f"Эталон {'ABC'[i]}:\n{t}" for i, t in enumerate(REFERENCE_VOICE)]
    return ("ЭТАЛОННЫЙ ГОЛОС — три карточки, которые пользователь переписал вручную. Извлеки из них манеру "
            "(источник простыми словами с именем → слова человека «Вы спрашиваете…» → ясное различение → "
            "конкретный разговорный вопрос). НЕ копируй их фразы и сюжеты в другие случаи.\n\n" + "\n\n".join(parts))

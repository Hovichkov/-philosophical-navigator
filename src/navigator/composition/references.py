"""Reader-friendly source references (M3.3).

Built by code from corpus metadata (work + location), never by the model. The corpus keeps its
own short notation (``Чис 11:10–17``, ``БГ 4.16–23``, ``Чжан 22``); the user sees
``Ветхий Завет, Числа 11:10–17``, ``Бхагавад-гита, 4.16–23``, ``Дао дэ цзин, глава 22``.
Each tradition keeps its natural coordinate system. Authors are added only where the project's
source registry (``filosofskiy-korpus-istochniki.md``) names them for the work.
"""

from __future__ import annotations

import re

from navigator.models.fragment import Fragment

OLD_TESTAMENT = {
    "Быт": "Бытие", "Исх": "Исход", "Лев": "Левит", "Чис": "Числа", "Втор": "Второзаконие",
    "Иов": "Иов", "Еккл": "Екклесиаст", "Пс": "Псалтирь", "Притч": "Притчи",
}
NEW_TESTAMENT = {"Мф": "Матфея", "Мк": "Марка", "Лк": "Луки", "Ин": "Иоанна"}

# Author named by the project source registry for works whose corpus rows have author = null.
REGISTRY_AUTHOR = {
    "Беседы": "Эпиктет", "Энхиридион / Руководство": "Эпиктет", "Письмо к Менекею": "Эпикур",
    "Главные мысли": "Эпикур", "Лунь юй": "Конфуций", "Диалоги Платона": "Платон",
}
WORK_DISPLAY = {"Энхиридион / Руководство": "Энхиридион", "Sallatha Sutta": "Саллатха-сутта"}


def bible_reference(location: str) -> str | None:
    m = re.match(r"^\s*([А-ЯЁ][а-яё]+)\.?\s+(.+)$", location or "")
    if not m:
        return None
    book, rest = m.group(1), m.group(2).strip()
    if book in OLD_TESTAMENT:
        return f"Ветхий Завет, {OLD_TESTAMENT[book]} {rest}"
    if book in NEW_TESTAMENT:
        return f"Новый Завет, {NEW_TESTAMENT[book]} {rest}"
    return None


def display_reference(work: str, location: str, author: str | None = None) -> str:
    """User-facing reference for a corpus card."""
    loc = (location or "").strip()
    bible = bible_reference(loc)
    if bible:
        return bible
    if work == "Бхагавад-гита":
        return "Бхагавад-гита, " + re.sub(r"^БГ\s*", "", loc)
    if work in ("Дао дэ цзин", "Чжуан-цзы"):
        return f"{work}, " + re.sub(r"^(?:Чжан|Гл\.)\s*", "глава ", loc)
    if work == "Дхаммапада":
        return f"Дхаммапада, {'стихи' if re.search(r'[–-]', loc) else 'стих'} {loc}"
    if work == "Фрагменты ранних греческих философов":
        return f"{work}, " + re.sub(r"^Фр\.\s*", "фр. ", loc)
    if work == "Диалоги Платона":
        return f"Платон, {loc}"
    name = WORK_DISPLAY.get(work, work)
    who = author or REGISTRY_AUTHOR.get(work)
    return ", ".join(p for p in (who, name, loc) if p)


def fragment_reference(f: Fragment) -> str:
    return display_reference(f.work, f.location, f.author)


# ------------------------------------------------------------------ MVP display label «автор · произведение · место»
# Presentation only (final corpus, MVP pass 1): the corpus CSV keeps its evidence values verbatim; the user sees a clean
# bibliographic line without editorial notes («(speaker по фрагменту)», «**…**», «(candidate master…)»).
NEW_TESTAMENT_DISPLAY = {"Мф": "От Матфея", "Мк": "От Марка", "Лк": "От Луки", "Ин": "От Иоанна"}
NO_AUTHOR_WORKS = {"Бхагавад-гита", "Коран", "Тора / Пятикнижие", "Евангелия", "Книга Иова и Экклезиаст"}
PLATO_WORKS = {"Апология Сократа", "Евтифрон", "Протагор", "Менон"}
PRESOCRATICS = "Фрагменты ранних греческих философов"


def _clean(text: str) -> str:
    text = re.sub(r"[*`]+", "", text or "")
    text = re.sub(r"\s*\([^)]*\)", "", text)  # editorial parentheses
    return re.sub(r"\s+", " ", text).strip(" ,;/")


def _display_author(f: Fragment) -> str | None:
    work, author = f.work or "", f.author or ""
    if work in NO_AUTHOR_WORKS or "упанишада" in work.lower():
        return None  # collective / many voices: the work itself is the source
    if work in PLATO_WORKS:
        return "Платон"
    a = _clean(author.split(";")[0])
    a = a.split(" / ")[0].strip().rstrip(".")
    return a or REGISTRY_AUTHOR.get(work)


def _display_work_and_place(f: Fragment, author: str | None) -> tuple[str | None, str | None]:
    work, loc = f.work or "", _clean(f.location or "")
    m = re.match(r"^\s*([А-ЯЁ][а-яё]+)\.?\s+(\d.*)$", loc)
    if work in ("Тора / Пятикнижие", "Книга Иова и Экклезиаст") and m and m.group(1) in OLD_TESTAMENT:
        return "Ветхий Завет", f"{OLD_TESTAMENT[m.group(1)]} {m.group(2)}"
    if work == "Евангелия" and m and m.group(1) in NEW_TESTAMENT_DISPLAY:
        return "Новый Завет", f"{NEW_TESTAMENT_DISPLAY[m.group(1)]} {m.group(2)}"
    if " — " in work and "сутта" in work.lower():  # «Анатта-лаккхана сутта — СН 22.59»: the canonical number is the place
        name, ref = work.split(" — ", 1)
        return name.strip(), ref.strip()
    if work == "Дхаммапада":
        return work, f"{'стихи' if re.search(r'[–-]', loc) else 'стих'} {loc}"
    if work == "Дао дэ цзин":
        return work, re.sub(r"^(?:Чжан|Гл\.)\s*", "глава ", loc)
    if work == PRESOCRATICS:
        if author and loc.startswith(author + ","):
            loc = loc[len(author) + 1:].strip()
        head, _, tail = loc.partition(" / ")
        if tail and loc[:1].islower() and not re.search(r"\d", head):  # «вводная реконструкция учения / А 9» → «А 9»
            loc = tail.strip()
        return None, (loc if re.search(r"\d", loc) else None)
    return WORK_DISPLAY.get(work, work) or None, loc or None


def display_label(f: Fragment) -> str:
    """«автор · произведение · место» for the user (e.g. «Будда · Амбалаттхикарахуловада сутта · МН 61»)."""
    author = _display_author(f)
    work, place = _display_work_and_place(f, author)
    parts = [p for p in (author, work, place) if p]
    return " · ".join(dict.fromkeys(parts))

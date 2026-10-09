"""Retrieval readiness of canonical Fragments (M1.5).

This module selects which *existing field values* may feed the MEANING and
STRUCTURE representations (TECHNICAL-DESIGN §7–§8) and audits whether they carry
card-specific content. It does NOT serialise representations, embed or index
anything — the serialisation format stays an EVAL PARAMETER for Milestone 2.

Guarantees:
- only retrieval-eligible (verified) Fragments are in the retrieval universe;
- editorial placeholders / working notes are never returned as semantic input.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from navigator.models.fragment import Fragment
from navigator.models.vocabularies import EDITORIAL_MARKERS, PHILOSOPHICAL_OPERATIONS_V0_1

# Template scaffolding produced by the textual pass around the launch move.
TEMPLATE_PREFIXES: tuple[str, ...] = (
    "Рассмотреть ситуацию через операцию, которую задаёт сам фрагмент:",
    "Какой философский ход совершает текст в ситуации:",
    "Launch-кандидат фиксирует следующий исходный ход:",
    "Рабочее прочтение следует непосредственно за этим ходом:",
)

# Below this many distinct content words (len > 3) the MEANING input is reported as THIN.
THIN_WORD_THRESHOLD = 5


def is_editorial(text: str | None) -> bool:
    return text is not None and any(m in text for m in EDITORIAL_MARKERS)


def retrieval_universe(fragments: Iterable[Fragment]) -> list[Fragment]:
    """Fragments that may be retrieved: retrieval-eligible and verified (launch) or registry-curated (restored full
    corpus). Unresolved and registry-reserve rows never enter retrieval."""
    return [
        f
        for f in fragments
        if f.technical.retrieval_eligible
        and f.technical.operational_status in ("verified", "registry_curated", "final_active")
    ]


def meaning_inputs(fragment: Fragment) -> dict[str, list[str]]:
    """Usable MEANING field values (thought, philosophical_questions, perspective)."""
    out: dict[str, list[str]] = {}
    if fragment.thought and not is_editorial(fragment.thought):
        out["thought"] = [fragment.thought]
    questions = [q for q in fragment.philosophical_questions or [] if not is_editorial(q)]
    if questions:
        out["philosophical_questions"] = questions
    if fragment.perspective and not is_editorial(fragment.perspective):
        out["perspective"] = [fragment.perspective]
    return out


def structure_inputs(fragment: Fragment) -> dict[str, list[str]]:
    """Usable STRUCTURE field values (coordinates, tensions, question_structures, operation)."""
    out: dict[str, list[str]] = {}
    for field in ("coordinates", "tensions", "question_structures"):
        values = [v for v in getattr(fragment, field) or [] if not is_editorial(v)]
        if values:
            out[field] = values
    op = fragment.philosophical_operation
    if op and op in PHILOSOPHICAL_OPERATIONS_V0_1:
        out["philosophical_operation"] = [op]
    return out


def generic_questions(fragments: Iterable[Fragment]) -> set[str]:
    """Questions shared verbatim by more than one Fragment (template questions)."""
    counts = Counter(q for f in fragments for q in f.philosophical_questions or [])
    return {q for q, n in counts.items() if n > 1}


def specific_meaning_text(fragment: Fragment, generic: set[str]) -> str:
    """MEANING input with template scaffolding and shared questions removed."""
    inputs = meaning_inputs(fragment)
    parts = inputs.get("thought", []) + [q for q in inputs.get("philosophical_questions", []) if q not in generic]
    parts += inputs.get("perspective", [])
    text = " ".join(parts)
    for prefix in TEMPLATE_PREFIXES:
        text = text.replace(prefix, " ")
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class MeaningReadiness:
    fragment_id: str
    state: str  # READY | THIN | EDITORIAL | GENERIC | EMPTY
    specific_words: int
    has_thought: bool

    @property
    def usable(self) -> bool:
        return self.state in {"READY", "THIN"}


def meaning_readiness(fragment: Fragment, generic: set[str]) -> MeaningReadiness:
    inputs = meaning_inputs(fragment)
    raw_present = any(
        [fragment.thought, fragment.philosophical_questions, fragment.perspective]
    )
    words = {w for w in re.findall(r"\w+", specific_meaning_text(fragment, generic).lower()) if len(w) > 3}
    if not inputs:
        state = "EDITORIAL" if raw_present else "EMPTY"
    elif not words:
        state = "GENERIC"
    elif len(words) < THIN_WORD_THRESHOLD:
        state = "THIN"
    else:
        state = "READY"
    return MeaningReadiness(fragment.id, state, len(words), "thought" in inputs)


def structure_ready(fragment: Fragment) -> bool:
    """Minimal STRUCTURE participation: valid operation, ≥1 question structure, ≥1 coordinate."""
    inputs = structure_inputs(fragment)
    return all(k in inputs for k in ("philosophical_operation", "question_structures", "coordinates"))

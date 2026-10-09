"""Deterministic MEANING representations.

Current specification — M2.4 "MEANING separation" (``MEANING_SPEC_ID = meaning-v2``):

MEANING = meaning of the human question ↔ meaning of the philosophical perspective.
TAXONOMY vocabulary (coordinates, tensions) belongs to STRUCTURE only; M2.3 showed
that carrying it in MEANING duplicated the STRUCTURE signal and produced a strong bias.

- Card document (``meaning-card-doc/2.0``): perspective, philosophical_questions.
  Values come through ``readiness.meaning_inputs``, so editorial placeholders never
  reach the text. Thought, fragment, commentary, context, author, tradition,
  translation, verification, technical fields, coordinates and tensions are not read.
- Q0 (``q0-question-only/1.0``): the confirmed question, verbatim (unchanged).
- Q1 (``q1-meaning-query/2.0``): confirmed question + working hypotheses.
  Coordinates, canonical/free tensions, context, circumstance and experiences are
  never included; they stay in the QueryRepresentation and the trace.

The M2.2 formats (``meaning-card-doc/1.0``, ``q1-meaning-query/1.0``) are kept as
``*_v1`` LEGACY functions only to reproduce the M2.2 run and the M2.3 diagnosis.

Any change to a format must bump its version: version and text hash are part of
the embedding-cache identity, and ``MEANING_SPEC_ID`` separates cache namespaces.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from navigator.corpus.readiness import meaning_inputs, retrieval_universe, structure_inputs
from navigator.models.fragment import Fragment
from navigator.models.query import QueryRepresentation
from navigator.models.vocabularies import TENSION_QUALIFIER

MEANING_SPEC_ID = "meaning-v2"
MEANING_CARD_DOC_VERSION = "meaning-card-doc/2.0"
Q0_QUERY_VERSION = "q0-question-only/1.0"
Q1_QUERY_VERSION = "q1-meaning-query/2.0"

# LEGACY (M2.2) — reproducibility only
MEANING_CARD_DOC_VERSION_V1 = "meaning-card-doc/1.0"
Q1_QUERY_VERSION_V1 = "q1-meaning-query/1.0"


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Representation:
    key: str  # card id or query id
    version: str
    text: str

    @property
    def sha256(self) -> str:
        return text_sha256(self.text)


def _strip_qualifier(tension: str) -> str:
    return tension[: -len(TENSION_QUALIFIER)] if tension.endswith(TENSION_QUALIFIER) else tension


def _meaning_lines(fragment: Fragment) -> list[str]:
    meaning = meaning_inputs(fragment)
    lines: list[str] = [f"Перспектива: {p}" for p in meaning.get("perspective", [])]
    questions = meaning.get("philosophical_questions", [])
    if questions:
        lines.append("Философские вопросы:")
        lines.extend(f"- {q}" for q in questions)
    return lines


def meaning_card_text(fragment: Fragment) -> str:
    """Card MEANING document (meaning-card-doc/2.0): perspective + philosophical_questions."""
    return "\n".join(_meaning_lines(fragment))


def meaning_card_text_v1(fragment: Fragment) -> str:
    """LEGACY M2.2 card document (meaning-card-doc/1.0) incl. coordinates and tensions."""
    structure = structure_inputs(fragment)
    lines = _meaning_lines(fragment)
    if structure.get("coordinates"):
        lines.append("Координаты: " + "; ".join(structure["coordinates"]))
    tensions = [_strip_qualifier(t) for t in structure.get("tensions", [])]
    if tensions:
        lines.append("Напряжения: " + "; ".join(tensions))
    return "\n".join(lines)


def meaning_card_documents(fragments: list[Fragment]) -> list[Representation]:
    """MEANING documents for the retrieval universe only (113), sorted by card id."""
    docs = []
    for f in sorted(retrieval_universe(fragments), key=lambda x: x.id):
        text = meaning_card_text(f)
        if not text:
            raise ValueError(f"{f.id}: empty MEANING document")
        docs.append(Representation(f.id, MEANING_CARD_DOC_VERSION, text))
    return docs


def q0_text(query: QueryRepresentation) -> str:
    return query.confirmed_question


def q1_text(query: QueryRepresentation) -> str:
    """Q1 (q1-meaning-query/2.0): confirmed question + working hypotheses."""
    lines = [f"Вопрос: {query.confirmed_question}", "Рабочие интерпретации:"]
    lines.extend(f"- {h}" for h in query.working_hypotheses)
    return "\n".join(lines)


def q1_text_v1(query: QueryRepresentation) -> str:
    """LEGACY M2.2 Q1 (q1-meaning-query/1.0) incl. canonical and free tensions."""
    lines = [q1_text(query)]
    tensions = [*query.canonical_tensions, *query.free_tensions]
    if tensions:
        lines.append("Смысловые напряжения:")
        lines.extend(f"- {t}" for t in tensions)
    return "\n".join(lines)


def q0_representation(query: QueryRepresentation, query_id: str) -> Representation:
    return Representation(query_id, Q0_QUERY_VERSION, q0_text(query))


def q1_representation(query: QueryRepresentation, query_id: str) -> Representation:
    return Representation(query_id, Q1_QUERY_VERSION, q1_text(query))

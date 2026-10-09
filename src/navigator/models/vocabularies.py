"""Closed and working vocabularies used by the canonical corpus.

Sources of truth:
- coordinates / tensions: TAXONOMY-philosophical-navigator-v1.1.md, §15A
  («Внутренние смысловые координаты retrieval»). Closed vocabulary.
- philosophical_operation: TECHNICAL-DESIGN-retrieval-v0.2.md §4 and
  OPERATION-AUDIT-launch-113-v0.1.md §2 (working dictionary v0.1). Closed for
  this milestone; must not be extended by implementation.
- question_structures: no document defines a closed vocabulary. The set below is
  exactly the set observed in OPERATION-AUDIT-launch-113-v0.1.md §7. It is used
  only to warn about unknown values, never to reject them (retrieval hints,
  not hard classifiers — D16 / invariant 7).
"""

from __future__ import annotations

COORDINATES: frozenset[str] = frozenset(
    {
        "желание",
        "ожидание / представление",
        "выбор / свобода",
        "действие",
        "контроль",
        "долг / ответственность",
        "привязанность",
        "принятие / сопротивление",
        "отношение к другому",
        "отношение к себе",
        "признание",
        "страх / конечность",
        "смысл / цель",
        "принадлежность",
    }
)

TENSIONS: frozenset[str] = frozenset(
    {
        "желание ↔ долг",
        "свобода ↔ привязанность",
        "действие ↔ принятие",
        "собственное желание ↔ признание",
        "отношение к себе ↔ взгляд другого",
        "контроль ↔ конечность",
        "долг перед другим ↔ долг перед собой",
        "ожидание ↔ действительность",
        "достигнутая цель ↔ смысл",
        "принадлежность ↔ свобода",
    }
)

PHILOSOPHICAL_OPERATIONS_V0_1: frozenset[str] = frozenset(
    {
        "REVALUE_GOOD",
        "EXAMINE_DESIRE",
        "DISTINGUISH",
        "CHALLENGE_ASSUMPTION",
        "LIMIT_CONTROL",
        "LIMIT_OBLIGATION",
        "PRESERVE_AGENCY",
        "RELATIONAL_ACCOUNTABILITY",
        "DECOUPLE_RESPONSE",
        "DECOUPLE_ACTION_OUTCOME",
        "HOLD_VALUE_CONFLICT",
        "SHIFT_ATTENTION",
        "ACKNOWLEDGE_FINITUDE",
        "PERSPECTIVE_LIMIT",
        "TRANSFORM_PRACTICE",
        "CHALLENGE_COMPARISON",
    }
)

QUESTION_STRUCTURE_OPEN_MARKER = "open / context-dependent"

QUESTION_STRUCTURES_OBSERVED: frozenset[str] = frozenset(
    {
        "desire↔meaning",
        "self↔other",
        "action↔outcome",
        "suffering↔meaning",
        "recognition↔self-worth",
        "knowledge↔perspective",
        "acceptance↔action",
        "justice↔response",
        "responsibility↔other autonomy",
        "attachment↔freedom",
        "freedom↔belonging",
        "duty↔desire",
        "control↔uncertainty",
        "personal↔institutional agency",
        QUESTION_STRUCTURE_OPEN_MARKER,
    }
)

# Fields that exist only relative to a concrete retrieval run (D02) and must
# never appear inside a canonical Fragment.
FORBIDDEN_RUNTIME_FIELDS: frozenset[str] = frozenset(
    {
        "required_assumption",
        "required_assumption_status",
        "required_unsupported_assumptions",
        "status",
        "candidate_status",
        "strong",
        "possible",
        "reject",
        "relevance",
        "question_relevance",
        "situational_relevance",
        "situational_applicability",
        "narrative_applicability",
        "relevant_to_confirmed_question",
        "supported_by_narrative",
        "source_fidelity",
        "coverage",
        "coverage_contribution",
        "relation_to_selected",
        "relation_to_other_candidates",
        "similarity",
        "embedding_similarity",
        "selection_reason",
        "rejection_reason",
        "personal_link",
    }
)

# Markers of unfinished editorial work that must never be stored as source text.
PLACEHOLDER_MARKERS: tuple[str, ...] = (
    "[FINAL TEXTUAL PASS",
    "зафиксировать по утверждённому реестру",
)

# The 1090 registry and the first-29 recovery source label coordinates/tensions
# in English. TAXONOMY v1.1 (§15A) is the source of truth and is in Russian.
# This is a 1:1 label mapping of the same 14 coordinates / 10 tensions, not a
# re-interpretation; the original English values stay in
# ``technical.registry_reference``. A registry tension may carry the qualifier
# " (potential)", which is preserved as-is after mapping.
COORDINATES_EN_TO_RU: dict[str, str] = {
    "desire": "желание",
    "expectation / representation": "ожидание / представление",
    "choice / freedom": "выбор / свобода",
    "action": "действие",
    "control": "контроль",
    "duty / responsibility": "долг / ответственность",
    "attachment": "привязанность",
    "acceptance / resistance": "принятие / сопротивление",
    "relation to other": "отношение к другому",
    "relation to self": "отношение к себе",
    "recognition": "признание",
    "fear / finitude": "страх / конечность",
    "meaning / goal": "смысл / цель",
    "belonging": "принадлежность",
}

TENSIONS_EN_TO_RU: dict[str, str] = {
    "desire ↔ duty": "желание ↔ долг",
    "freedom ↔ attachment": "свобода ↔ привязанность",
    "action ↔ acceptance": "действие ↔ принятие",
    "own desire ↔ recognition": "собственное желание ↔ признание",
    "relation to self ↔ gaze of other": "отношение к себе ↔ взгляд другого",
    "control ↔ finitude": "контроль ↔ конечность",
    "duty to other ↔ duty to self": "долг перед другим ↔ долг перед собой",
    "expectation ↔ reality": "ожидание ↔ действительность",
    "achieved goal ↔ meaning": "достигнутая цель ↔ смысл",
    "belonging ↔ freedom": "принадлежность ↔ свобода",
}

TENSION_QUALIFIER = " (potential)"

# MVP launch rule (CLAUDE-CODE-M1-CORRECTION-CLOSEOUT-PROMPT.md §1; matches
# CORPUS-LAUNCH-124-operational-status-v2.0.md). Supersedes the earlier
# "124 verified / unresolved = 0" assumption of TECHNICAL-DESIGN v0.2 §0.
LAUNCH_SHORTLIST_COUNT = 124
UNRESOLVED_IDS: frozenset[str] = frozenset(
    {"C0377", "C0396", "C0398", "C0215", "C0230", "C0258", "C0703", "C0704", "C0705", "C0706", "C0707"}
)
RETRIEVAL_VERIFIED_COUNT = LAUNCH_SHORTLIST_COUNT - len(UNRESOLVED_IDS)  # 113

SOURCE_ROUTE_STATUS = "disabled_pending_full_fragment_text"

# Editorial / working notes that must never be treated as philosophical content
# (M1.5). Checked in addition to PLACEHOLDER_MARKERS for MEANING inputs.
EDITORIAL_MARKERS: tuple[str, ...] = (
    *PLACEHOLDER_MARKERS,
    "сильный кандидат",
    "Сохранять притчу",
    "high_context_required",
    "Флаг:",
)

"""Canonical Fragment schema (TECHNICAL-DESIGN-retrieval-v0.2 §4, D01/D02/D45).

The Pydantic model enforces *shape and types* only. Every content field that the
approved sources may lack is Optional: ``None`` means "absent in the accessible
sources", never "empty by decision". Completeness, vocabularies and cross-record
rules are enforced by ``navigator.corpus.validator`` so that a gap is reported
as a gap instead of making the corpus unloadable.

``extra="forbid"`` on every model keeps run-specific judgments (D02) and any
undeclared field out of the canonical record.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr

FragmentId = Annotated[str, Field(pattern=r"^C\d{4}$")]
NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]

SCHEMA_VERSION = "fragment-schema/0.2.0"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Relations(_Strict):
    contrasts_with: list[FragmentId] = Field(default_factory=list)
    resonates_with: list[FragmentId] = Field(default_factory=list)
    complicates: list[FragmentId] = Field(default_factory=list)


class RegistryReference(_Strict):
    """Row of CORPUS-FULL-1090-v1.md kept for traceability only.

    These values are pre-launch working-registry data. They are NOT canonical
    launch content and are not used to fill any canonical field.
    """

    status: NonEmptyStr
    decision: NonEmptyStr
    author_speaker: StrictStr | None = None
    work: StrictStr | None = None
    location: StrictStr | None = None
    philosophical_move: StrictStr | None = None
    perspective: StrictStr | None = None
    coordinates_en: list[NonEmptyStr] = Field(default_factory=list)
    tensions_en: list[NonEmptyStr] = Field(default_factory=list)


class FragmentTechnical(_Strict):
    """Existing source/technical metadata of the launch corpus plus import provenance."""

    # "launch" = the 124 launch corpus (data/corpus); "restored_registry" = a CORPUS-FULL-1090 row restored into the
    # full corpus (data/corpus-full) without a textual pass.
    # "final_2026_10_07" = a row of corpus/final-2026-10-07/FINAL-CORPUS-ACTIVE-v1.csv (navigator.corpus.final_corpus).
    corpus_status: Literal["launch", "restored_registry", "final_2026_10_07"] = "launch"
    # MVP rule: 113 verified / 11 unresolved (CLAUDE-CODE-M1-CORRECTION-CLOSEOUT-PROMPT §1).
    # Unresolved Fragments are kept for history/audit but never enter retrieval.
    # Full corpus (restored registry rows): "registry_curated" = main row with a philosophical move + perspective
    # (retrieval-eligible); "registry_reserve" = reserve row whose perspective is only a registry placeholder
    # (stored, not retrieval-eligible until it has project-sourced meaning).
    operational_status: Literal["verified", "unresolved", "registry_curated", "registry_reserve", "final_active"]
    retrieval_eligible: StrictBool
    operational_status_basis: NonEmptyStr = "CLAUDE-CODE-M1-CORRECTION-CLOSEOUT-PROMPT.md §1"

    # First-29 recovery provenance (CORPUS-LAUNCH-FIRST-29-recovery-source-v0.2.md).
    # None for Fragments that have a textual-pass card.
    recovery_status: StrictStr | None = None
    recovery_batch: StrictStr | None = None
    old_yaml_status: StrictStr | None = None

    launch_philosophical_move: StrictStr | None = None
    launch_location: StrictStr | None = None
    speaker: StrictStr | None = None
    fragment_storage_status: StrictStr | None = None
    verification_flags: list[NonEmptyStr] | None = None

    # Editorial placeholders removed from content fields (they are instructions,
    # not source text), preserved verbatim so nothing is lost.
    thought_placeholder: StrictStr | None = None
    translation_placeholder: StrictStr | None = None

    has_textual_pass_card: StrictBool
    in_operation_audit_113: StrictBool
    historical_unresolved_status_v2_0: StrictBool
    historical_unresolved_textual_pass: StrictBool

    field_provenance: dict[NonEmptyStr, NonEmptyStr] = Field(default_factory=dict)
    # Curation layer (data/corpus/curation/*.json): field → note, incl. any replaced value.
    curation: dict[NonEmptyStr, NonEmptyStr] | None = None
    registry_reference: RegistryReference | None = None


class Fragment(_Strict):
    # SOURCE
    id: FragmentId
    tradition: NonEmptyStr | None = None
    author: NonEmptyStr | None = None
    work: NonEmptyStr | None = None
    location: NonEmptyStr | None = None

    # TEXT
    fragment: NonEmptyStr | None = None
    thought: NonEmptyStr | None = None
    context: NonEmptyStr | None = None
    commentary: NonEmptyStr | None = None

    # MEANING
    philosophical_questions: list[NonEmptyStr] | None = None
    coordinates: list[NonEmptyStr] | None = None
    tensions: list[NonEmptyStr] | None = None
    perspective: NonEmptyStr | None = None

    # OPERATION-AWARE RETRIEVAL LAYER
    philosophical_operation: NonEmptyStr | None = None
    question_structures: list[NonEmptyStr] | None = None

    # RELATIONS
    relations: Relations | None = None

    # VERIFICATION / SOURCE METADATA
    translation: NonEmptyStr | None = None
    source: NonEmptyStr | None = None
    copyright_status: NonEmptyStr | None = None
    source_verified: StrictBool | None = None
    interpretation_verified: StrictBool | None = None

    technical: FragmentTechnical


# Field policy after the M1 correction (CLOSEOUT-PROMPT §4–§7):
#
# BLOCKING_IDENTITY — source identity; absence is a blocking error for every Fragment.
# BLOCKING_RETRIEVAL — STRUCTURE-route metadata; blocking only for retrieval-eligible
#   (verified) Fragments. Excluded unresolved Fragments may lack it.
# CONTENT_FIELDS — completeness of the card. Absence is a non-blocking gap
#   (CONTENT_GAP, or RECOVERY_GAP for the first 29), never filled by guesses.
# ``fragment`` is reported separately: SOURCE route is disabled pending full text.
# ``author`` is optional by CORPUS v0.1 («если применимо»); ``relations`` are
# optional for MVP. ``tensions`` may legitimately be an empty list.
BLOCKING_IDENTITY: tuple[str, ...] = ("tradition", "work", "location")
BLOCKING_RETRIEVAL: tuple[str, ...] = ("philosophical_operation", "question_structures")

CONTENT_FIELDS: dict[str, tuple[str, ...]] = {
    "TEXT": ("thought", "context", "commentary"),
    "MEANING": ("philosophical_questions", "coordinates", "tensions", "perspective"),
    "VERIFICATION": (
        "translation",
        "source",
        "copyright_status",
        "source_verified",
        "interpretation_verified",
    ),
}

# Inputs of the derived semantic representations (TECHNICAL-DESIGN §7–§9).
MEANING_ROUTE_FIELDS: tuple[str, ...] = ("thought", "philosophical_questions", "perspective")
STRUCTURE_ROUTE_FIELDS: tuple[str, ...] = ("coordinates", "tensions", "question_structures", "philosophical_operation")

EMPTY_LIST_ALLOWED: frozenset[str] = frozenset({"tensions"})

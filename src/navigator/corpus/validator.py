"""Canonical corpus validator (TECHNICAL-DESIGN-retrieval-v0.2 D49, corrected by
CLAUDE-CODE-M1-CORRECTION-CLOSEOUT-PROMPT.md).

Severities:
- ``error``   — schema / integrity / allowlist failure. Any error blocks index
                build (D49, hard invariant 34).
- ``warning`` — non-blocking gap or issue that needs a human decision.
- ``info``    — descriptive observation.

Launch rule: shortlist 124 = 113 verified (retrieval allowlist) + 11 unresolved
(kept for audit, never retrievable). Missing full ``fragment`` text is a warning:
the SOURCE route is disabled pending full text. Missing card content is a
non-blocking CONTENT_GAP / RECOVERY_GAP, never filled by guesses.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pydantic import ValidationError

from navigator.models.fragment import (
    BLOCKING_IDENTITY,
    BLOCKING_RETRIEVAL,
    CONTENT_FIELDS,
    EMPTY_LIST_ALLOWED,
    MEANING_ROUTE_FIELDS,
    SCHEMA_VERSION,
    STRUCTURE_ROUTE_FIELDS,
    Fragment,
)
from navigator.corpus.readiness import (
    generic_questions,
    is_editorial,
    meaning_readiness,
    retrieval_universe,
    structure_ready,
)
from navigator.models.vocabularies import (
    COORDINATES,
    FORBIDDEN_RUNTIME_FIELDS,
    LAUNCH_SHORTLIST_COUNT,
    PHILOSOPHICAL_OPERATIONS_V0_1,
    PLACEHOLDER_MARKERS,
    QUESTION_STRUCTURE_OPEN_MARKER,
    QUESTION_STRUCTURES_OBSERVED,
    SOURCE_ROUTE_STATUS,
    TENSION_QUALIFIER,
    TENSIONS,
    UNRESOLVED_IDS,
)

VALIDATOR_VERSION = "corpus-validator/0.3.0"
EXPECTED_COUNT = LAUNCH_SHORTLIST_COUNT
_QS_RE = re.compile(r"^[^↔;]+↔[^↔;]+$")
_TEXT_FIELDS = ("fragment", "thought", "context", "commentary", "perspective", "translation", "source")
_TEMPLATE_PREFIXES = {
    "context": "Launch-кандидат фиксирует следующий исходный ход:",
    "commentary": "Рабочее прочтение следует непосредственно за этим ходом:",
    "perspective": "Рассмотреть ситуацию через операцию, которую задаёт сам фрагмент:",
}


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    fragment_id: str | None = None
    field: str | None = None
    line: int | None = None


@dataclass
class ValidationResult:
    issues: list[Issue]
    fragments: list[Fragment]
    expected_count: int
    actual_count: int
    expected_unresolved: frozenset[str]
    allowlist: list[str] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def codes(self, severity: str | None = None) -> set[str]:
        return {i.code for i in self.issues if severity is None or i.severity == severity}


def _is_missing(value, field: str) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, list) and not value and field not in EMPTY_LIST_ALLOWED:
        return True
    return False


def validate_records(
    records: list[tuple[int, dict]],
    expected_count: int = EXPECTED_COUNT,
    expected_ids: list[str] | None = None,
    expected_unresolved: frozenset[str] = UNRESOLVED_IDS,
    manifest_unresolved: list[str] | None = None,
    manifest_allowlist: list[str] | None = None,
) -> ValidationResult:
    """Validate already-parsed JSON records (line number, object).

    ``expected_unresolved`` is the authoritative unresolved set (the 11 of the
    closeout rule by default). ``manifest_*`` are checked against it and against
    the records when a manifest is available.
    """
    issues: list[Issue] = []

    def add(sev, code, msg, fid=None, field=None, line=None):
        issues.append(Issue(sev, code, msg, fid, field, line))

    # ---- per-record: forbidden run-specific fields, then shape/types
    fragments: list[Fragment] = []
    raw_ids: list[tuple[int, str | None]] = []
    for line, obj in records:
        fid = obj.get("id") if isinstance(obj, dict) else None
        raw_ids.append((line, fid if isinstance(fid, str) else None))
        if not isinstance(obj, dict):
            add("error", "SCHEMA_TYPE", "record is not a JSON object", line=line)
            continue
        technical = obj.get("technical") if isinstance(obj.get("technical"), dict) else {}
        for scope, keys in (("", obj.keys()), ("technical.", technical.keys())):
            for key in sorted(set(keys) & FORBIDDEN_RUNTIME_FIELDS):
                add(
                    "error",
                    "FORBIDDEN_RUNTIME_FIELD",
                    f"run-specific field '{scope}{key}' must not be stored in a canonical Fragment (D02)",
                    fid,
                    scope + key,
                    line,
                )
        try:
            fragments.append(Fragment.model_validate(obj))
        except ValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(p) for p in err["loc"])
                code = "UNKNOWN_FIELD" if err["type"] == "extra_forbidden" else "SCHEMA_TYPE"
                if code == "UNKNOWN_FIELD" and err["loc"] and str(err["loc"][-1]) in FORBIDDEN_RUNTIME_FIELDS:
                    continue  # already reported as FORBIDDEN_RUNTIME_FIELD
                if loc.startswith("question_structures"):
                    code = "MALFORMED_QUESTION_STRUCTURES"
                add("error", code, f"{loc}: {err['msg']}", fid, loc, line)

    # ---- count and IDs
    if len(records) != expected_count:
        add("error", "COUNT_MISMATCH", f"expected {expected_count} launch Fragment records, found {len(records)}")

    id_lines: dict[str, list[int]] = defaultdict(list)
    for line, fid in raw_ids:
        if fid is None:
            add("error", "MISSING_ID", "record has no string 'id'", line=line)
        else:
            id_lines[fid].append(line)
    for fid, lines in sorted(id_lines.items()):
        if len(lines) > 1:
            add("error", "DUPLICATE_ID", f"ID {fid} occurs on lines {lines}", fid, "id")

    if expected_ids is not None:
        present = set(id_lines)
        for fid in sorted(set(expected_ids) - present):
            add("error", "MISSING_EXPECTED_ID", f"launch ID {fid} is absent from the corpus", fid, "id")
        for fid in sorted(present - set(expected_ids)):
            add("error", "UNEXPECTED_ID", f"ID {fid} is not part of the launch manifest", fid, "id")

    known_ids = set(id_lines)

    # ---- 113 / 11 rule
    for fid in sorted(expected_unresolved - known_ids):
        add("error", "UNRESOLVED_ID_MISSING", f"unresolved {fid} must stay in the corpus for audit", fid, "id")
    for f in fragments:
        should_be_unresolved = f.id in expected_unresolved
        status = f.technical.operational_status
        if should_be_unresolved and status != "unresolved":
            add("error", "OPERATIONAL_STATUS_MISMATCH", f"{f.id} must be 'unresolved', found '{status}'", f.id, "technical.operational_status")
        if not should_be_unresolved and status != "verified":
            add("error", "OPERATIONAL_STATUS_MISMATCH", f"{f.id} is not in the unresolved set but has status '{status}'", f.id, "technical.operational_status")
        if f.technical.retrieval_eligible != (status == "verified"):
            add(
                "error",
                "RETRIEVAL_ELIGIBILITY_MISMATCH",
                f"retrieval_eligible={f.technical.retrieval_eligible} contradicts operational_status='{status}'",
                f.id,
                "technical.retrieval_eligible",
            )
        if f.technical.retrieval_eligible and should_be_unresolved:
            add("error", "UNRESOLVED_IN_ALLOWLIST", f"unresolved {f.id} is marked retrieval-eligible", f.id, "technical.retrieval_eligible")

    # What the records claim is retrievable; a leaked unresolved shows up here and in the count.
    allowlist = [f.id for f in fragments if f.technical.retrieval_eligible]
    expected_verified = expected_count - len(expected_unresolved)
    if len(set(allowlist)) != expected_verified:
        add("error", "VERIFIED_COUNT_MISMATCH", f"retrieval universe has {len(set(allowlist))} Fragment, expected {expected_verified}")

    if manifest_unresolved is not None and set(manifest_unresolved) != set(expected_unresolved):
        add(
            "error",
            "UNRESOLVED_SET_MISMATCH",
            f"manifest unresolved {sorted(manifest_unresolved)} ≠ required {sorted(expected_unresolved)}",
        )
    if manifest_allowlist is not None:
        leaked = sorted(set(manifest_allowlist) & set(expected_unresolved))
        if leaked:
            add("error", "UNRESOLVED_IN_ALLOWLIST", f"manifest retrieval_allowlist contains unresolved {leaked}")
        if len(manifest_allowlist) != len(set(manifest_allowlist)):
            add("error", "ALLOWLIST_MISMATCH", "manifest retrieval_allowlist contains duplicates")
        if set(manifest_allowlist) != set(allowlist):
            add(
                "error",
                "ALLOWLIST_MISMATCH",
                f"manifest retrieval_allowlist differs from records: "
                f"only in manifest {sorted(set(manifest_allowlist) - set(allowlist))}, "
                f"only in records {sorted(set(allowlist) - set(manifest_allowlist))}",
            )

    # ---- per-fragment content rules
    generic = generic_questions(retrieval_universe(fragments))
    for f in fragments:
        eligible = f.technical.retrieval_eligible
        recovery = f.technical.recovery_status is not None

        for field in BLOCKING_IDENTITY:
            if _is_missing(getattr(f, field), field):
                add("error", "MISSING_SOURCE_IDENTITY", f"SOURCE.{field} is absent", f.id, field)

        for field in BLOCKING_RETRIEVAL:
            if _is_missing(getattr(f, field), field):
                if eligible:
                    add("error", "RETRIEVAL_METADATA_MISSING", f"retrieval-eligible Fragment lacks {field} (STRUCTURE route)", f.id, field)
                else:
                    add("info", "EXCLUDED_UNRESOLVED_NO_OPERATION", f"{field} absent; Fragment is excluded from retrieval", f.id, field)

        for layer, fields in CONTENT_FIELDS.items():
            for field in fields:
                if _is_missing(getattr(f, field), field):
                    add(
                        "warning",
                        "RECOVERY_GAP" if recovery else "CONTENT_GAP",
                        f"{layer}.{field} is absent" + (" (first-29 recovery)" if recovery else ""),
                        f.id,
                        field,
                    )

        if f.fragment is None:
            add("warning", "FRAGMENT_TEXT_ABSENT", f"full fragment text absent; SOURCE route {SOURCE_ROUTE_STATUS}", f.id, "fragment")

        if eligible:
            mr = meaning_readiness(f, generic)
            if not mr.usable:
                add(
                    "error",
                    "MEANING_NOT_READY",
                    f"MEANING representation input is {mr.state} (thought / philosophical_questions / perspective)",
                    f.id,
                )
            elif mr.state == "THIN":
                add("warning", "MEANING_THIN", f"only {mr.specific_words} specific content words in MEANING input", f.id)
            if not structure_ready(f):
                add("error", "STRUCTURE_NOT_READY", "needs a valid operation, ≥1 question_structure and ≥1 coordinate", f.id)
            for field in ("thought", "perspective"):
                if is_editorial(getattr(f, field)):
                    add("error", "EDITORIAL_TEXT_IN_MEANING", f"{field} holds an editorial note, not philosophical content", f.id, field)
            for q in f.philosophical_questions or []:
                if is_editorial(q):
                    add("error", "EDITORIAL_TEXT_IN_MEANING", "philosophical_questions item holds an editorial note", f.id, "philosophical_questions")

        templated = [k for k, p in _TEMPLATE_PREFIXES.items() if (getattr(f, k) or "").startswith(p)]
        if templated:
            add("warning", "TEMPLATED_INTERPRETATION", f"templated semantic fields: {', '.join(templated)}", f.id)

        for field in _TEXT_FIELDS:
            value = getattr(f, field)
            if isinstance(value, str) and any(m in value for m in PLACEHOLDER_MARKERS):
                add("error", "PLACEHOLDER_TEXT", f"{field} contains an editorial placeholder, not source text", f.id, field)

        for value in f.coordinates or []:
            if value not in COORDINATES:
                add("error", "INVALID_TAXONOMY_VALUE", f"coordinate «{value}» is not in TAXONOMY v1.1", f.id, "coordinates")
        for dup in [v for v, n in Counter(f.coordinates or []).items() if n > 1]:
            add("warning", "DUPLICATE_VALUE", f"coordinate «{dup}» repeated", f.id, "coordinates")

        for value in f.tensions or []:
            base = value[: -len(TENSION_QUALIFIER)] if value.endswith(TENSION_QUALIFIER) else value
            if base not in TENSIONS:
                add("error", "INVALID_TAXONOMY_VALUE", f"tension «{value}» is not in TAXONOMY v1.1", f.id, "tensions")

        op = f.philosophical_operation
        if op is not None and op not in PHILOSOPHICAL_OPERATIONS_V0_1:
            add(
                "error",
                "INVALID_OPERATION",
                f"philosophical_operation «{op}» is not in the working dictionary v0.1",
                f.id,
                "philosophical_operation",
            )

        qs = f.question_structures
        if qs is not None:
            for value in qs:
                if value != QUESTION_STRUCTURE_OPEN_MARKER and not _QS_RE.match(value):
                    add(
                        "error",
                        "MALFORMED_QUESTION_STRUCTURES",
                        f"question_structure «{value}» is neither 'A↔B' nor «{QUESTION_STRUCTURE_OPEN_MARKER}»",
                        f.id,
                        "question_structures",
                    )
                elif value not in QUESTION_STRUCTURES_OBSERVED:
                    add(
                        "warning",
                        "UNKNOWN_QUESTION_STRUCTURE",
                        f"question_structure «{value}» is not in the set observed in OPERATION-AUDIT (soft vocabulary)",
                        f.id,
                        "question_structures",
                    )
            if len(set(qs)) != len(qs):
                add("error", "MALFORMED_QUESTION_STRUCTURES", "question_structures contains duplicates", f.id, "question_structures")
            if QUESTION_STRUCTURE_OPEN_MARKER in qs and len(qs) > 1:
                add(
                    "warning",
                    "OPEN_MARKER_MIXED",
                    f"«{QUESTION_STRUCTURE_OPEN_MARKER}» is combined with concrete structures",
                    f.id,
                    "question_structures",
                )

        if f.relations is None:
            add("info", "RELATIONS_UNAVAILABLE", "relations absent (not required for MVP)", f.id, "relations")
        else:
            for rel_type in ("contrasts_with", "resonates_with", "complicates"):
                for target in getattr(f.relations, rel_type):
                    if target == f.id:
                        add("error", "SELF_RELATION", f"{rel_type} points to the Fragment itself", f.id, f"relations.{rel_type}")
                    elif target not in known_ids:
                        add("error", "BROKEN_RELATION", f"{rel_type} → {target} does not exist in the corpus", f.id, f"relations.{rel_type}")

        if eligible and (f.source_verified is False or f.interpretation_verified is False):
            add(
                "warning",
                "CARD_VERIFICATION_FLAG_FALSE",
                f"verified Fragment has card-level source_verified={f.source_verified}, "
                f"interpretation_verified={f.interpretation_verified}",
                f.id,
                "source_verified",
            )
        if f.copyright_status and f.copyright_status.startswith("check"):
            add("info", "COPYRIGHT_PENDING", f"copyright_status is a pending check: «{f.copyright_status}»", f.id, "copyright_status")
        if f.technical.thought_placeholder:
            add("info", "THOUGHT_PLACEHOLDER_PRESERVED", "textual-pass Thought placeholder preserved in technical.thought_placeholder", f.id, "thought")
        if f.technical.translation_placeholder:
            add("info", "TRANSLATION_PLACEHOLDER_PRESERVED", "translation placeholder preserved in technical.translation_placeholder", f.id, "translation")

    return ValidationResult(
        issues=issues,
        fragments=fragments,
        expected_count=expected_count,
        actual_count=len(records),
        expected_unresolved=frozenset(expected_unresolved),
        allowlist=allowlist,
    )


def load_jsonl(path: Path) -> tuple[list[tuple[int, dict]], list[Issue]]:
    records, issues = [], []
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            records.append((n, json.loads(raw)))
        except json.JSONDecodeError as exc:
            issues.append(Issue("error", "JSON_PARSE", f"line {n}: {exc.msg}", line=n))
    return records, issues


def validate_corpus_file(
    corpus_path: Path,
    manifest_path: Path | None = None,
    expected_count: int = EXPECTED_COUNT,
    expected_unresolved: frozenset[str] = UNRESOLVED_IDS,
) -> ValidationResult:
    records, parse_issues = load_jsonl(corpus_path)
    expected_ids = manifest_unresolved = manifest_allowlist = None
    if manifest_path and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_ids = manifest.get("launch_ids")
        expected_count = manifest.get("expected_count", expected_count)
        manifest_unresolved = manifest.get("unresolved_ids")
        manifest_allowlist = manifest.get("retrieval_allowlist")
    result = validate_records(
        records, expected_count, expected_ids, expected_unresolved, manifest_unresolved, manifest_allowlist
    )
    result.issues[:0] = parse_issues
    return result


# --------------------------------------------------------------------------- summary


def summarize(result: ValidationResult, corpus_path: Path, manifest: dict | None = None) -> dict:
    frags = result.fragments
    eligible = [f for f in frags if f.technical.retrieval_eligible]

    def coverage_of(population: list[Fragment], fields) -> dict:
        return {
            f_: {
                "present": sum(1 for x in population if not _is_missing(getattr(x, f_), f_)),
                "missing": sum(1 for x in population if _is_missing(getattr(x, f_), f_)),
            }
            for f_ in fields
        }

    all_fields = ["fragment", *BLOCKING_IDENTITY, *BLOCKING_RETRIEVAL, *(f for fs in CONTENT_FIELDS.values() for f in fs)]

    gaps: dict[str, dict[str, list[str]]] = {}
    for i in result.issues:
        if i.code in {"CONTENT_GAP", "RECOVERY_GAP"} and i.fragment_id:
            gaps.setdefault(i.fragment_id, {}).setdefault(i.code, []).append(i.field or "")

    recovery = {
        f.id: {
            "batch": f.technical.recovery_batch,
            "recovery_status": f.technical.recovery_status,
            "retrieval_eligible": f.technical.retrieval_eligible,
            "reconstructed_fields": (
                ["work", "location", "perspective", "coordinates", "tensions"]
                if f.technical.field_provenance.get("MEANING", "").startswith("RECONSTRUCTED")
                else []
            ),
            "gaps": gaps.get(f.id, {}).get("RECOVERY_GAP", []),
        }
        for f in frags
        if f.technical.recovery_status is not None
    }

    unresolved_present = sorted(f.id for f in frags if f.technical.operational_status == "unresolved")
    return {
        "validator_version": VALIDATOR_VERSION,
        "schema_version": SCHEMA_VERSION,
        "corpus_path": str(corpus_path),
        "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest() if corpus_path.exists() else None,
        "corpus_version": (manifest or {}).get("corpus_version"),
        "status": "PASS" if result.ok else "FAIL",
        "index_build_allowed": result.ok,
        "blocking_codes": sorted({i.code for i in result.errors}),
        "launch": {
            "launch_shortlist_count": result.actual_count,
            "expected_launch_shortlist_count": result.expected_count,
            "retrieval_verified_count": len(result.allowlist),
            "unresolved_count": len(unresolved_present),
            "unresolved_ids": unresolved_present,
            "unresolved_set_matches_rule": set(unresolved_present) == set(result.expected_unresolved),
            "unresolved_in_retrieval_universe": sorted(set(result.allowlist) & set(result.expected_unresolved)),
            "retrieval_universe": result.allowlist,
        },
        "counts": {
            "records": result.actual_count,
            "schema_valid": len(frags),
            "unique_ids": len({f.id for f in frags}),
        },
        "routes": {
            "SOURCE": {"status": SOURCE_ROUTE_STATUS, "fragments_with_full_text": sum(1 for f in frags if f.fragment)},
            "MEANING": {
                "status": "enabled",
                "eligible_with_all_inputs": sum(1 for f in eligible if all(not _is_missing(getattr(f, x), x) for x in MEANING_ROUTE_FIELDS)),
                "eligible_with_no_inputs": sorted(f.id for f in eligible if all(_is_missing(getattr(f, x), x) for x in MEANING_ROUTE_FIELDS)),
                "field_coverage_eligible": coverage_of(eligible, MEANING_ROUTE_FIELDS),
            },
            "STRUCTURE": {
                "status": "enabled",
                "eligible_with_all_inputs": sum(1 for f in eligible if all(not _is_missing(getattr(f, x), x) for x in STRUCTURE_ROUTE_FIELDS)),
                "field_coverage_eligible": coverage_of(eligible, STRUCTURE_ROUTE_FIELDS),
            },
        },
        "readiness": _readiness_summary(frags),
        "issue_summary": {
            sev: dict(Counter(i.code for i in result.issues if i.severity == sev)) for sev in ("error", "warning", "info")
        },
        "field_coverage": {"all_124": coverage_of(frags, all_fields), "retrieval_113": coverage_of(eligible, all_fields)},
        "operation_layer": {
            "eligible_with_philosophical_operation": sum(1 for f in eligible if f.philosophical_operation),
            "eligible_with_question_structures": sum(1 for f in eligible if f.question_structures),
            "unresolved_without_operation": sorted(f.id for f in frags if not f.technical.retrieval_eligible and not f.philosophical_operation),
            "operation_counts": dict(Counter(f.philosophical_operation for f in eligible if f.philosophical_operation).most_common()),
        },
        "first_29_recovery": recovery,
        "fragments_with_content_gaps": dict(sorted(gaps.items())),
        "issues": [asdict(i) for i in result.issues],
    }


def _readiness_summary(frags: list[Fragment]) -> dict:
    universe = retrieval_universe(frags)
    generic = generic_questions(universe)
    states = {f.id: meaning_readiness(f, generic) for f in universe}
    return {
        "retrieval_universe_count": len(universe),
        "meaning_states": dict(Counter(r.state for r in states.values())),
        "meaning_not_usable": sorted(k for k, r in states.items() if not r.usable),
        "meaning_thin": sorted(k for k, r in states.items() if r.state == "THIN"),
        "meaning_without_thought": sorted(k for k, r in states.items() if not r.has_thought),
        "structure_ready": sum(1 for f in universe if structure_ready(f)),
        "structure_not_ready": sorted(f.id for f in universe if not structure_ready(f)),
        "generic_questions": sorted(generic),
    }

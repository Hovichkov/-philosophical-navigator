"""Validator of the machine-readable M2.1 benchmark.

Checks structure and spec fidelity only. Expected structures are guidance: the
validator checks that their vocabulary is well-formed, never that future
retrieval reproduces them.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from pydantic import ValidationError

from navigator.benchmark.build import BENCHMARK_JSON, build_benchmark
from navigator.benchmark.source_md import BENCHMARK_MD
from navigator.corpus.sources import sha256
from navigator.models.benchmark import EVALUATION_DIMENSIONS, FAILURE_CATEGORIES, Benchmark, TensionRef
from navigator.models.vocabularies import COORDINATES, TENSIONS, UNRESOLVED_IDS

BENCHMARK_VALIDATOR_VERSION = "benchmark-validator/0.1.0"
EXPECTED_CASES = [f"B{i:02d}" for i in range(1, 21)]
EXPECTED_PAIRS = ["CP1", "CP2", "CP3", "CP4"]

_CARD_ID_RE = re.compile(r"\bC\d{4}\b")
_TENSION_RE = re.compile(r"^[^↔]+ ↔ [^↔]+$")
# Tradition / school labels used in the launch corpus. The benchmark must not require any.
TRADITION_MARKERS = (
    "стоиц", "буддиз", "буддий", "даос", "конфуци", "христиан", "ислам", "иудаи", "иудей",
    "индуи", "веданта", "эпикур", "библейск", "платон", "сократ", "эпиктет", "будда", "коран",
)


@dataclass(frozen=True)
class BenchmarkIssue:
    severity: str
    code: str
    message: str
    item: str | None = None


def _check_tension(t: TensionRef, where: str, issues: list[BenchmarkIssue]) -> None:
    if not _TENSION_RE.match(t.text):
        issues.append(BenchmarkIssue("error", "TENSION_FORMAT", f"«{t.text}» is not in the 'A ↔ B' convention", where))
        return
    left, right = (p.strip() for p in t.text.split("↔", 1))
    reversed_text = f"{right} ↔ {left}"
    expected = (
        ("exact", t.text) if t.text in TENSIONS
        else ("reversed_poles", reversed_text) if reversed_text in TENSIONS
        else ("case_specific", None)
    )
    if (t.match, t.taxonomy_tension) != expected:
        issues.append(
            BenchmarkIssue(
                "error",
                "TENSION_MATCH_INCONSISTENT",
                f"«{t.text}» marked {t.match}/{t.taxonomy_tension}, TAXONOMY v1.1 gives {expected[0]}/{expected[1]}",
                where,
            )
        )


def validate_benchmark_data(data: dict, root: Path | None = None) -> tuple[list[BenchmarkIssue], Benchmark | None]:
    issues: list[BenchmarkIssue] = []

    def add(sev, code, msg, item=None):
        issues.append(BenchmarkIssue(sev, code, msg, item))

    # ---- mandatory card IDs / unresolved / required traditions (whole document scan)
    dump = json.dumps(data, ensure_ascii=False)
    card_ids = sorted(set(_CARD_ID_RE.findall(dump)))
    if card_ids:
        add("error", "CARD_ID_PRESENT", f"benchmark must not name card IDs: {card_ids}")
    if set(card_ids) & UNRESOLVED_IDS:
        add("error", "UNRESOLVED_REFERENCED", f"unresolved cards referenced: {sorted(set(card_ids) & UNRESOLVED_IDS)}")
    lowered = dump.lower()
    traditions = sorted({m for m in TRADITION_MARKERS if m in lowered})
    if traditions:
        add("error", "TRADITION_OR_AUTHOR_REQUIRED", f"benchmark names specific traditions/authors: {traditions}")

    try:
        bench = Benchmark.model_validate(data)
    except ValidationError as exc:
        for err in exc.errors():
            code = "FORBIDDEN_FIELD" if err["type"] == "extra_forbidden" else "SCHEMA"
            add("error", code, f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}")
        return issues, None

    # ---- cases
    ids = [c.id for c in bench.cases]
    if len(ids) != 20:
        add("error", "CASE_COUNT", f"expected 20 main cases, found {len(ids)}")
    for dup in sorted(k for k, n in Counter(ids).items() if n > 1):
        add("error", "DUPLICATE_CASE_ID", f"case ID {dup} is not unique", dup)
    if ids != EXPECTED_CASES and len(ids) == 20 and len(set(ids)) == 20:
        add("error", "CASE_IDS_UNSTABLE", f"case IDs must be B01…B20 in order, found {ids}")

    for c in bench.cases:
        for coord in c.expected_structure.probable_coordinates:
            if coord not in COORDINATES:
                add("error", "COORDINATE_NOT_CANONICAL", f"«{coord}» is not a TAXONOMY v1.1 coordinate", c.id)
        for t in c.expected_structure.probable_tensions:
            _check_tension(t, c.id, issues)

    covered = {x for c in bench.cases for x in c.expected_structure.probable_coordinates}
    missing = sorted(COORDINATES - covered)
    if missing:
        add("warning", "COORDINATE_COVERAGE", f"main cases do not cover coordinates: {missing}")

    # ---- contrast pairs
    pair_ids = [p.id for p in bench.contrast_pairs]
    if pair_ids != EXPECTED_PAIRS:
        add("error", "CONTRAST_PAIRS", f"expected contrast pairs {EXPECTED_PAIRS}, found {pair_ids}")
    case_set = set(ids)
    for p in bench.contrast_pairs:
        for v, side in ((p.variant_a, "A"), (p.variant_b, "B")):
            if v.id != f"{p.id}-{side}":
                add("error", "VARIANT_ID", f"variant {v.id} does not belong to {p.id}-{side}", p.id)
            if v.case_ref is not None and v.case_ref not in case_set:
                add("error", "BROKEN_CASE_REFERENCE", f"{v.id} references unknown case {v.case_ref}", p.id)
            for coord in v.probable_coordinates:
                if coord not in COORDINATES:
                    add("error", "COORDINATE_NOT_CANONICAL", f"«{coord}» is not a TAXONOMY v1.1 coordinate", v.id)
            for t in v.probable_tensions:
                _check_tension(t, v.id, issues)
        if p.variant_a.narrative and p.variant_b.narrative and p.variant_a.narrative == p.variant_b.narrative:
            add("error", "CONTRAST_NOT_CONTRASTING", "both variants carry the same narrative", p.id)

    # ---- evaluation / failure taxonomy / routes
    if bench.evaluation.scale != [0, 1, 2]:
        add("error", "EVALUATION_SCALE", f"scale must be [0, 1, 2], found {bench.evaluation.scale}")
    dims = [d.id for d in bench.evaluation.card_level_dimensions]
    if dims != list(EVALUATION_DIMENSIONS):
        add("error", "EVALUATION_DIMENSIONS", f"dimensions must be {list(EVALUATION_DIMENSIONS)}, found {dims}")
    for d in bench.evaluation.card_level_dimensions:
        if [lv.score for lv in d.levels] != [0, 1, 2]:
            add("error", "EVALUATION_LEVELS", f"{d.id} must define levels 0, 1, 2", d.id)
    if [f.id for f in bench.failure_taxonomy] != list(FAILURE_CATEGORIES):
        add("error", "FAILURE_TAXONOMY", f"failure categories must be {list(FAILURE_CATEGORIES)}")
    if "SOURCE" in bench.required_routes or bench.source_route_required:
        add("error", "SOURCE_REQUIRED", "benchmark must not require the SOURCE route")

    # ---- fidelity to the canonical Markdown spec
    if root is not None and (root / BENCHMARK_MD).exists():
        if bench.spec_sha256 != sha256(root / BENCHMARK_MD):
            add("error", "SPEC_DRIFT", "spec_sha256 differs from the canonical Markdown; rebuild the benchmark")
        elif build_benchmark(root).model_dump(mode="json") != bench.model_dump(mode="json"):
            add("error", "SPEC_DRIFT", "machine-readable benchmark differs from a fresh transcription of the spec")

    case_specific = sum(
        1 for c in bench.cases for t in c.expected_structure.probable_tensions if t.match == "case_specific"
    )
    add("info", "CASE_SPECIFIC_TENSIONS", f"{case_specific} case tensions are case-specific formulations (kept verbatim)")
    return issues, bench


def validate_benchmark_file(path: Path, root: Path | None = None) -> tuple[list[BenchmarkIssue], Benchmark | None]:
    return validate_benchmark_data(json.loads(path.read_text(encoding="utf-8")), root)


def summarize(issues: list[BenchmarkIssue], bench: Benchmark | None, path: Path) -> dict:
    tension_matches = Counter(
        t.match for c in (bench.cases if bench else []) for t in c.expected_structure.probable_tensions
    )
    return {
        "validator_version": BENCHMARK_VALIDATOR_VERSION,
        "benchmark_path": str(path),
        "status": "PASS" if not [i for i in issues if i.severity == "error"] else "FAIL",
        "counts": {
            "cases": len(bench.cases) if bench else None,
            "contrast_pairs": len(bench.contrast_pairs) if bench else None,
            "evaluation_dimensions": len(bench.evaluation.card_level_dimensions) if bench else None,
            "failure_categories": len(bench.failure_taxonomy) if bench else None,
        },
        "case_tension_matches": dict(tension_matches),
        "issues": [asdict(i) for i in issues],
    }


DEFAULT_BENCHMARK = BENCHMARK_JSON

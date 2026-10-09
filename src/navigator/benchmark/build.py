"""Build the machine-readable M2.1 benchmark from its canonical Markdown spec.

Output: ``data/eval/benchmarks/m2_1-retrieval-benchmark-v0.1.json``. Every text
value is transcribed from the spec; the only additions are structural
(stable IDs, TAXONOMY match of each tension, splitting of lists) and the
corpus/route context stated in spec §0 and §8.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from navigator.benchmark.source_md import (
    BENCHMARK_MD,
    load,
    normalize,
    parse_cases,
    parse_contrast_pairs,
    parse_list_section,
    parse_rubric,
    section_text,
)
from navigator.corpus.sources import sha256
from navigator.models.benchmark import (
    Benchmark,
    BenchmarkCase,
    ContrastPair,
    ContrastVariant,
    CorpusContext,
    Evaluation,
    EvaluationDimension,
    ExpectedStructure,
    FailureCategory,
    ScaleLevel,
    SetLevelEvaluation,
    TensionRef,
)
from navigator.models.vocabularies import (
    COORDINATES,
    LAUNCH_SHORTLIST_COUNT,
    RETRIEVAL_VERIFIED_COUNT,
    SOURCE_ROUTE_STATUS,
    TENSIONS,
    UNRESOLVED_IDS,
)

BENCHMARK_JSON = Path("data/eval/benchmarks/m2_1-retrieval-benchmark-v0.1.json")

DIMENSION_IDS = {
    "Relevance": "relevance",
    "Transformative value": "transformative_value",
    "Distinctness": "distinctness",
    "Grounding": "grounding",
    "Corpus fit": "corpus_fit",
}

_REQUIREMENT_RE = re.compile(r"не должн|не должен|должен заметно")


def tension_ref(text: str) -> TensionRef:
    if text in TENSIONS:
        return TensionRef(text=text, match="exact", taxonomy_tension=text)
    if "↔" in text:
        left, right = (p.strip() for p in text.split("↔", 1))
        reversed_text = f"{right} ↔ {left}"
        if reversed_text in TENSIONS:
            return TensionRef(text=text, match="reversed_poles", taxonomy_tension=reversed_text)
    return TensionRef(text=text, match="case_specific")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _probable_from_expected(text: str) -> tuple[list[str], list[TensionRef]]:
    """Coordinates/tensions of a contrast variant, only where the spec lists them plainly.

    The first sentence is split on ';'. The first segment counts as coordinates
    only if every comma-separated item is a TAXONOMY coordinate; later segments
    containing '↔' are tensions. Prose (e.g. CP1-B) yields nothing.
    """
    first = _sentences(text)[0].rstrip(".")
    segments = [s.strip() for s in first.split(";")]
    head = [c.strip() for c in segments[0].split(",")]
    coords = head if head and all(c in COORDINATES for c in head) else []
    tensions = [tension_ref(s) for s in segments[1:] if "↔" in s] if coords else []
    return coords, tensions


def _split_shift(text: str) -> tuple[str, str | None]:
    """Separate requirement sentences («не должен», «не должны», «должен заметно») verbatim."""
    shift, req = [], []
    for s in _sentences(text):
        (req if _REQUIREMENT_RE.search(s) else shift).append(s)
    return " ".join(shift), (" ".join(req) or None)


def _variant(vid: str, label_value: str | None, narrative: str | None, expected: str | None) -> ContrastVariant:
    case_ref = note = None
    if label_value:
        m = re.match(r"^(B\d{2})\.\s*(.*)$", label_value)
        if not m:
            raise ValueError(f"{vid}: expected a case reference, got {label_value!r}")
        case_ref, note = m.group(1), (m.group(2).strip() or None)
    coords, tensions = _probable_from_expected(expected) if expected else ([], [])
    return ContrastVariant(
        id=vid,
        case_ref=case_ref,
        note=note,
        narrative=narrative,
        expected=expected,
        probable_coordinates=coords,
        probable_tensions=tensions,
    )


def build_contrast_pair(raw: dict) -> ContrastPair:
    pid = raw["id"]
    fields = raw["fields"]
    a_ref = b_ref = a_nar = b_nar = a_exp = b_exp = shift = requirement = None
    last_variant = None
    for label, value in fields:
        if label == f"{pid}-A":
            a_ref, last_variant = value, "A"
        elif label == f"{pid}-B":
            b_ref, last_variant = value, "B"
        elif label == f"{pid}-A narrative":
            a_nar, last_variant = value, "A"
        elif label == f"{pid}-B narrative":
            b_nar, last_variant = value, "B"
        elif label == "Expected":
            if last_variant == "A":
                a_exp = value
            else:
                b_exp = value
        elif label == "Expected shift":
            shift = value
        elif label == "Contrast requirement":
            requirement = value
        else:
            raise ValueError(f"{pid}: unknown field {label!r}")

    b_shift_coords: tuple[list[str], list[TensionRef]] = ([], [])
    if shift:
        shift_text, shift_req = _split_shift(shift)
        requirement = requirement or shift_req
        b_shift_coords = _probable_from_expected(shift_text)
    else:
        shift_text = None

    variant_b = _variant(f"{pid}-B", b_ref, b_nar, b_exp)
    if shift and not b_exp and b_shift_coords[0]:
        variant_b = variant_b.model_copy(
            update={"probable_coordinates": b_shift_coords[0], "probable_tensions": b_shift_coords[1]}
        )
    return ContrastPair(
        id=pid,
        title=raw["title"],
        variant_a=_variant(f"{pid}-A", a_ref, a_nar, a_exp),
        variant_b=variant_b,
        expected_semantic_shift=shift_text,
        contrast_requirement=requirement,
    )


def build_benchmark(root: Path) -> Benchmark:
    text = load(root)

    cases = [
        BenchmarkCase(
            id=c["id"],
            title=c["title"],
            circumstance=c["circumstance"],
            experiences=c["experiences"],
            center=c["center"],
            narrative=c["narrative"],
            expected_structure=ExpectedStructure(
                semantic_node=c["expected_structure"]["semantic_node"],
                probable_coordinates=c["expected_structure"]["coordinates"],
                probable_tensions=[tension_ref(t) for t in c["expected_structure"]["tensions"]],
                distinctions=c["expected_structure"]["distinctions"],
            ),
            failure_traps=c["failure_traps"],
        )
        for c in parse_cases(text)
    ]

    rubric_block = normalize(section_text(text, "# 5. Evaluation rubric", "# 6. Set-level evaluation"))
    aggregate_policy = rubric_block[rubric_block.index("Единый итоговый балл") :]
    set_block = normalize(section_text(text, "# 6. Set-level evaluation", "# 7. Диагностика failure"))
    main_question = re.search(r"\*\*(.+?)\*\*", set_block).group(1)
    checks_text = set_block.split("Проверяются ", 1)[1].rstrip(".")
    checks = [c.strip() for c in re.split(r", | и (?=сохранение)", checks_text)]
    set_size = re.search(r"набора из (\d)–(\d)", set_block)

    failures = []
    for item in parse_list_section(text, "# 7. Диагностика failure", "# 8. Правила benchmark"):
        m = re.match(r"^\*\*([A-Z]+)\*\* — (.+)$", item)
        failures.append(FailureCategory(id=m.group(1), description=m.group(2)))

    trace_block = normalize(section_text(text, "# 9. Что логировать при будущем прогоне", "# 10. M2.1 acceptance criteria"))
    trace_fields = [f.strip() for f in trace_block.split(":", 1)[1].rstrip(".").split(";")]

    return Benchmark(
        benchmark_id="M2.1-retrieval-benchmark",
        version="0.1",
        spec_document=str(BENCHMARK_MD),
        spec_sha256=sha256(root / BENCHMARK_MD),
        corpus_context=CorpusContext(
            total=LAUNCH_SHORTLIST_COUNT,
            retrieval_eligible=RETRIEVAL_VERIFIED_COUNT,
            unresolved=len(UNRESOLVED_IDS),
            source_route=SOURCE_ROUTE_STATUS,
        ),
        required_routes=["MEANING", "STRUCTURE"],
        cases=cases,
        contrast_principle=normalize(section_text(text, "# 4. Контрастные пары", "## CP1")),
        contrast_pairs=[build_contrast_pair(p) for p in parse_contrast_pairs(text)],
        evaluation=Evaluation(
            scale=[0, 1, 2],
            card_level_dimensions=[
                EvaluationDimension(
                    id=DIMENSION_IDS[label],
                    label=label,
                    levels=[ScaleLevel(score=s, description=d) for s, d in levels],
                )
                for label, levels in parse_rubric(text)
            ],
            aggregate_policy=aggregate_policy,
            set_level=SetLevelEvaluation(
                set_size={"min": int(set_size.group(1)), "max": int(set_size.group(2))},
                main_question=main_question,
                checks=checks,
            ),
        ),
        failure_taxonomy=failures,
        rules=parse_list_section(text, "# 8. Правила benchmark", "# 9. Что логировать"),
        trace_fields=trace_fields,
    )


def write_benchmark(root: Path, force: bool = False) -> Path:
    out = root / BENCHMARK_JSON
    if out.exists() and not force:
        raise FileExistsError(f"{out} already exists; rebuild only with --force")
    benchmark = build_benchmark(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(benchmark.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out

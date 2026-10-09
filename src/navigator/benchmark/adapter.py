"""BENCHMARK ADAPTER — builds QueryRepresentation objects from M2.1 benchmark items.

This is NOT a production interpretation layer. Conventions (M2.2 decision):
- confirmed_question := benchmark ``center`` (outer «» removed) — proxy for the
  question a user would confirm;
- working_hypotheses := [expected_structure.semantic_node, *distinctions] —
  a reproducible test proxy built from evaluation guidance;
- coordinates / tensions := expected structure; tensions marked ``exact`` or
  ``reversed_poles`` go to canonical_tensions in their TAXONOMY form, tensions
  marked ``case_specific`` go to free_tensions verbatim.

Every query carries ``provenance.origin = "benchmark_adapter"``.

Contrast variants without a main case have no center and (mostly) no prose
interpretation in the spec; the adapter does not invent them. Such variants get
no QueryRepresentation: only the routes whose inputs exist are computed
(see ``ContrastProbe``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from navigator.models.benchmark import Benchmark, BenchmarkCase, ContrastVariant, TensionRef
from navigator.models.query import QueryProvenance, QueryRepresentation, UserContext

ADAPTER_VERSION = "benchmark-adapter/0.1.0"
CONFIRMED_QUESTION_SOURCE = "benchmark_center_proxy"
INTERPRETATION_SOURCE = "benchmark_expected_structure_proxy"
ADAPTER_NOTE = "M2.2 benchmark convention; not a production confirmed question or interpretation"


def center_to_question(center: str) -> str:
    text = center.strip()
    if text.startswith("«") and text.endswith("»"):
        text = text[1:-1].strip()
    return text


def split_tensions(refs: list[TensionRef]) -> tuple[list[str], list[str]]:
    canonical: list[str] = []
    free: list[str] = []
    for t in refs:
        if t.match in ("exact", "reversed_poles"):
            if t.taxonomy_tension not in canonical:
                canonical.append(t.taxonomy_tension)
        elif t.text not in free:
            free.append(t.text)
    return canonical, free


def case_query(case: BenchmarkCase) -> QueryRepresentation:
    es = case.expected_structure
    canonical, free = split_tensions(es.probable_tensions)
    return QueryRepresentation(
        confirmed_question=center_to_question(case.center),
        context=UserContext(circumstance=case.circumstance, narrative=case.narrative),
        experiences=case.experiences,
        working_hypotheses=[es.semantic_node, *es.distinctions][:4],
        coordinates=list(dict.fromkeys(es.probable_coordinates)),
        canonical_tensions=canonical,
        free_tensions=free,
        provenance=QueryProvenance(
            origin="benchmark_adapter",
            confirmed_question_source=CONFIRMED_QUESTION_SOURCE,
            interpretation_source=INTERPRETATION_SOURCE,
            benchmark_item_id=case.id,
            note=ADAPTER_NOTE,
        ),
    )


@dataclass
class ContrastProbe:
    """Inputs available for one contrast variant."""

    variant_id: str
    narrative: str
    query: QueryRepresentation | None
    coordinates: list[str]
    canonical_tensions: list[str]
    free_tensions: list[str]
    unavailable: dict[str, str] = field(default_factory=dict)


def contrast_probe(variant: ContrastVariant, bench: Benchmark) -> ContrastProbe:
    if variant.case_ref:
        case = next(c for c in bench.cases if c.id == variant.case_ref)
        q = case_query(case)
        return ContrastProbe(
            variant.id, case.narrative, q, q.coordinates, q.canonical_tensions, q.free_tensions
        )
    canonical, free = split_tensions(variant.probable_tensions)
    unavailable = {
        "Q0_QUESTION_ONLY_CONTROL": "benchmark variant has no center (confirmed-question proxy)",
        "Q1_MEANING": "benchmark variant has no center and no working-hypothesis proxy",
    }
    if not variant.probable_coordinates:
        unavailable["STRUCTURE"] = "benchmark variant lists no coordinates"
    return ContrastProbe(
        variant.id, variant.narrative, None, list(variant.probable_coordinates), canonical, free, unavailable
    )

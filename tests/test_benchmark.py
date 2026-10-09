"""M2.1 — retrieval benchmark: machine-readable form, validator and future trace contract."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from navigator.benchmark.build import BENCHMARK_JSON, build_benchmark
from navigator.benchmark.source_md import BENCHMARK_MD, normalize
from navigator.benchmark.validator import validate_benchmark_data, validate_benchmark_file
from navigator.models.benchmark import EVALUATION_DIMENSIONS, FAILURE_CATEGORIES, ExpectedStructure
from navigator.models.trace import BenchmarkRunTrace

ROOT = Path(__file__).resolve().parents[1]
BENCH_PATH = ROOT / BENCHMARK_JSON
SPEC_SHA256 = "ca3c9474cd7186692b561bbba108244bcbf1db44a1e8d674d448ba9b951d2cf7"

needs_benchmark = pytest.mark.skipif(not BENCH_PATH.exists(), reason="benchmark not built")


@pytest.fixture(scope="module")
def data() -> dict:
    return json.loads(BENCH_PATH.read_text(encoding="utf-8"))


def errors(d: dict, root: Path | None = None) -> set[str]:
    issues, _ = validate_benchmark_data(d, root)
    return {i.code for i in issues if i.severity == "error"}


# ------------------------------------------------------------------ real benchmark


@needs_benchmark
def test_real_benchmark_passes():
    issues, bench = validate_benchmark_file(BENCH_PATH, ROOT)
    assert [i for i in issues if i.severity == "error"] == []
    assert [c.id for c in bench.cases] == [f"B{i:02d}" for i in range(1, 21)]
    assert [p.id for p in bench.contrast_pairs] == ["CP1", "CP2", "CP3", "CP4"]


@needs_benchmark
def test_canonical_spec_is_unchanged_and_in_sync(data):
    from navigator.corpus.sources import sha256

    assert sha256(ROOT / BENCHMARK_MD) == SPEC_SHA256 == data["spec_sha256"]
    assert build_benchmark(ROOT).model_dump(mode="json") == data


@needs_benchmark
def test_case_texts_are_verbatim_from_spec(data):
    spec = normalize((ROOT / BENCHMARK_MD).read_text(encoding="utf-8"))
    for case in data["cases"]:
        for field in ("narrative", "center", "circumstance"):
            assert case[field] in spec, (case["id"], field)
        assert case["expected_structure"]["semantic_node"] in spec
        for trap in case["failure_traps"]:
            assert trap in spec, (case["id"], trap)
    for pair in data["contrast_pairs"]:
        for side in ("variant_a", "variant_b"):
            if pair[side]["narrative"]:
                assert pair[side]["narrative"] in spec


@needs_benchmark
def test_contrast_pairs_reference_expected_cases(data):
    refs = {p["id"]: (p["variant_a"]["case_ref"], p["variant_b"]["case_ref"]) for p in data["contrast_pairs"]}
    assert refs == {"CP1": ("B11", None), "CP2": (None, None), "CP3": ("B02", None), "CP4": ("B05", None)}
    assert all(p["contrast_requirement"] for p in data["contrast_pairs"])


@needs_benchmark
def test_evaluation_and_failure_taxonomy_match_spec(data):
    ev = data["evaluation"]
    assert ev["scale"] == [0, 1, 2]
    assert [d["id"] for d in ev["card_level_dimensions"]] == list(EVALUATION_DIMENSIONS)
    assert ev["aggregate_score"] is False
    assert ev["set_level"]["set_size"] == {"min": 3, "max": 5}
    assert [f["id"] for f in data["failure_taxonomy"]] == list(FAILURE_CATEGORIES)


@needs_benchmark
def test_no_card_ids_no_traditions_no_source(data):
    assert data["source_route_required"] is False
    assert data["required_routes"] == ["MEANING", "STRUCTURE"]
    codes = errors(data)
    assert not {"CARD_ID_PRESENT", "UNRESOLVED_REFERENCED", "TRADITION_OR_AUTHOR_REQUIRED", "SOURCE_REQUIRED"} & codes


def test_expected_structure_is_guidance_not_gold():
    es = ExpectedStructure.model_fields
    assert es["role"].default == "evaluation_guidance"
    assert "required_card_ids" not in es and "gold_card_ids" not in es


# ------------------------------------------------------------------ validator failure modes


@needs_benchmark
def test_wrong_case_count(data):
    d = copy.deepcopy(data)
    d["cases"].pop()
    assert "CASE_COUNT" in errors(d)


@needs_benchmark
def test_duplicate_case_id(data):
    d = copy.deepcopy(data)
    d["cases"][1]["id"] = "B01"
    assert "DUPLICATE_CASE_ID" in errors(d)


@needs_benchmark
def test_missing_contrast_pair(data):
    d = copy.deepcopy(data)
    d["contrast_pairs"].pop()
    assert "CONTRAST_PAIRS" in errors(d)


@needs_benchmark
def test_broken_contrast_reference(data):
    d = copy.deepcopy(data)
    d["contrast_pairs"][0]["variant_a"]["case_ref"] = "B99"
    assert "BROKEN_CASE_REFERENCE" in errors(d)


@needs_benchmark
def test_missing_required_case_field(data):
    d = copy.deepcopy(data)
    d["cases"][0]["narrative"] = ""
    assert "SCHEMA" in errors(d)


@needs_benchmark
def test_non_canonical_coordinate(data):
    d = copy.deepcopy(data)
    d["cases"][0]["expected_structure"]["probable_coordinates"].append("desire")
    assert "COORDINATE_NOT_CANONICAL" in errors(d)


@needs_benchmark
def test_tension_convention_and_taxonomy_flag(data):
    d = copy.deepcopy(data)
    d["cases"][0]["expected_structure"]["probable_tensions"][0]["text"] = "желание против долга"
    assert "TENSION_FORMAT" in errors(d)
    d = copy.deepcopy(data)
    t = d["cases"][0]["expected_structure"]["probable_tensions"][0]  # «желание ↔ долг», exact
    t["match"], t["taxonomy_tension"] = "case_specific", None
    assert "TENSION_MATCH_INCONSISTENT" in errors(d)


@needs_benchmark
def test_evaluation_dimensions_and_aggregate(data):
    d = copy.deepcopy(data)
    d["evaluation"]["card_level_dimensions"].pop()
    assert "EVALUATION_DIMENSIONS" in errors(d)
    d = copy.deepcopy(data)
    d["evaluation"]["aggregate_score"] = True
    assert "SCHEMA" in errors(d)


@needs_benchmark
def test_failure_taxonomy_must_match(data):
    d = copy.deepcopy(data)
    d["failure_taxonomy"].append({"id": "OTHER", "description": "x"})
    assert errors(d) & {"SCHEMA", "FAILURE_TAXONOMY"}


@needs_benchmark
def test_mandatory_card_ids_rejected(data):
    d = copy.deepcopy(data)
    d["cases"][0]["expected_card_ids"] = ["C0442"]
    assert {"CARD_ID_PRESENT", "FORBIDDEN_FIELD"} <= errors(d)
    d = copy.deepcopy(data)
    d["cases"][0]["failure_traps"].append("не выдать C0377")
    assert {"CARD_ID_PRESENT", "UNRESOLVED_REFERENCED"} <= errors(d)


@needs_benchmark
def test_required_tradition_rejected(data):
    d = copy.deepcopy(data)
    d["cases"][0]["expected_structure"]["distinctions"].append("обязательно стоицизм")
    assert "TRADITION_OR_AUTHOR_REQUIRED" in errors(d)


@needs_benchmark
def test_source_route_cannot_be_required(data):
    d = copy.deepcopy(data)
    d["required_routes"].append("SOURCE")
    assert "SCHEMA" in errors(d)
    d = copy.deepcopy(data)
    d["source_route_required"] = True
    assert "SCHEMA" in errors(d)


@needs_benchmark
def test_spec_drift_detected(data):
    d = copy.deepcopy(data)
    d["cases"][0]["center"] = "«Другой вопрос?»"
    assert "SPEC_DRIFT" in errors(d, ROOT)


# ------------------------------------------------------------------ future trace contract


def trace(**overrides) -> dict:
    t = {
        "run_id": "run-0001",
        "benchmark_version": "0.1",
        "item_id": "B03",
        "input": {"narrative": "synthetic narrative"},
        "working_hypotheses": [{"text": "h1"}, {"text": "h2"}],
        "query_representation": {"coordinates": ["смысл / цель"], "tensions": ["достигнутая цель ↔ смысл"]},
        "meaning_candidates": [{"fragment_id": "C0579", "route": "MEANING", "rank": 1, "score": 0.8}],
        "structure_candidates": [{"fragment_id": "C0441", "route": "STRUCTURE", "rank": 1}],
        "candidate_pool": [
            {"fragment_id": "C0579", "found_by": ["MEANING"]},
            {"fragment_id": "C0441", "found_by": ["STRUCTURE"]},
            {"fragment_id": "C0583", "found_by": ["MEANING"], "excluded": True, "exclusion_reason": "overlap"},
        ],
        "final_cards": [
            {"fragment_id": "C0579", "role": "anchor", "explanation": "e1"},
            {"fragment_id": "C0441", "role": "counterweight", "explanation": "e2"},
        ],
        "card_evaluations": [{"fragment_id": "C0579", "relevance": 2, "grounding": 1}],
        "failures": [{"category": "RANKING", "notes": "n"}],
    }
    t.update(overrides)
    return t


def test_trace_contract_accepts_minimal_run():
    BenchmarkRunTrace.model_validate(trace())


def test_trace_coordinates_are_not_tied_to_expected_structure():
    # A run may interpret differently from the benchmark guidance (spec §8.4).
    BenchmarkRunTrace.model_validate(trace(query_representation={"coordinates": ["контроль"], "tensions": []}))


@pytest.mark.parametrize(
    "override",
    [
        {"meaning_candidates": [{"fragment_id": "C0377", "route": "MEANING"}]},  # unresolved
        {"structure_candidates": [{"fragment_id": "C0441", "route": "SOURCE"}]},  # SOURCE route
        {"meaning_candidates": [{"fragment_id": "C0441", "route": "STRUCTURE"}]},  # wrong route list
        {"working_hypotheses": [{"text": "only one"}]},
        {"working_hypotheses": [{"text": f"h{i}"} for i in range(5)]},
        {"final_cards": [{"fragment_id": f"C00{i:02d}", "role": "r", "explanation": "e"} for i in range(6)]},
        {"final_cards": [{"fragment_id": "C0583", "role": "r", "explanation": "e"}]},  # excluded from pool
        {"card_evaluations": [{"fragment_id": "C0579", "relevance": 3}]},
        {"card_evaluations": [{"fragment_id": "C0579", "total_score": 8}]},  # no aggregate
        {"failures": [{"category": "OTHER"}]},
        {"item_id": "X1"},
    ],
)
def test_trace_contract_rejects(override):
    with pytest.raises(ValidationError):
        BenchmarkRunTrace.model_validate(trace(**override))

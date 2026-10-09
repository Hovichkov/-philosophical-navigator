"""M2.2 baseline benchmark run: 20 cases through Q0 / Q1 / STRUCTURE / union,
plus contrast-pair overlap diagnostics.

Results are written only for a real (non-fake) embedding client. Diagnostics
report overlap sizes and IDs without any PASS threshold (analysis is M2.3).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from navigator.benchmark.adapter import ADAPTER_VERSION, ContrastProbe, case_query, contrast_probe
from navigator.models.benchmark import Benchmark
from navigator.models.retrieval import CandidateRetrievalResult
from navigator.models.trace import (
    BenchmarkRunTrace,
    PoolCandidate,
    QueryRepresentation as TraceQuerySummary,
    RouteCandidate,
    UserInput,
    WorkingHypothesis,
)
from navigator.representations.meaning import (
    MEANING_CARD_DOC_VERSION,
    MEANING_SPEC_ID,
    Q0_QUERY_VERSION,
    Q1_QUERY_VERSION,
    Representation,
)
from navigator.retrieval.engine import CandidateRetriever
from navigator.retrieval.routes import STRUCTURE_RANKING_RULE, cosine_rank, structure_rank

RUN_FORMAT = "m2.2-baseline-run/0.1.0"
CONTRAST_TOP_N = 10
NARRATIVE_CONTROL_VERSION = "narrative-control/1.0"
DEFAULT_RUNS_DIR = Path("reports/benchmark-runs")


def trace_for_case(run_id: str, bench: Benchmark, case_id: str, result: CandidateRetrievalResult) -> BenchmarkRunTrace:
    q = result.query
    return BenchmarkRunTrace(
        run_id=run_id,
        benchmark_version=bench.version,
        item_id=case_id,
        config={
            "run_format": RUN_FORMAT,
            "adapter": ADAPTER_VERSION,
            "embedding": result.embedding_config,
            "corpus_version": result.corpus_version,
        },
        input=UserInput(
            circumstance=q.context.circumstance,
            experiences=q.experiences,
            center=q.confirmed_question,
            narrative=q.context.narrative,
        ),
        working_hypotheses=[WorkingHypothesis(text=h) for h in q.working_hypotheses],
        query_representation=TraceQuerySummary(
            coordinates=q.coordinates, tensions=[*q.canonical_tensions, *q.free_tensions]
        ),
        meaning_candidates=[
            RouteCandidate(fragment_id=h.card_id, route="MEANING", rank=h.rank, score=h.cosine)
            for h in result.q1_meaning.hits
        ],
        structure_candidates=[
            RouteCandidate(
                fragment_id=h.card_id, route="STRUCTURE", rank=h.rank,
                signals={"tension_overlap": h.tension_overlap, "coordinate_overlap": h.coordinate_overlap},
            )
            for h in result.structure.hits
        ],
        candidate_pool=[
            PoolCandidate(
                fragment_id=c.card_id,
                found_by=["MEANING" if r == "Q1_MEANING" else "STRUCTURE" for r in c.found_by],
                signals=c.model_dump(exclude={"card_id", "found_by"}),
            )
            for c in result.candidate_union
        ],
        candidate_retrieval=result,
    )


def _overlap(a: list[str] | None, b: list[str] | None, top_n: int) -> dict:
    if a is None or b is None:
        return {"status": "not_computable"}
    common = sorted(set(a) & set(b))
    union = set(a) | set(b)
    return {
        "status": "computed",
        "a_ids": a,
        "b_ids": b,
        "overlap_ids": common,
        "overlap_count": len(common),
        "overlap_share_of_top_n": round(len(common) / top_n, 3),
        "jaccard": round(len(common) / len(union), 3) if union else None,
    }


def contrast_diagnostics(bench: Benchmark, retriever: CandidateRetriever, top_n: int = CONTRAST_TOP_N) -> list[dict]:
    results = []
    for pair in bench.contrast_pairs:
        probes = [contrast_probe(pair.variant_a, bench), contrast_probe(pair.variant_b, bench)]

        def route_ids(p: ContrastProbe, route: str) -> list[str] | None:
            if route in p.unavailable:
                return None
            if route == "STRUCTURE":
                hits, _, _ = structure_rank(retriever.universe, p.coordinates, p.canonical_tensions, top_n)
                return [h.card_id for h in hits]
            if route == "NARRATIVE_CONTROL":
                rep = Representation(f"{p.variant_id}:narrative", NARRATIVE_CONTROL_VERSION, p.narrative)
                vec = retriever.query_cache.embed([rep], retriever.client, persist=retriever.persist_cache)[0]
                return [h.card_id for h in cosine_rank(vec, retriever.card_ids, retriever.card_vectors, top_n)]
            result = retriever.retrieve(p.query, p.variant_id)
            hits = result.q0_control.hits if route == "Q0_QUESTION_ONLY_CONTROL" else result.q1_meaning.hits
            return [h.card_id for h in hits[:top_n]]

        routes = {}
        for route in ("Q0_QUESTION_ONLY_CONTROL", "Q1_MEANING", "STRUCTURE", "NARRATIVE_CONTROL"):
            a, b = route_ids(probes[0], route), route_ids(probes[1], route)
            entry = _overlap(a, b, top_n)
            if entry["status"] == "not_computable":
                entry["reasons"] = {
                    p.variant_id: p.unavailable.get(route) for p in probes if p.unavailable.get(route)
                }
            routes[route] = entry
        results.append(
            {
                "pair_id": pair.id,
                "variants": [p.variant_id for p in probes],
                "case_refs": [pair.variant_a.case_ref, pair.variant_b.case_ref],
                "top_n": top_n,
                "routes": routes,
                "note": "no PASS threshold; smaller overlap is not automatically better (M2.3 analysis)",
            }
        )
    return results


def run_benchmark(bench: Benchmark, retriever: CandidateRetriever, run_id: str) -> tuple[list[BenchmarkRunTrace], list[dict]]:
    traces = [trace_for_case(run_id, bench, c.id, retriever.retrieve(case_query(c), c.id)) for c in bench.cases]
    return traces, contrast_diagnostics(bench, retriever)


def write_run(
    bench: Benchmark, retriever: CandidateRetriever, runs_dir: Path = DEFAULT_RUNS_DIR, run_id: str | None = None,
    run_label: str = "m2_4-meaning-separation",
) -> Path:
    if getattr(retriever.client, "is_fake", True):
        raise RuntimeError("refusing to record benchmark results produced by a fake embedding client")
    run_id = run_id or f"{run_label}-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    traces, contrast = run_benchmark(bench, retriever, run_id)
    out = runs_dir / run_id
    out.mkdir(parents=True, exist_ok=False)
    with (out / "traces.jsonl").open("w", encoding="utf-8") as fh:
        for t in traces:
            fh.write(json.dumps(t.model_dump(mode="json"), ensure_ascii=False) + "\n")
    (out / "contrast-diagnostics.json").write_text(json.dumps(contrast, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "run-manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "run_format": RUN_FORMAT,
                "empirical": True,
                "benchmark_spec_sha256": bench.spec_sha256,
                "embedding": retriever.client.config.public_dict(),
                "embedding_device": getattr(retriever.client, "device", None),
                "representations": {
                    "meaning_spec": MEANING_SPEC_ID,
                    "card": MEANING_CARD_DOC_VERSION,
                    "q0": Q0_QUERY_VERSION,
                    "q1": Q1_QUERY_VERSION,
                    "structure_rule": STRUCTURE_RANKING_RULE,
                },
                "corpus_version": retriever.corpus_version,
                "top_k": retriever.top_k,
                "contrast_top_n": CONTRAST_TOP_N,
                "cases": len(traces),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return out


def write_structure_only_run(
    bench: Benchmark, fragments: list, runs_dir: Path = DEFAULT_RUNS_DIR, top_k: int = 15, corpus_version: str | None = None
) -> Path:
    """Deterministic STRUCTURE route for all cases (no embeddings involved).

    Partial empirical artifact for when no embedding API is available: Q0, Q1 and
    the candidate union are NOT computed here.
    """
    from navigator.benchmark.adapter import contrast_probe
    from navigator.corpus.readiness import retrieval_universe
    from navigator.retrieval.routes import STRUCTURE_RANKING_RULE

    universe = sorted(retrieval_universe(fragments), key=lambda f: f.id)
    run_id = "m2_2-structure-only-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cases = []
    for c in bench.cases:
        q = case_query(c)
        hits, matching, tied = structure_rank(universe, q.coordinates, q.canonical_tensions, top_k)
        cases.append(
            {
                "case_id": c.id,
                "confirmed_question": q.confirmed_question,
                "coordinates": q.coordinates,
                "canonical_tensions": q.canonical_tensions,
                "free_tensions_not_used_by_structure": q.free_tensions,
                "matching_cards": matching,
                "tied_at_cutoff": tied,
                "hits": [h.model_dump() for h in hits],
            }
        )
    contrast = []
    for pair in bench.contrast_pairs:
        probes = [contrast_probe(pair.variant_a, bench), contrast_probe(pair.variant_b, bench)]
        ids = []
        for p in probes:
            if "STRUCTURE" in p.unavailable:
                ids.append(None)
            else:
                h, _, _ = structure_rank(universe, p.coordinates, p.canonical_tensions, CONTRAST_TOP_N)
                ids.append([x.card_id for x in h])
        entry = _overlap(ids[0], ids[1], CONTRAST_TOP_N)
        if entry["status"] == "not_computable":
            entry["reasons"] = {p.variant_id: p.unavailable["STRUCTURE"] for p in probes if "STRUCTURE" in p.unavailable}
        contrast.append({"pair_id": pair.id, "variants": [p.variant_id for p in probes], "STRUCTURE": entry})
    out = runs_dir / run_id
    out.mkdir(parents=True, exist_ok=False)
    (out / "structure-results.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "run_format": RUN_FORMAT,
                "scope": "STRUCTURE route only; Q0/Q1/union pending real embeddings (PENDING_API)",
                "adapter": ADAPTER_VERSION,
                "ranking_rule": STRUCTURE_RANKING_RULE,
                "top_k": top_k,
                "contrast_top_n": CONTRAST_TOP_N,
                "corpus_version": corpus_version,
                "benchmark_spec_sha256": bench.spec_sha256,
                "cases": cases,
                "contrast_structure_overlap": contrast,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return out

"""Run comparison and human-readable retrieval samples (reporting only).

No ranking, selection or rewriting: results are shown exactly as recorded.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from navigator.diagnostics.retrieval_diagnosis import ranking_stats
from navigator.models.fragment import Fragment


def load_traces(run_dir: Path) -> list[dict]:
    return [json.loads(l) for l in (run_dir / "traces.jsonl").read_text(encoding="utf-8").splitlines()]


def _rankings(traces: list[dict], route_key: str) -> dict[str, list[str]]:
    return {t["item_id"]: [h["card_id"] for h in t["candidate_retrieval"][route_key]["hits"]] for t in traces}


def _union_stats(traces: list[dict]) -> dict:
    sizes = [len(t["candidate_retrieval"]["candidate_union"]) for t in traces]
    both = [sum(1 for c in t["candidate_retrieval"]["candidate_union"] if len(c["found_by"]) == 2) for t in traces]
    cards = {c["card_id"] for t in traces for c in t["candidate_retrieval"]["candidate_union"]}
    return {
        "mean_size": round(statistics.mean(sizes), 2), "min_size": min(sizes), "max_size": max(sizes),
        "found_by_both_mean": round(statistics.mean(both), 2), "found_by_both_min": min(both), "found_by_both_max": max(both),
        "found_by_both_per_case": {t["item_id"]: b for t, b in zip(traces, both)},
        "unique_cards_across_cases": len(cards),
    }


def compare_runs(old: list[dict], new: list[dict], fragments: list[Fragment]) -> dict:
    universe = sorted((f for f in fragments if f.technical.retrieval_eligible), key=lambda f: f.id)
    ids = [f.id for f in universe]
    recovered = {f.id for f in universe if f.technical.recovery_status}
    out: dict = {}
    for route, key in (("Q1", "q1_meaning"), ("Q0", "q0_control"), ("STRUCTURE", "structure")):
        o, n = _rankings(old, key), _rankings(new, key)
        per_case_overlap = {k: len(set(o[k]) & set(n[k])) for k in n}
        out[route] = {
            "old": ranking_stats(o, ids, recovered),
            "new": ranking_stats(n, ids, recovered),
            "top15_overlap_old_new_per_case": per_case_overlap,
            "top15_overlap_old_new_mean": round(statistics.mean(per_case_overlap.values()) / 15, 4),
            "identical": o == n,
        }
    old_s = {t["item_id"]: t["candidate_retrieval"]["structure"] for t in old}
    new_s = {t["item_id"]: t["candidate_retrieval"]["structure"] for t in new}
    out["STRUCTURE"]["byte_identical_route_records"] = old_s == new_s
    out["union"] = {"old": _union_stats(old), "new": _union_stats(new)}
    return out


def _source_label(f: Fragment) -> str:
    return f"{f.work}, {f.location}" if f.work else "—"


def _cut(text: str | None, n: int = 260) -> str:
    text = (text or "—").replace("\n", " ")
    return text if len(text) <= n else text[: n - 1] + "…"


def render_samples(traces: list[dict], fragments: list[Fragment], bench_cases: dict, run_id: str,
                   q1_top: int = 10, structure_top: int = 5) -> str:
    by_id = {f.id: f for f in fragments}
    lines = [
        "# M2.4 — Retrieval samples (raw, unranked by hand)",
        "",
        f"Run: `{run_id}` · model `BAAI/bge-m3` · MEANING spec `meaning-v2` "
        "(card = perspective + philosophical_questions; Q1 = question + hypotheses).",
        "",
        "Results are shown exactly as retrieved: no reranking, no manual selection, no rewriting.",
        "Mark **[both]** = the card is in the candidate union through both Q1 and STRUCTURE (top-15 each).",
        "Recovered-first-29 cards are marked *(recovered)*. Perspectives of 84 cards are templated in the corpus "
        "(«Рассмотреть ситуацию через операцию…») — shown verbatim.",
        "",
    ]
    for t in traces:
        cr = t["candidate_retrieval"]
        case = bench_cases[t["item_id"]]
        both = {c["card_id"] for c in cr["candidate_union"] if len(c["found_by"]) == 2}
        q = cr["query"]
        lines += [
            f"## {t['item_id']}. {case.title}",
            "",
            f"**Ситуация:** {case.circumstance} · переживания: {', '.join(case.experiences)}",
            "",
            f"**Вопрос (center → confirmed question):** {q['confirmed_question']}",
            "",
            f"**Narrative:** {_cut(case.narrative, 600)}",
            "",
            "**Working hypotheses (benchmark proxy):**",
            *[f"- {h}" for h in q["working_hypotheses"]],
            "",
            f"**Q1 top-{q1_top}:**",
            "",
            "| # | card | источник | perspective | cos | |",
            "|---|---|---|---|---|---|",
        ]
        for h in cr["q1_meaning"]["hits"][:q1_top]:
            f = by_id[h["card_id"]]
            mark = "**[both]**" if h["card_id"] in both else ""
            rec = " *(recovered)*" if f.technical.recovery_status else ""
            lines.append(
                f"| {h['rank']} | {h['card_id']}{rec} | {_source_label(f)} | {_cut(f.perspective).replace('|', '/')} | {h['cosine']:.3f} | {mark} |"
            )
        lines += [
            "",
            f"**STRUCTURE top-{structure_top}** (query coordinates: {', '.join(cr['structure']['query_coordinates']) or '—'}; "
            f"canonical tensions: {', '.join(cr['structure']['query_canonical_tensions']) or '—'}; "
            f"matching cards {cr['structure']['matching_cards']}, tied at cutoff {cr['structure']['tied_at_cutoff']}):",
            "",
            "| # | card | источник | matched tensions | matched coordinates | operation | |",
            "|---|---|---|---|---|---|---|",
        ]
        for h in cr["structure"]["hits"][:structure_top]:
            f = by_id[h["card_id"]]
            mark = "**[both]**" if h["card_id"] in both else ""
            rec = " *(recovered)*" if f.technical.recovery_status else ""
            lines.append(
                f"| {h['rank']} | {h['card_id']}{rec} | {_source_label(f)} | {', '.join(h['matched_tensions']) or '—'} | "
                f"{', '.join(h['matched_coordinates']) or '—'} | {h['operation'] or '—'} | {mark} |"
            )
        lines += ["", f"Candidate union: {len(cr['candidate_union'])} cards, of them {len(both)} through both routes.", ""]
    return "\n".join(lines) + "\n"

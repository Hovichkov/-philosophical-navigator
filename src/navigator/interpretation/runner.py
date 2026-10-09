"""M2.6 interpretation benchmark runner, samples and end-to-end smoke (reporting only)."""

from __future__ import annotations

import datetime as dt
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from pydantic import TypeAdapter

from navigator.interpretation.interpreter import PROMPT_VERSION, Interpreter, interpret
from navigator.models.interpretation import InsufficientInterpretation, InterpretationInput, InterpretationResult

BENCHMARK_PATH = Path("data/eval/interpretation/m2_6-interpretation-benchmark-v0.1.json")
Outcome = InterpretationResult | InsufficientInterpretation
_OUTCOME = TypeAdapter(Outcome)


def load_benchmark(path: Path = BENCHMARK_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def case_input(case: dict) -> InterpretationInput:
    return InterpretationInput(
        topic=case["topic"], experiences=case["experiences"],
        difficulty_center=case["difficulty_center"], free_narrative=case["free_narrative"],
    )


def run_interpretation(cases: list[dict], interpreter: Interpreter, out_dir: Path, workers: int = 3) -> dict[str, Outcome]:
    (out_dir / "interpretations").mkdir(parents=True, exist_ok=True)
    results: dict[str, Outcome] = {}
    todo = []
    for c in cases:
        path = out_dir / "interpretations" / f"{c['id']}.json"
        if path.exists():  # resume
            results[c["id"]] = _OUTCOME.validate_json(path.read_text(encoding="utf-8"))
        else:
            todo.append(c)
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(interpret, case_input(c), interpreter): c["id"] for c in todo}
        for fut in as_completed(futures):
            cid = futures[fut]
            try:
                res = fut.result()
            except Exception as exc:
                errors[cid] = str(exc)[:800]
                continue
            (out_dir / "interpretations" / f"{cid}.json").write_text(res.model_dump_json(indent=2) + "\n", encoding="utf-8")
            results[cid] = res
    (out_dir / "errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "run-manifest.json").write_text(json.dumps({
        "run_id": out_dir.name, "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "interpreter": interpreter.name, "model": interpreter.model, "prompt_version": PROMPT_VERSION,
        "cases": len(cases), "completed": len(results),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return results


def render_samples(cases: list[dict], results: dict[str, Outcome], run_id: str,
                   review_notes: dict[str, list[str]] | None = None) -> str:
    lines = [
        "# M2.6 — Interpretation samples",
        "",
        f"Run: `{run_id}` · interpreter: Claude via the local Claude Code CLI · prompt `{PROMPT_VERSION}`.",
        "",
        "Outputs are shown exactly as generated. Working hypotheses are INTERNAL retrieval material — "
        "in the product the user sees only the proposed question. No aggregate scores.",
        "",
    ]
    for c in cases:
        lines += [f"## {c['id']}. {c['label']}", "", "### Input", "",
                  f"- **topic:** {c['topic']}", f"- **experiences:** {', '.join(c['experiences'])}",
                  f"- **difficulty_center:** {c['difficulty_center']}", f"- **free narrative:** {c['free_narrative']}", ""]
        res = results.get(c["id"])
        if res is None:
            lines += ["_Interpretation failed (see errors.json)._", ""]
            continue
        if isinstance(res, InsufficientInterpretation):
            lines += ["### Result: insufficient input", "", f"- reason: {res.reason}",
                      f"- clarification shown to the user: «{res.clarification_prompt}»", ""]
            continue
        lines += ["### Proposed question", "", f"> {res.proposed_question}", "",
                  "### Working hypotheses (internal)", "", *[f"{i}. {h}" for i, h in enumerate(res.working_hypotheses, 1)], "",
                  "### Semantic mapping", "",
                  f"- **coordinates:** {', '.join(res.coordinates)}",
                  f"- **canonical tensions:** {', '.join(res.canonical_tensions) or '—'}",
                  f"- **free tensions:** {', '.join(res.free_tensions) or '—'}", "",
                  "### Notes", ""]
        notes = [f"- ({n.kind}) {n.note}" for n in res.trace.reading_notes]
        notes += [f"- (ambiguity) {a}" for a in res.ambiguity_notes]
        lines += (notes or ["- —"]) + [""]
        if res.trace.attempts > 1:
            lines += [f"_Needed {res.trace.attempts} attempts to pass the contract._", ""]
        for note in (review_notes or {}).get(c["id"], []):
            lines += [f"**Human review:** {note}", ""]
    return "\n".join(lines) + "\n"


def run_e2e_smoke(case: dict, interpretation: InterpretationResult, fragments: list, retriever, composer, out_dir: Path) -> dict:
    """raw input → interpretation → SIMULATED confirmation → M2.4 retrieval → M2.5 composition.

    Existing layers are used as they are; nothing is modified. The confirmation is
    explicitly marked ``benchmark_simulation`` in the Confirmation and the query provenance.
    """
    from navigator.composition.composer import build_package, compose
    from navigator.interpretation.interpreter import confirm, to_query_representation

    confirmation = confirm(interpretation, action="confirmed", source="benchmark_simulation")
    query = to_query_representation(interpretation, confirmation, item_id=case["id"])
    retrieval = retriever.retrieve(query, case["id"])
    trace = {"item_id": case["id"], "run_id": out_dir.name, "candidate_retrieval": retrieval.model_dump(mode="json")}
    composition = compose(build_package(trace, fragments), fragments, composer)
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "stages": ["raw_input", "interpretation", "simulated_confirmation", "m2_4_retrieval", "m2_5_composition"],
        "input": case,
        "interpretation": json.loads(interpretation.model_dump_json()),
        "confirmation": json.loads(confirmation.model_dump_json()),
        "query_representation": json.loads(query.model_dump_json()),
        "retrieval": trace["candidate_retrieval"],
        "composition": json.loads(composition.model_dump_json()),
    }
    (out_dir / "e2e-smoke.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    by_id = {f.id: f for f in fragments}
    q1 = retrieval.q1_meaning.hits
    md = [
        f"# M2.6 — end-to-end smoke: {case['id']}", "",
        "raw input → Interpretation (M2.6) → **simulated confirmation** → retrieval M2.4 (unchanged) → Composition M2.5 (unchanged)", "",
        "## 1. Raw input", "", f"- topic: {case['topic']}", f"- experiences: {', '.join(case['experiences'])}",
        f"- difficulty_center: {case['difficulty_center']}", f"- narrative: {case['free_narrative']}", "",
        "## 2. Proposed question (shown to the user)", "", f"> {interpretation.proposed_question}", "",
        "## 3. Confirmation boundary", "",
        f"- action: `{confirmation.action}`, source: **`{confirmation.source}`** (simulated for this smoke test, not a user action)",
        f"- query provenance: origin `{query.provenance.origin}`, confirmed_question_source `{query.provenance.confirmed_question_source}`", "",
        "## 4. Retrieval (M2.4, meaning-v2)", "", "Q1 top-10:", "",
    ]
    md += [f"{h.rank}. {h.card_id} — {by_id[h.card_id].work}, {by_id[h.card_id].location} (cos {h.cosine:.3f})" for h in q1[:10]]
    md += ["", "STRUCTURE top-5: " + ", ".join(h.card_id for h in retrieval.structure.hits[:5]),
           f"Candidate union: {len(retrieval.candidate_union)} cards", "", "## 5. Composition (M2.5)", "", composition.user_text().rstrip(), "",
           f"Q1 top card {composition.q1_top.card_id}: {composition.q1_top.decision} — {composition.q1_top.reason}", ""]
    (out_dir / "E2E-SMOKE.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return record

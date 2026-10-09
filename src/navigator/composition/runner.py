"""M2.5 composition benchmark run over a recorded M2.4 retrieval run (resumable)."""

from __future__ import annotations

import datetime as dt
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from navigator.composition.composer import PACKAGE_VERSION, PROMPT_VERSION, Composer, build_package, compose
from navigator.models.composition import CompositionResult
from navigator.models.fragment import Fragment

DEFAULT_OUT = Path("reports/composition-runs")


def run_composition(traces: list[dict], fragments: list[Fragment], composer: Composer, out_dir: Path,
                    workers: int = 3) -> dict[str, CompositionResult]:
    (out_dir / "packages").mkdir(parents=True, exist_ok=True)
    (out_dir / "compositions").mkdir(parents=True, exist_ok=True)
    results: dict[str, CompositionResult] = {}
    todo = []
    for t in traces:
        pkg = build_package(t, fragments)
        (out_dir / "packages" / f"{t['item_id']}.json").write_text(json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        done = out_dir / "compositions" / f"{t['item_id']}.json"
        if done.exists():  # resume
            results[t["item_id"]] = CompositionResult.model_validate_json(done.read_text(encoding="utf-8"))
        else:
            todo.append(pkg)
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(compose, pkg, fragments, composer): pkg["item_id"] for pkg in todo}
        for fut in as_completed(futures):
            item = futures[fut]
            try:
                res = fut.result()
            except Exception as exc:  # recorded, run continues
                errors[item] = str(exc)[:800]
                continue
            (out_dir / "compositions" / f"{item}.json").write_text(res.model_dump_json(indent=2) + "\n", encoding="utf-8")
            results[item] = res
    (out_dir / "errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return results


def write_manifest(out_dir: Path, traces: list[dict], results: dict, composer: Composer) -> None:
    (out_dir / "run-manifest.json").write_text(
        json.dumps(
            {
                "run_id": out_dir.name,
                "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "retrieval_run_id": traces[0]["run_id"] if traces else None,
                "composer": composer.name,
                "model": composer.model,
                "package_version": PACKAGE_VERSION,
                "prompt_version": PROMPT_VERSION,
                "cases": len(traces),
                "composed": len(results),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def render_samples(results: dict[str, CompositionResult], traces: list[dict], bench_cases: dict,
                   fragments: list[Fragment], run_id: str) -> str:
    by_id = {f.id: f for f in fragments}
    lines = [
        "# M2.5 — Composition samples",
        "",
        f"Composition run: `{run_id}` · retrieval: M2.4 (`meaning-v2`). Composer: Claude via the local Claude Code CLI.",
        "",
        "Each answer is shown exactly as generated. Sources come from corpus metadata. "
        "`Why these cards` and rejected candidates are the composer's own recorded reasons.",
        "",
    ]
    for t in traces:
        item = t["item_id"]
        case = bench_cases[item]
        lines += [f"## {item}. {case.title}", "", f"**Ситуация:** {case.circumstance} · переживания: {', '.join(case.experiences)}", ""]
        lines += [f"**Confirmed question:** {t['candidate_retrieval']['query']['confirmed_question']}", ""]
        res = results.get(item)
        if res is None:
            lines += ["_Composition failed for this case (see errors.json)._", ""]
            continue
        q1 = [h["card_id"] for h in t["candidate_retrieval"]["q1_meaning"]["hits"]]
        sel = ", ".join(f"{p.card_id} (Q1 #{q1.index(p.card_id) + 1})" if p.card_id in q1 else f"{p.card_id} (STRUCTURE only)" for p in res.perspectives)
        lines += [f"**Selected ({len(res.perspectives)}):** {sel}", "", "---", "", res.user_text().rstrip(), "", "---", ""]
        lines += ["**Why these cards**", ""]
        for p in res.perspectives:
            lines.append(f"- {p.card_id} — *{p.role}*: {p.why_selected}")
        if res.fewer_than_three_reason:
            lines.append(f"- Only two perspectives: {res.fewer_than_three_reason}")
        lines += ["", f"**Q1 top card {res.q1_top.card_id}: {res.q1_top.decision}** — {res.q1_top.reason}", ""]
        if res.rejected:
            lines += ["**Notable rejected candidates**", ""]
            for r in res.rejected:
                f = by_id.get(r.card_id)
                rank = f"Q1 #{q1.index(r.card_id) + 1}" if r.card_id in q1 else "STRUCTURE"
                lines.append(f"- {r.card_id} ({rank}, {f.work if f else '?'}): {r.reason}")
            lines.append("")
    return "\n".join(lines) + "\n"

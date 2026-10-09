"""CLI (D50). Milestone 1 exposes only corpus commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from navigator.benchmark.build import BENCHMARK_JSON, write_benchmark
from navigator.benchmark.validator import summarize as summarize_benchmark
from navigator.benchmark.validator import validate_benchmark_file
from navigator.corpus.importer import write_corpus
from navigator.corpus.validator import summarize, validate_corpus_file

DEFAULT_CORPUS = Path("data/corpus/fragments.jsonl")
DEFAULT_MANIFEST = Path("data/corpus/launch-manifest.json")
DEFAULT_REPORT_DIR = Path("reports/validation")


def render_markdown(summary: dict, manifest: dict | None) -> str:
    launch, routes = summary["launch"], summary["routes"]
    out = [
        "# Corpus validation — machine summary",
        "",
        f"- status: **{summary['status']}** · index build allowed: **{summary['index_build_allowed']}**",
        f"- corpus: `{summary['corpus_path']}` · version `{summary['corpus_version']}` · sha256 `{(summary['corpus_sha256'] or '')[:16]}…`",
        f"- launch shortlist: {launch['launch_shortlist_count']} / expected {launch['expected_launch_shortlist_count']}",
        f"- retrieval universe (verified): {launch['retrieval_verified_count']}",
        f"- unresolved (excluded): {launch['unresolved_count']} — {', '.join(launch['unresolved_ids'])}",
        f"- unresolved set matches rule: {launch['unresolved_set_matches_rule']} · unresolved in retrieval universe: {launch['unresolved_in_retrieval_universe'] or 'none'}",
        f"- blocking codes: {', '.join(summary['blocking_codes']) or '—'}",
        "",
        "## Routes",
        "",
        f"- SOURCE: `{routes['SOURCE']['status']}` (Fragment with full text: {routes['SOURCE']['fragments_with_full_text']})",
        f"- MEANING: all inputs for {routes['MEANING']['eligible_with_all_inputs']} / {launch['retrieval_verified_count']}; "
        f"no inputs: {', '.join(routes['MEANING']['eligible_with_no_inputs']) or '—'}",
        f"- STRUCTURE: all inputs for {routes['STRUCTURE']['eligible_with_all_inputs']} / {launch['retrieval_verified_count']}",
        "",
        "## Retrieval readiness (113)",
        "",
        f"- MEANING states: {summary['readiness']['meaning_states']} · not usable: {', '.join(summary['readiness']['meaning_not_usable']) or '—'} · thin: {', '.join(summary['readiness']['meaning_thin']) or '—'}",
        f"- MEANING without Thought: {len(summary['readiness']['meaning_without_thought'])}",
        f"- STRUCTURE ready: {summary['readiness']['structure_ready']} / {summary['readiness']['retrieval_universe_count']} · not ready: {', '.join(summary['readiness']['structure_not_ready']) or '—'}",
        "",
        "## Issues by code",
        "",
        "| severity | code | count |",
        "|---|---|---|",
    ]
    for sev, codes in summary["issue_summary"].items():
        for code, n in sorted(codes.items(), key=lambda kv: -kv[1]):
            out.append(f"| {sev} | {code} | {n} |")
    out += ["", "## Field coverage", "", "| field | present (124) | missing (124) | present (113) | missing (113) |", "|---|---|---|---|---|"]
    all_cov, ret_cov = summary["field_coverage"]["all_124"], summary["field_coverage"]["retrieval_113"]
    for field, cov in all_cov.items():
        r = ret_cov[field]
        out.append(f"| {field} | {cov['present']} | {cov['missing']} | {r['present']} | {r['missing']} |")
    out += ["", "## First-29 recovery", "", "| id | batch | recovery_status | reconstructed | gaps |", "|---|---|---|---|---|"]
    for fid, r in summary["first_29_recovery"].items():
        out.append(
            f"| {fid} | {r['batch']} | {r['recovery_status']} | {', '.join(r['reconstructed_fields']) or '—'} | {', '.join(r['gaps']) or '—'} |"
        )
    if manifest:
        out += ["", "## Import notes (source cross-checks)", ""]
        for n in manifest.get("import_notes", []):
            if n["kind"] != "YAML_REPAIRED":
                out.append(f"- `{n['kind']}` {n['fragment_id'] or ''} — {n['detail']}")
        repaired = sum(1 for n in manifest.get("import_notes", []) if n["kind"] == "YAML_REPAIRED")
        out.append(f"- `YAML_REPAIRED` — {repaired} textual-pass blocks (prose list items quoted verbatim)")
    return "\n".join(out) + "\n"


def cmd_import(args: argparse.Namespace) -> int:
    corpus, manifest = write_corpus(Path(args.root), Path(args.out_dir), force=args.force)
    print(f"wrote {corpus}\nwrote {manifest}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    corpus, manifest_path = Path(args.corpus), Path(args.manifest)
    result = validate_corpus_file(corpus, manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    summary = summarize(result, corpus, manifest)
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "corpus-validation.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (report_dir / "corpus-validation.md").write_text(render_markdown(summary, manifest), encoding="utf-8")
    launch = summary["launch"]
    print(
        f"status={summary['status']} shortlist={launch['launch_shortlist_count']} "
        f"retrieval={launch['retrieval_verified_count']} unresolved={launch['unresolved_count']} "
        f"errors={len(result.errors)} warnings={len(result.warnings)} "
        f"index_build_allowed={summary['index_build_allowed']}"
    )
    return 0 if result.ok else 1


def cmd_build_benchmark(args: argparse.Namespace) -> int:
    print(f"wrote {write_benchmark(Path(args.root), force=args.force)}")
    return 0


def cmd_validate_benchmark(args: argparse.Namespace) -> int:
    path = Path(args.benchmark)
    issues, bench = validate_benchmark_file(path, Path(args.root))
    summary = summarize_benchmark(issues, bench, path)
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "benchmark-validation.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    errors = [i for i in issues if i.severity == "error"]
    print(f"status={summary['status']} cases={summary['counts']['cases']} pairs={summary['counts']['contrast_pairs']} errors={len(errors)}")
    for i in errors:
        print(f"  {i.code} {i.item or ''} {i.message}")
    return 0 if not errors else 1


def _load_fragments(corpus: Path):
    from navigator.models.fragment import Fragment

    return [Fragment.model_validate(json.loads(line)) for line in corpus.read_text(encoding="utf-8").splitlines()]


def _corpus_version(manifest: Path) -> str | None:
    return json.loads(manifest.read_text(encoding="utf-8")).get("corpus_version") if manifest.exists() else None


def cmd_export_meaning_docs(args: argparse.Namespace) -> int:
    from navigator.representations.meaning import MEANING_CARD_DOC_VERSION, meaning_card_documents

    docs = meaning_card_documents(_load_fragments(Path(args.corpus)))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for d in docs:
            fh.write(json.dumps({"card_id": d.key, "version": d.version, "sha256": d.sha256, "text": d.text}, ensure_ascii=False) + "\n")
    print(f"wrote {len(docs)} MEANING documents ({MEANING_CARD_DOC_VERSION}) to {out}")
    return 0


def _real_retriever(args: argparse.Namespace):
    from navigator.providers.embeddings import (
        LOCAL_EMBEDDING_CONFIG,
        OPENAI_EMBEDDING_CONFIG,
        EmbeddingUnavailable,
        make_client,
    )
    from navigator.retrieval.engine import CandidateRetriever

    config = OPENAI_EMBEDDING_CONFIG if args.embedding_provider == "openai" else LOCAL_EMBEDDING_CONFIG
    try:
        client = make_client(config)
    except EmbeddingUnavailable as exc:
        print(f"M2.2 empirical run not executed: {exc}")
        return None
    return CandidateRetriever(
        _load_fragments(Path(args.corpus)), client, cache_root=Path(args.cache_root),
        corpus_version=_corpus_version(Path(args.manifest)),
    )


def cmd_embed_meaning_cards(args: argparse.Namespace) -> int:
    retriever = _real_retriever(args)
    if retriever is None:
        return 2
    print(f"cached {len(retriever.card_ids)} MEANING card embeddings under {args.cache_root}")
    return 0


def cmd_run_benchmark_retrieval(args: argparse.Namespace) -> int:
    from navigator.benchmark.runner import write_run
    from navigator.models.benchmark import Benchmark

    retriever = _real_retriever(args)
    if retriever is None:
        return 2
    bench = Benchmark.model_validate(json.loads(Path(args.benchmark).read_text(encoding="utf-8")))
    print(f"wrote {write_run(bench, retriever, Path(args.runs_dir))}")
    return 0


def cmd_diagnose_retrieval(args: argparse.Namespace) -> int:
    """M2.3 diagnostics only; production retrieval, representations and caches are untouched."""
    import datetime as dt

    from navigator.diagnostics.retrieval_diagnosis import run_diagnosis, write_report
    from navigator.models.benchmark import Benchmark
    from navigator.providers.embeddings import LOCAL_EMBEDDING_CONFIG, EmbeddingUnavailable, make_client

    try:
        client = make_client(LOCAL_EMBEDDING_CONFIG)
    except EmbeddingUnavailable as exc:
        print(f"diagnosis not executed: {exc}")
        return 2
    traces = [json.loads(l) for l in (Path(args.baseline_run) / "traces.jsonl").read_text(encoding="utf-8").splitlines()]
    bench = Benchmark.model_validate(json.loads(Path(args.benchmark).read_text(encoding="utf-8")))
    result = run_diagnosis(_load_fragments(Path(args.corpus)), bench, traces, client, Path(args.diag_cache_root))
    result["meta"] = {
        "baseline_run": args.baseline_run,
        "embedding": client.config.public_dict(),
        "device": getattr(client, "device", None),
        "note": "diagnostic variants only; production M2.2 behaviour unchanged",
    }
    out = Path(args.out_root) / ("m2_3-retrieval-diagnosis-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    write_report(result, out)
    print(f"wrote {out}")
    return 0


def cmd_compare_runs(args: argparse.Namespace) -> int:
    """Reporting only: compare two recorded runs and render readable samples of the new one."""
    from navigator.benchmark.compare import compare_runs, load_traces, render_samples
    from navigator.models.benchmark import Benchmark

    fragments = _load_fragments(Path(args.corpus))
    new_dir = Path(args.new_run)
    new = load_traces(new_dir)
    comparison = compare_runs(load_traces(Path(args.old_run)), new, fragments)
    (new_dir / "comparison-vs-old.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bench = Benchmark.model_validate(json.loads(Path(args.benchmark).read_text(encoding="utf-8")))
    Path(args.samples_out).write_text(render_samples(new, fragments, {c.id: c for c in bench.cases}, new_dir.name), encoding="utf-8")
    print(f"wrote {new_dir / 'comparison-vs-old.json'} and {args.samples_out}")
    return 0


def cmd_compose_benchmark(args: argparse.Namespace) -> int:
    """M2.5 experimental composition over a recorded retrieval run (retrieval is not re-run)."""
    import datetime as dt

    from navigator.benchmark.compare import load_traces
    from navigator.composition.composer import ClaudeCodeCLIComposer
    from navigator.composition.runner import render_samples, run_composition, write_manifest
    from navigator.models.benchmark import Benchmark

    fragments = _load_fragments(Path(args.corpus))
    traces = load_traces(Path(args.retrieval_run))
    if args.only:
        traces = [t for t in traces if t["item_id"] in set(args.only.split(","))]
    out = Path(args.out) if args.out else Path("reports/composition-runs") / (
        "m2_5-composition-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    composer = ClaudeCodeCLIComposer(model=args.model)
    results = run_composition(traces, fragments, composer, out, workers=args.workers)
    write_manifest(out, traces, results, composer)
    bench = Benchmark.model_validate(json.loads(Path(args.benchmark).read_text(encoding="utf-8")))
    Path(args.samples_out).write_text(
        render_samples(results, traces, {c.id: c for c in bench.cases}, fragments, out.name), encoding="utf-8")
    print(f"composed {len(results)}/{len(traces)} → {out}; samples → {args.samples_out}")
    return 0 if len(results) == len(traces) else 1


def cmd_interpret_benchmark(args: argparse.Namespace) -> int:
    """M2.6 interpretation benchmark (Claude Code CLI, no API key)."""
    import datetime as dt

    from navigator.interpretation.interpreter import ClaudeCodeCLIInterpreter
    from navigator.interpretation.runner import load_benchmark, render_samples, run_interpretation

    bench = load_benchmark(Path(args.benchmark_file))
    cases = bench["cases"] + bench.get("edge_cases", [])
    if args.only:
        cases = [c for c in cases if c["id"] in set(args.only.split(","))]
    out = Path(args.out) if args.out else Path("reports/interpretation-runs") / (
        "m2_6-interpretation-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    results = run_interpretation(cases, ClaudeCodeCLIInterpreter(model=args.model), out, workers=args.workers)
    review = {k: v.get("human_review_notes", []) for k, v in bench.get("regression_expectations", {}).items()}
    Path(args.samples_out).write_text(render_samples(cases, results, out.name, review), encoding="utf-8")
    print(f"interpreted {len(results)}/{len(cases)} → {out}; samples → {args.samples_out}")
    return 0 if len(results) == len(cases) else 1


def cmd_prototype(args: argparse.Namespace) -> int:
    """M3 local browser prototype."""
    from navigator.prototype.server import serve

    serve(port=args.port, open_browser=not args.no_browser, corpus=args.corpus, final_mode=args.final_mode,
          retrieval_layer=None if args.retrieval_layer == "none" else args.retrieval_layer, pool_size=args.pool_size)
    return 0


def cmd_validate_final_corpus(args: argparse.Namespace) -> int:
    """Validate corpus/final-2026-10-07 (manifest + CORPUS-CONTRACT asserts on FINAL-CORPUS-ACTIVE-v1.csv)."""
    from navigator.corpus.final_corpus import FinalCorpusError, load_final_active, verify_manifest

    d = Path(args.dir)
    bad = verify_manifest(d)
    if bad:
        print("MANIFEST FAIL:\n- " + "\n- ".join(bad))
        return 1
    try:
        cards = load_final_active(d)
    except FinalCorpusError as exc:
        print(f"CONTRACT FAIL: {exc}")
        return 1
    print(f"status=PASS manifest=ok active={len(cards)} unique_ids={len({c.card_id for c in cards})}")
    return 0


def cmd_restore_full_corpus(args: argparse.Namespace) -> int:
    """Restore CORPUS-FULL-1090 into data/corpus-full (the 124 launch corpus in data/corpus is not touched)."""
    from navigator.corpus.full_restore import FULL_CORPUS_DIR, write_full

    m = write_full(Path(args.root))
    c = m["counts"]
    print(f"total={c['total']} eligible={c['retrieval_eligible']} status={c['by_status']} -> {FULL_CORPUS_DIR}")
    return 0


def cmd_audit_quotes(args: argparse.Namespace) -> int:
    """M3.3 quote-readiness audit of the retrieval-eligible cards (read-only over the corpus)."""
    from navigator.models.fragment import Fragment
    from navigator.quotes import INVENTORY_PATH, audit

    root = Path(args.root)
    fragments = [Fragment.model_validate(json.loads(l))
                 for l in (root / "data/corpus/fragments.jsonl").read_text(encoding="utf-8").splitlines()]
    inv = audit(fragments, root)
    out = root / INVENTORY_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(inv, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    c = inv["counts"]
    print(f"eligible={inv['total_eligible']} READY={c['READY']} PARTIAL={c['PARTIAL']} NOT_READY={c['NOT_READY']} -> {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="navigator")
    sub = parser.add_subparsers(dest="command", required=True)

    p_import = sub.add_parser("import-corpus", help="assemble data/corpus/fragments.jsonl from source documents")
    p_import.add_argument("--root", default=".")
    p_import.add_argument("--out-dir", default=str(DEFAULT_CORPUS.parent))
    p_import.add_argument("--force", action="store_true")
    p_import.set_defaults(func=cmd_import)

    p_val = sub.add_parser("validate-corpus", help="validate the canonical corpus and write reports")
    p_val.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    p_val.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    p_val.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    p_val.set_defaults(func=cmd_validate)

    p_bb = sub.add_parser("build-benchmark", help="transcribe the M2.1 benchmark spec into machine-readable JSON")
    p_bb.add_argument("--root", default=".")
    p_bb.add_argument("--force", action="store_true")
    p_bb.set_defaults(func=cmd_build_benchmark)

    p_vb = sub.add_parser("validate-benchmark", help="validate the machine-readable M2.1 benchmark")
    p_vb.add_argument("--benchmark", default=str(BENCHMARK_JSON))
    p_vb.add_argument("--root", default=".")
    p_vb.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    p_vb.set_defaults(func=cmd_validate_benchmark)

    p_ex = sub.add_parser("export-meaning-docs", help="write the deterministic MEANING card documents for inspection")
    p_ex.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    p_ex.add_argument("--out", default="data/retrieval/representations/meaning-card-docs.jsonl")
    p_ex.set_defaults(func=cmd_export_meaning_docs)

    for name, func, helptext in (
        ("embed-meaning-cards", cmd_embed_meaning_cards, "embed the 113 MEANING card documents into the local cache"),
        ("run-benchmark-retrieval", cmd_run_benchmark_retrieval, "M2.2 baseline run: 20 cases + contrast diagnostics"),
    ):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("--corpus", default=str(DEFAULT_CORPUS))
        sp.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
        sp.add_argument("--cache-root", default="data/retrieval/embeddings")
        sp.add_argument("--benchmark", default=str(BENCHMARK_JSON))
        sp.add_argument("--runs-dir", default="reports/benchmark-runs")
        sp.add_argument("--embedding-provider", choices=["local", "openai"], default="local")
        sp.set_defaults(func=func)

    p_dg = sub.add_parser("diagnose-retrieval", help="M2.3 retrieval diagnosis (diagnostic only)")
    p_dg.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    p_dg.add_argument("--benchmark", default=str(BENCHMARK_JSON))
    p_dg.add_argument("--baseline-run", default="reports/benchmark-runs/m2_2-baseline-20260927T102714Z")
    p_dg.add_argument("--diag-cache-root", default="data/retrieval/diagnostics-cache")
    p_dg.add_argument("--out-root", default="reports/diagnostics")
    p_dg.set_defaults(func=cmd_diagnose_retrieval)

    p_cr = sub.add_parser("compare-runs", help="compare two recorded benchmark runs; render readable samples")
    p_cr.add_argument("--old-run", required=True)
    p_cr.add_argument("--new-run", required=True)
    p_cr.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    p_cr.add_argument("--benchmark", default=str(BENCHMARK_JSON))
    p_cr.add_argument("--samples-out", default="reports/validation/M2.4-RETRIEVAL-SAMPLES.md")
    p_cr.set_defaults(func=cmd_compare_runs)

    p_cp = sub.add_parser("compose-benchmark", help="M2.5 experimental composition (Claude Code CLI, no API key)")
    p_cp.add_argument("--retrieval-run", default="reports/benchmark-runs/m2_4-meaning-separation-20260927T114629Z")
    p_cp.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    p_cp.add_argument("--benchmark", default=str(BENCHMARK_JSON))
    p_cp.add_argument("--out", default=None, help="existing run dir to resume")
    p_cp.add_argument("--only", default=None, help="comma-separated case ids")
    p_cp.add_argument("--model", default="claude-opus-5-5")
    p_cp.add_argument("--workers", type=int, default=3)
    p_cp.add_argument("--samples-out", default="reports/validation/M2.5-COMPOSITION-SAMPLES.md")
    p_cp.set_defaults(func=cmd_compose_benchmark)

    p_it = sub.add_parser("interpret-benchmark", help="M2.6 interpretation benchmark (Claude Code CLI)")
    p_it.add_argument("--benchmark-file", default="data/eval/interpretation/m2_6-interpretation-benchmark-v0.1.json")
    p_it.add_argument("--out", default=None)
    p_it.add_argument("--only", default=None)
    p_it.add_argument("--model", default="claude-opus-5-5")
    p_it.add_argument("--workers", type=int, default=3)
    p_it.add_argument("--samples-out", default="reports/validation/M2.6-INTERPRETATION-SAMPLES.md")
    p_it.set_defaults(func=cmd_interpret_benchmark)

    p_pr = sub.add_parser("prototype", help="M3: open the local browser prototype")
    p_pr.add_argument("--port", type=int, default=8770)
    p_pr.add_argument("--no-browser", action="store_true")
    p_pr.add_argument("--corpus", choices=["compact", "full", "final"], default="compact",
                      help="compact = 124 launch corpus (113 eligible, default); full = restored CORPUS-FULL-1090; "
                           "final = TEST mode on corpus/final-2026-10-07 (verified quotes shown)")
    p_pr.add_argument("--final-mode", choices=["A", "B", "C"], default="A",
                      help="final corpus retrieval document: A move / B move+quote / C diagnostic legacy metadata")
    p_pr.add_argument("--retrieval-layer", choices=["v1-block1", "none"], default="v1-block1",
                      help="final corpus, mode B: Retrieval Layer v1 (Block 1: Gita, Upanishads, Dao De Jing — "
                           "retrieval_text + quote instead of move + quote); none = plain mode B")
    p_pr.add_argument("--pool-size", type=int, choices=[15, 20, 25], default=20,
                      help="final corpus: candidates passed to the selection (max 3 per source); 15 = previous behaviour")
    p_pr.set_defaults(func=cmd_prototype)

    p_vf = sub.add_parser("validate-final-corpus", help="validate corpus/final-2026-10-07 against its contract")
    p_vf.add_argument("--dir", default="corpus/final-2026-10-07")
    p_vf.set_defaults(func=cmd_validate_final_corpus)

    p_rf = sub.add_parser("restore-full-corpus", help="restore CORPUS-FULL-1090 into data/corpus-full")
    p_rf.add_argument("--root", default=".")
    p_rf.set_defaults(func=cmd_restore_full_corpus)

    p_aq = sub.add_parser("audit-quotes", help="M3.3 quote-readiness audit (writes the inventory JSON)")
    p_aq.add_argument("--root", default=".")
    p_aq.set_defaults(func=cmd_audit_quotes)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

"""Final corpus 2026-10-07: retrieval experiment A / B / C (+ compact as reference). Nothing here chooses a mode.

usage:
  eval_final.py bench <out.json>            M2.1 benchmark (20 cases), real bge-m3: retrieval behaviour per mode
  eval_final.py cases <case,...> <out.json> product evaluation: one interpretation per case, then per mode
                                            retrieval → selection → writer + independent validator (full pipeline)

Selection sees the same card information in every mode (final fields only: move, verified quote, reference) —
only the retrieval document differs, so differences come from retrieval. Results are saved after every case.
"""
import json
import re
import sys
import time
from pathlib import Path

from navigator.benchmark.adapter import case_query
from navigator.composition.composer import (
    PROMPT_VERSION, ClaudeCodeCLIComposer, ComposerMeta, build_package, check_selection, compose_written, package_sha256,
)
from navigator.composition.grounding_validator import ClaudeCodeCLIValidator
from navigator.composition.references import fragment_reference
from navigator.composition.writer import ClaudeCodeCLIWriter
from navigator.corpus.final_corpus import FINAL_CORPUS_VERSION, final_snapshot_fragments, load_final_active
from navigator.interpretation.interpreter import ClaudeCodeCLIInterpreter, confirm, interpret, to_query_representation
from navigator.models.benchmark import Benchmark
from navigator.models.fragment import Fragment
from navigator.models.interpretation import InterpretationInput
from navigator.providers.embeddings import LocalSentenceTransformerClient
from navigator.prototype.flow import SHORT_QUOTE_WORDS
from navigator.prototype.server import ensure_claude_on_path
from navigator.representations.final_meaning import MODES, load_legacy, mode_snapshot
from navigator.representations.meaning import q1_text
from navigator.retrieval.engine import CandidateRetriever

OUT = Path("reports/final-corpus-eval")
SESSIONS = Path("reports/prototype-sessions")
INTERP_BENCH = Path("data/eval/interpretation/m2_6-interpretation-benchmark-v0.1.json")


def session_input(sid):
    return json.loads((SESSIONS / f"{sid}.json").read_text(encoding="utf-8"))["interpretation_input"]


def bench_input(cid):
    c = next(c for c in json.loads(INTERP_BENCH.read_text(encoding="utf-8"))["cases"] if c["id"] == cid)
    return {k: c[k] for k in ("topic", "experiences", "difficulty_center", "free_narrative")}


def projects_input():
    i = session_input("dbd44e5bd76f")  # the user's manual session (topic, feelings, difficulty)
    i["free_narrative"] = ("Я веду несколько проектов и не понимаю, продолжать так или остановиться на одном. Если выберу "
                           "один, боюсь, что денег не хватит или он мне наскучит, а если оставлю несколько, боюсь "
                           "выгореть. Как выбирать, когда у каждого пути свой страх и ни один не даёт гарантий?")
    return i


CASES = {
    "1-projects": projects_input,
    "2-limits-productivity": lambda: session_input("483f5633f57e"),
    "3-close-person-R03": lambda: bench_input("R03"),
    "4-R01": lambda: bench_input("R01"),
}

_W = re.compile(r"\w+")


def words(t):
    return {w for w in _W.findall((t or "").lower().replace("ё", "е")) if len(w) > 3}


def jacc(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def setup():
    final = final_snapshot_fragments(load_final_active())
    legacy = load_legacy()
    client = LocalSentenceTransformerClient()
    retr = {}
    for m in MODES:
        s = mode_snapshot(final, m, legacy)
        retr[m] = (CandidateRetriever(s.fragments, client, cache_root=Path("data/retrieval/embeddings-final"),
                                      corpus_version=FINAL_CORPUS_VERSION, card_docs=s.docs), s)
    compact = [Fragment.model_validate(json.loads(l)) for l in Path("data/corpus/fragments.jsonl").read_text(encoding="utf-8").splitlines()]
    retr["compact"] = (CandidateRetriever(compact, client, corpus_version="launch-124"), None)
    return final, compact, retr


def bench(out_file):
    final, compact, retr = setup()
    by = {f.id: f for f in final}
    b = Benchmark.model_validate(json.loads(Path("data/eval/benchmarks/m2_1-retrieval-benchmark-v0.1.json").read_text(encoding="utf-8")))
    rows = []
    for case in b.cases:
        q = case_query(case)
        qw = words(q1_text(q))
        rec = {"case": case.id, "title": case.title}
        for m, (r, snap) in retr.items():
            t = time.monotonic()
            res = r.retrieve(q, f"bench-{case.id}-{m}")
            sec = time.monotonic() - t
            docs = {d.key: d.text for d in r.card_docs}
            top = [h.card_id for h in res.q1_meaning.hits]
            rec[m] = {
                "seconds": round(sec, 3), "top15": top, "cos": [h.cosine for h in res.q1_meaning.hits],
                "structure_hits": len(res.structure.hits), "union": len(res.candidate_union),
                "doc_lexical": round(sum(jacc(qw, words(docs[c])) for c in top) / len(top), 4),
                "quote_lexical": round(sum(jacc(qw, words(by[c].fragment)) for c in top if c in by) /
                                       max(1, sum(1 for c in top if c in by)), 4),
            }
        rows.append(rec)
    (OUT / out_file).write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def card_view(p, f):
    q = {"text": f.fragment, "work": f.work, "location": f.location, "in_main": len(f.fragment.split()) <= SHORT_QUOTE_WORDS,
         "translator": f.translation, "edition": f.source}
    return {"card_id": p.card_id, "title": p.title, "source": fragment_reference(f), "main_idea": p.main_idea,
            "quote": q, "applied_insight": p.applied_insight, "reflection_question": p.reflection_question,
            "question_explanation": p.question_explanation, "details": p.perspective}


def cases(names, out_file):
    ensure_claude_on_path()
    final, _, retr = setup()
    by = {f.id: f for f in final}
    interpreter, composer = ClaudeCodeCLIInterpreter(), ClaudeCodeCLIComposer()
    results = []
    for name in names:
        i = CASES[name]()
        rec = {"case": name, "input": i}
        t = time.monotonic()
        interp = interpret(InterpretationInput(**i), interpreter)
        rec["interpretation_seconds"] = round(time.monotonic() - t, 2)
        rec["proposed_question"] = interp.proposed_question
        rec["working_hypotheses"] = interp.working_hypotheses
        query = to_query_representation(interp, confirm(interp, "confirmed"))
        for m in MODES:
            r, snap = retr[m]
            docs = {d.key: d.text for d in r.card_docs}
            run = {}
            t = time.monotonic()
            res = r.retrieve(query, f"{name}-{m}")
            run["retrieval_seconds"] = round(time.monotonic() - t, 3)
            run["top"] = [{"card_id": h.card_id, "rank": h.rank, "cosine": h.cosine, "source": fragment_reference(by[h.card_id]),
                           "move": by[h.card_id].technical.launch_philosophical_move,
                           "legacy_doc": h.card_id in set(snap.legacy_matched)} for h in res.q1_meaning.hits]
            run["structure_hits"] = [{"card_id": h.card_id, "rank": h.rank, "tensions": h.matched_tensions,
                                      "coordinates": h.matched_coordinates} for h in res.structure.hits]
            trace = {"item_id": f"{name}-{m}", "run_id": f"final-{m}", "candidate_retrieval": res.model_dump(mode="json")}
            pkg = build_package(trace, final)  # final fields only, identical across modes
            t = time.monotonic()
            output, usage = composer.complete(pkg)
            run["selection_seconds"] = round(time.monotonic() - t, 2)
            run["selection"] = output
            try:
                check_selection(pkg, output)
            except ValueError as exc:
                run["selection_error"] = str(exc)
                rec[m] = run
                continue
            meta = ComposerMeta(composer=composer.name, model=composer.model, prompt_version=PROMPT_VERSION,
                                package_sha256=package_sha256(pkg), attempts=1, usage={"calls": [usage], "repairs": []})
            t = time.monotonic()
            try:
                comp = compose_written(pkg, output, final, meta, ClaudeCodeCLIWriter(effort="medium"),
                                       validator=ClaudeCodeCLIValidator(effort="medium"))
                run["writing_seconds"] = round(time.monotonic() - t, 2)
                run["cards"] = [card_view(p, by[p.card_id]) for p in comp.perspectives]
                w = comp.meta.usage.get("writer") or {}
                run["writer"] = {"dropped": w.get("dropped"), "count_reason": comp.count_reason,
                                 "cards": [{"card_id": c["card_id"], "attempts": c["attempts"], "repairs": c["repairs"],
                                            "validation": [{"seconds": v["call_seconds"], "violations": v["violations"]}
                                                           for v in c.get("validation", [])]} for c in w.get("cards", [])]}
            except Exception as exc:  # recorded, not hidden
                run["writing_seconds"] = round(time.monotonic() - t, 2)
                run["writing_error"] = repr(exc)[:1500]
            run["total_seconds"] = round(run["retrieval_seconds"] + run["selection_seconds"] + run.get("writing_seconds", 0), 2)
            rec[m] = run
            print(name, m, "done", run.get("total_seconds"), run.get("writing_error", "")[:80], flush=True)
        results.append(rec)
        (OUT / out_file).write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1] == "bench":
        bench(sys.argv[2])
    else:
        cases(sys.argv[2].split(","), sys.argv[3])

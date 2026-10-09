"""BEFORE / AFTER of the temporary MVP retrieval diversity guardrail (final corpus, mode B) on 4 real cases.

BEFORE = the recorded real run (prototype session / cases-ABC-all.json, mode B): same confirmed question and hypotheses.
AFTER  = the same query representation → retrieval WITH the guardrail → real selection → writer + independent
         validator (claude CLI, the production prompts, 3 selection attempts as in the prototype).
The script first checks that retrieval WITHOUT the guardrail reproduces the recorded BEFORE pool exactly.
Results are saved after every case.

usage: eval_guardrail.py <out.json> [case,...]
"""
import json
import sys
import time
from pathlib import Path

from navigator.composition.composer import ClaudeCodeCLIComposer, build_package, compose
from navigator.composition.grounding_validator import ClaudeCodeCLIValidator
from navigator.composition.references import fragment_reference
from navigator.composition.writer import ClaudeCodeCLIWriter
from navigator.corpus.final_corpus import FINAL_CORPUS_VERSION, final_snapshot_fragments, load_final_active
from navigator.models.query import QueryProvenance, QueryRepresentation, UserContext
from navigator.providers.embeddings import LocalSentenceTransformerClient
from navigator.prototype.server import ensure_claude_on_path
from navigator.representations.final_meaning import mode_snapshot
from navigator.retrieval.diversity import SourceDiversityGuardrail
from navigator.retrieval.engine import CandidateRetriever

OUT = Path("reports/final-corpus-eval")
SESSIONS = Path("reports/prototype-sessions")


def from_session(sid):
    d = json.loads((SESSIONS / f"{sid}.json").read_text(encoding="utf-8"))
    comp = d["composition"]
    before = {"pool": comp["candidate_pool"], "selected": [p["card_id"] for p in comp["perspectives"]],
              "cards": [{"card_id": p["card_id"], "title": p["title"], "source": p["source"]} for p in comp["perspectives"]],
              "origin": f"reports/prototype-sessions/{sid}.json"}
    return QueryRepresentation.model_validate(d["query_representation"]), d["interpretation_input"], before


def r01():
    rec = next(r for r in json.loads((OUT / "cases-ABC-all.json").read_text(encoding="utf-8")) if r["case"] == "4-R01")
    i, run = rec["input"], rec["B"]
    q = QueryRepresentation(
        confirmed_question=rec["proposed_question"],
        context=UserContext(circumstance=i["topic"], narrative=i["free_narrative"]), experiences=i["experiences"],
        working_hypotheses=rec["working_hypotheses"],
        provenance=QueryProvenance(origin="production", confirmed_question_source="user_confirmed",
                                   interpretation_source="cases-ABC-all.json 4-R01 (m2_6 interpretation benchmark R01)"))
    before = {"pool": [t["card_id"] for t in run["top"]], "selected": [c["card_id"] for c in run["cards"]],
              "cards": [{"card_id": c["card_id"], "title": c["title"], "source": c["source"]} for c in run["cards"]],
              "origin": "reports/final-corpus-eval/cases-ABC-all.json 4-R01 mode B"}
    return q, i, before


CASES = {
    "A-loves-another": lambda: from_session("e9559bde9cf8"),
    "B-psychology-student": lambda: from_session("19e21efebc7e"),
    "C-wife-control": lambda: from_session("c1941dba2054"),
    "D-R01": r01,
}


def main(out_file, names):
    ensure_claude_on_path()
    final = final_snapshot_fragments(load_final_active())
    by = {f.id: f for f in final}
    snap = mode_snapshot(final, "B")
    client = LocalSentenceTransformerClient()
    kw = dict(cache_root=Path("data/retrieval/embeddings-final"), corpus_version=FINAL_CORPUS_VERSION, card_docs=snap.docs)
    plain = CandidateRetriever(snap.fragments, client, **kw)
    guarded = CandidateRetriever(snap.fragments, client, diversity_guardrail=SourceDiversityGuardrail(), **kw)
    out_path = OUT / out_file
    results = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else []
    for name in names:
        q, inp, before = CASES[name]()
        rec = {"case": name, "input": inp, "confirmed_question": q.confirmed_question,
               "working_hypotheses": q.working_hypotheses, "before": before}
        base = plain.retrieve(q, f"{name}-plain")
        rec["before_pool_reproduced"] = sorted(c.card_id for c in base.candidate_union) == sorted(before["pool"])
        t = time.monotonic()
        res = guarded.retrieve(q, f"{name}-guarded")
        rec["retrieval_seconds"] = round(time.monotonic() - t, 3)
        rec["after_pool"] = [{"card_id": h.card_id, "rank": h.rank, "cosine": h.cosine, "author": by[h.card_id].author,
                              "source": fragment_reference(by[h.card_id]),
                              "move": by[h.card_id].technical.launch_philosophical_move} for h in res.q1_meaning.hits]
        rec["guardrail"] = res.diversity_guardrail
        trace = {"item_id": f"guardrail-{name}", "run_id": "guardrail-after", "candidate_retrieval": res.model_dump(mode="json")}
        t = time.monotonic()
        try:
            comp = compose(build_package(trace, final), final, ClaudeCodeCLIComposer(), max_attempts=3,
                           writer=ClaudeCodeCLIWriter(effort="medium"), validator=ClaudeCodeCLIValidator(effort="medium"))
            rec["composition_seconds"] = round(time.monotonic() - t, 2)
            rec["after"] = {
                "selected": [p.card_id for p in comp.perspectives],
                "cards": [{"card_id": p.card_id, "author": by[p.card_id].author, "source": p.source, "title": p.title,
                           "main_idea": p.main_idea, "applied_insight": p.applied_insight,
                           "reflection_question": p.reflection_question, "details": p.perspective,
                           "perspective_effect": p.perspective_effect, "perspective_frame": p.perspective_frame}
                          for p in comp.perspectives],
                "count_reason": comp.count_reason,
                "rejected": [r.model_dump() for r in comp.rejected],
                "selection_repairs": comp.meta.usage.get("repairs", []),
                "selection_attempts": comp.meta.attempts,
                "same_author_dropped": (comp.meta.usage.get("writer") or {}).get("same_author_dropped"),
                "considered": (comp.meta.usage.get("writer") or {}).get("considered"),
            }
        except Exception as exc:  # recorded, not hidden
            rec["composition_seconds"] = round(time.monotonic() - t, 2)
            rec["after_error"] = repr(exc)[:3000]
        results = [r for r in results if r["case"] != name] + [rec]
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(name, "done", rec.get("composition_seconds"), rec.get("after_error", "")[:120], flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2].split(",") if len(sys.argv) > 2 else list(CASES))

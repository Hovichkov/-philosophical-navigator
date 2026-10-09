"""Retrieval Layer v1 / Block 1: BEFORE (mode B + guardrail, the recorded real runs) vs AFTER (mode B + layer +
guardrail, the same confirmed question and hypotheses → real selection → writer + independent validator).

usage: eval_retrieval_layer.py pools <out.json>            retrieval only, all known cases (fast, no model calls)
       eval_retrieval_layer.py compose <out.json> [case,...]  + real composition, saved after every case
"""
import json
import sys
import time
from pathlib import Path

from navigator.composition.composer import ClaudeCodeCLIComposer, build_package, compose
from navigator.composition.grounding_validator import ClaudeCodeCLIValidator
from navigator.composition.references import display_label
from navigator.composition.writer import ClaudeCodeCLIWriter
from navigator.corpus.final_corpus import FINAL_CORPUS_VERSION, final_snapshot_fragments, load_final_active
from navigator.models.query import QueryProvenance, QueryRepresentation, UserContext
from navigator.providers.embeddings import LocalSentenceTransformerClient
from navigator.prototype.server import ensure_claude_on_path
from navigator.representations.final_meaning import mode_snapshot
from navigator.representations.retrieval_layer import load_retrieval_layer
from navigator.retrieval.diversity import SourceDiversityGuardrail
from navigator.retrieval.engine import CandidateRetriever

OUT = Path("reports/final-corpus-eval")
SESSIONS = Path("reports/prototype-sessions")
CASES = {"роман": "84ec8453fdcf", "лекции": "9635439e65fd", "долги": "3f952b110d2c", "любит другого": "e9559bde9cf8",
         "студент": "19e21efebc7e", "жена": "c1941dba2054"}


def from_session(sid):
    d = json.loads((SESSIONS / f"{sid}.json").read_text(encoding="utf-8"))
    sel = [p["card_id"] for p in (d.get("composition") or {}).get("perspectives", [])]
    return QueryRepresentation.model_validate(d["query_representation"]), sel, f"reports/prototype-sessions/{sid}.json"


def r01():
    rec = next(r for r in json.loads((OUT / "cases-ABC-all.json").read_text(encoding="utf-8")) if r["case"] == "4-R01")
    i = rec["input"]
    q = QueryRepresentation(confirmed_question=rec["proposed_question"],
                            context=UserContext(circumstance=i["topic"], narrative=i["free_narrative"]),
                            experiences=i["experiences"], working_hypotheses=rec["working_hypotheses"],
                            provenance=QueryProvenance(origin="production", confirmed_question_source="user_confirmed",
                                                       interpretation_source="cases-ABC-all.json 4-R01"))
    ga = json.loads((OUT / "guardrail-before-after.json").read_text(encoding="utf-8"))
    before = next(r for r in ga if r["case"] == "D-R01")["after"]["selected"]  # B + guardrail, real run 2026-10-08
    return q, before, "guardrail-before-after.json D-R01 (B + guardrail)"


def queries():
    out = {name: from_session(sid) for name, sid in CASES.items()}
    out["R01"] = r01()
    return out


def setup():
    final = final_snapshot_fragments(load_final_active())
    client = LocalSentenceTransformerClient()
    kw = dict(cache_root=Path("data/retrieval/embeddings-final"), corpus_version=FINAL_CORPUS_VERSION,
              diversity_guardrail=SourceDiversityGuardrail())
    plain = mode_snapshot(final, "B")
    layered = mode_snapshot(final, "B", retrieval_layer=load_retrieval_layer(known_ids={f.id for f in final}))
    return final, {"before": CandidateRetriever(plain.fragments, client, card_docs=plain.docs, **kw),
                   "after": CandidateRetriever(layered.fragments, client, card_docs=layered.docs, **kw)}


def pool_view(res, by):
    return [{"rank": h.rank, "card_id": h.card_id, "source": display_label(by[h.card_id]),
             "move": by[h.card_id].technical.launch_philosophical_move} for h in res.q1_meaning.hits]


def main(cmd, out_file, names=None):
    final, retr = setup()
    by = {f.id: f for f in final}
    out_path = OUT / out_file
    results = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else []
    qs = queries()
    if cmd == "compose":
        ensure_claude_on_path()
    for name in names or list(qs):
        q, before_sel, origin = qs[name]
        rec = {"case": name, "origin": origin, "question": q.confirmed_question, "before_selected": before_sel}
        for k, r in retr.items():
            rec[f"{k}_pool"] = pool_view(r.retrieve(q, f"rl-{name}-{k}"), by)
        if cmd == "compose":
            res = retr["after"].retrieve(q, f"rl-{name}-after")
            trace = {"item_id": f"rl-{name}", "run_id": "retrieval-layer-v1", "candidate_retrieval": res.model_dump(mode="json")}
            t = time.monotonic()
            try:
                comp = compose(build_package(trace, final), final, ClaudeCodeCLIComposer(), max_attempts=3,
                               writer=ClaudeCodeCLIWriter(effort="medium"), validator=ClaudeCodeCLIValidator(effort="medium"))
                rec["after_selected"] = [p.card_id for p in comp.perspectives]
                rec["after_cards"] = [{"card_id": p.card_id, "source": display_label(by[p.card_id]), "comment": p.main_idea,
                                       "application": p.applied_insight, "question": p.reflection_question}
                                      for p in comp.perspectives]
                rec["considered"] = (comp.meta.usage.get("writer") or {}).get("considered")
            except Exception as exc:  # recorded, not hidden
                rec["after_error"] = repr(exc)[:2000]
            rec["composition_seconds"] = round(time.monotonic() - t, 1)
        results = [r for r in results if r["case"] != name] + [rec]
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(name, "done", rec.get("composition_seconds", ""), rec.get("after_error", "")[:100], flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3].split(",") if len(sys.argv) > 3 else None)

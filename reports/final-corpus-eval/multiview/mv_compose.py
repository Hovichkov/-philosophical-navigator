import sys, time; sys.path.insert(0, sys.argv[1])
from mv_setup import *
from navigator.composition.composer import ClaudeCodeCLIComposer, build_package, compose
from navigator.composition.grounding_validator import ClaudeCodeCLIValidator
from navigator.composition.writer import ClaudeCodeCLIWriter
from navigator.composition.references import display_label
from navigator.models.retrieval import CandidateRetrievalResult
from navigator.prototype.server import ensure_claude_on_path
ensure_claude_on_path()
out_path = Path(sys.argv[2]); variants = sys.argv[3].split(",")
results = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else []
idx = {c: i for i, c in enumerate(IDS)}
def make_pool(q, v):
    if v == "single20": return pool(fuse(q, "single"), 20)
    if v == "single25": return pool(fuse(q, "single"), 25)
    if v == "hybrid15+5": return hybrid(q, 20, core=15)
    raise ValueError(v)
for name, q in KNOWN.items():
    for v in variants:
        if any(r["case"] == name and r["variant"] == v for r in results): continue
        names, S, comb = scores(q); p = make_pool(q, v)
        base = R.retrieve(q, f"mv-{name}-{v}").model_dump(mode="json")
        best = {c: float(max(S[:, idx[c]].max(), comb[idx[c]])) for c in p}
        base["q1_meaning"]["top_k"] = len(p)
        base["q1_meaning"]["hits"] = [{"card_id": c, "rank": i + 1, "cosine": round(best[c], 6)} for i, c in enumerate(p)]
        base["candidate_union"] = [{"card_id": c, "found_by": ["Q1_MEANING"], "meaning_rank": i + 1, "meaning_score": round(best[c], 6),
                                    "structure_rank": None, "coordinate_overlap": None, "matched_coordinates": None,
                                    "tension_overlap": None, "matched_tensions": None, "operation": None}
                                   for i, c in sorted(enumerate(p), key=lambda x: x[1])]
        base.pop("diversity_guardrail", None)
        res = CandidateRetrievalResult.model_validate(base)
        trace = {"item_id": f"mv-{name}", "run_id": f"multiview-{v}", "candidate_retrieval": res.model_dump(mode="json")}
        rec = {"case": name, "variant": v, "pool": p}
        t = time.monotonic()
        try:
            comp = compose(build_package(trace, FINAL), FINAL, ClaudeCodeCLIComposer(), max_attempts=3,
                           writer=ClaudeCodeCLIWriter(effort="medium"), validator=ClaudeCodeCLIValidator(effort="medium"))
            rec["selected"] = [x.card_id for x in comp.perspectives]
            rec["cards"] = [{"card_id": x.card_id, "source": display_label(BY[x.card_id]), "comment": x.main_idea,
                             "application": x.applied_insight, "question": x.reflection_question} for x in comp.perspectives]
            rec["considered"] = (comp.meta.usage.get("writer") or {}).get("considered")
        except Exception as exc:
            rec["error"] = repr(exc)[:1500]
        rec["seconds"] = round(time.monotonic() - t, 1)
        results.append(rec)
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(name, v, rec.get("selected"), rec.get("error", "")[:80], rec["seconds"], flush=True)

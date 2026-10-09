"""M3.1 control run: replay recorded M3 prototype sessions (same input, same human confirmation
action and text) through the current prototype flow with the real Claude Code CLI + local bge-m3."""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from navigator.prototype.server import build_services, ensure_claude_on_path
from navigator.prototype.flow import Session

OUT = Path("reports/m3_1-control-run")
CASES = {"R01": "fa5146428783", "S2-son-outbursts": "94e9f19afb64", "S3-planning": "0cea5a1e196e", "S4-layoff": "77ad233e57d0"}

ensure_claude_on_path()
services = build_services()
services.retriever()


def run(name, sid):
    old = json.loads((Path("reports/prototype-sessions") / f"{sid}.json").read_text(encoding="utf-8"))
    i, c = old["interpretation_input"], old["confirmation"]
    s = Session(services, OUT / "sessions")
    t0 = time.time()
    rec = {"case": name, "replayed_from": sid, "session_id": s.id, "action": c["action"]}
    try:
        s.submit(i["topic"], i["experiences"], i["difficulty_center"], i["free_narrative"])
        rec["proposed_question"] = s.interpretation.proposed_question if s.interpretation else None
        text = None if c["action"] == "confirmed" else c["confirmed_question"]
        s.confirm(c["action"], text)
        t1 = time.time()
        view = s.answer()
        rec.update(confirmed_question=view["confirmed_question"], perspectives=view["perspectives"],
                   card_ids=[p.card_id for p in s.composition.perspectives],
                   old_card_ids=[p["card_id"] for p in old["composition"]["perspectives"]],
                   interpretation_attempts=s.interpretation.trace.attempts,
                   composition_attempts=s.composition.meta.attempts,
                   composition_repairs=s.composition.meta.usage.get("repairs", []),
                   seconds_interpret_confirm=round(t1 - t0), seconds_answer=round(time.time() - t1))
    except Exception as exc:
        rec["error"] = repr(exc)[:2000]
        rec["session_errors"] = s.errors
    print(name, "done", rec.get("error", "ok"), flush=True)
    return rec


with ThreadPoolExecutor(2) as ex:
    results = list(ex.map(lambda kv: run(*kv), CASES.items()))
(OUT / "control-run.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

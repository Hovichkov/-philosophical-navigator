"""M3.2 control run: replay recorded prototype sessions through the current flow with the real
Claude Code CLI + local bge-m3, staged (retrieve → compose), with M3.2 property checks.

Confirmation policy: the confirmed question is held equal to the recorded human one. If the new
proposal equals it → «confirmed»; otherwise the recorded action is replayed with the recorded text
(«edited» / «replaced»); for a recorded «confirmed» that now differs, «edited» with the recorded text.
"""
import json, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from navigator.composition.quality import failed, property_checks
from navigator.prototype.flow import Session
from navigator.prototype.server import build_services, ensure_claude_on_path

OUT = Path("reports/m3_2-control-run")
REF = {c["id"]: c for c in json.loads(Path("tests/fixtures/m3_2_reference_cases.json").read_text(encoding="utf-8"))["cases"]}
CASES = {"A-son-guilt-control": "94e9f19afb64", "B-meaningful-work-money-debt": "1067f8377ca7",
         "R01": "fa5146428783", "S3-planning": "0cea5a1e196e", "S4-layoff": "77ad233e57d0"}

import sys
ONLY = sys.argv[1].split(",") if len(sys.argv) > 1 else None  # rerun a subset: replay.py A-...,B-...
OUT_FILE = sys.argv[2] if len(sys.argv) > 2 else "control-run.json"
if ONLY:
    CASES = {k: v for k, v in CASES.items() if k in ONLY}

ensure_claude_on_path()
services = build_services()
services.retriever()


def run(name, sid):
    old = json.loads((Path("reports/prototype-sessions") / f"{sid}.json").read_text(encoding="utf-8"))
    i, c = old["interpretation_input"], old["confirmation"]
    s = Session(services, OUT / "sessions")
    rec = {"case": name, "replayed_from": sid, "session_id": s.id}
    try:
        t0 = time.time()
        s.submit(i["topic"], i["experiences"], i["difficulty_center"], i["free_narrative"])
        rec["proposed_question"] = s.interpretation.proposed_question
        rec["interpretation_seconds"] = round(time.time() - t0)
        target = c["confirmed_question"]
        if name == "R01":
            action, text = "confirmed", None  # R01 is replayed as «Да» on whatever is proposed
        elif rec["proposed_question"] == target:
            action, text = "confirmed", None
        else:
            action, text = ("edited" if c["action"] == "confirmed" else c["action"]), target
        s.confirm(action, text)
        rec["action"] = action
        t1 = time.time(); s.retrieve(); t2 = time.time()
        view = s.compose(); t3 = time.time()
        checks = property_checks(s.composition, services.fragments, REF.get(name, {}).get("not_in_user_words", []))
        rec.update(confirmed_question=view["confirmed_question"], perspectives=view["perspectives"],
                   card_ids=[p.card_id for p in s.composition.perspectives],
                   distinctions=[p.distinction for p in s.composition.perspectives],
                   fewer_than_three_reason=s.composition.fewer_than_three_reason,
                   old_card_ids=[p["card_id"] for p in old["composition"]["perspectives"]],
                   composition_attempts=s.composition.meta.attempts,
                   composition_repairs=s.composition.meta.usage.get("repairs", []),
                   rejected=[r.model_dump() for r in s.composition.rejected],
                   retrieve_seconds=round(t2 - t1, 1), compose_seconds=round(t3 - t2),
                   checks_failed=failed(checks), checks_total=len(checks))
    except Exception as exc:
        rec["error"] = repr(exc)[:2000]
        rec["session_errors"] = s.errors
    print(name, "done", rec.get("error", "ok"), flush=True)
    return rec


with ThreadPoolExecutor(2) as ex:
    results = list(ex.map(lambda kv: run(*kv), CASES.items()))
(OUT / OUT_FILE).write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

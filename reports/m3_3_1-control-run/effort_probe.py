"""M3.3.1 probe: same card brief written at different `--effort` levels (time, tokens, checks, text)."""
import json, sys, time
from pathlib import Path
from navigator.composition.composer import build_package, source_label
from navigator.composition.writer import ClaudeCodeCLIWriter, build_brief, check_card, user_words_from_package
from navigator.models.fragment import Fragment
from navigator.prototype.server import ensure_claude_on_path

ensure_claude_on_path()
frags = [Fragment.model_validate(json.loads(l)) for l in Path("data/corpus/fragments.jsonl").read_text(encoding="utf-8").splitlines()]
by = {f.id: f for f in frags}
run = json.load(open("reports/m3_3_1-control-run/control-after.json"))[1]  # B-son
sess = json.load(open(f"reports/m3_3_1-control-run/sessions/{run['session_id']}.json"))
pkg = build_package({"item_id": "probe", "run_id": "probe", "candidate_retrieval": sess["retrieval"]}, frags)
sel = run["writer"]["selection"]
card = next(s for s in sel if s["card_id"] == sys.argv[1])
brief = build_brief(pkg, card, [s for s in sel if s is not card], by[card["card_id"]])
out = []
for effort in sys.argv[2].split(","):
    w = ClaudeCodeCLIWriter(effort=None if effort == "default" else effort)
    t = time.monotonic()
    fields, usage = w.complete(brief)
    try:
        check_card(card["card_id"], fields, card, source_label(by[card["card_id"]]), user_words_from_package(pkg)); ok = "ok"
    except ValueError as e:
        ok = str(e)[:200]
    out.append({"effort": effort, "seconds": round(time.monotonic() - t, 1), "output_tokens": usage["output_tokens"],
                "thinking_tokens": usage["thinking_tokens"], "check": ok, "fields": fields})
    print(effort, out[-1]["seconds"], usage["output_tokens"], usage["thinking_tokens"], ok, flush=True)
Path(f"reports/m3_3_1-control-run/effort-probe-{card['card_id']}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

"""M3.3.1 control/measurement run: replay recorded prototype sessions through the CURRENT prototype flow
(real Claude Code CLI + local bge-m3), sequentially (no parallel sessions, so timings are not contaminated),
answering «Да» on whatever is proposed now, and keep the full user-facing text + per-stage timings.

usage: replay.py <case,case,...> <out.json>
"""
import json, sys, time
from pathlib import Path

from navigator.prototype.flow import Session
from navigator.prototype.server import build_services, ensure_claude_on_path

OUT = Path("reports/m3_3_1-control-run")
CASES = {
    "A-productivity": "483f5633f57e",  # the user's latest manual productivity session (M3.3)
    "B-son": "79c1111a1710",            # the user's M3.3 manual son session (R01 narrative)
    "C-R01": "fa5146428783",
    "D-layoff": "77ad233e57d0",         # not productivity / parenting / reference-card topics
    "E-teacher": "62eb82de110a",        # the user's own case that failed with a CLI error on 2026-09-28
    "F-projects": "dbd44e5bd76f",       # M3.4 manual test: three cards doing one job (several projects)
}
# Inputs written for a control run (no recorded session). M3.4.2 transfer: facts + feeling, the cause not explained,
# gender-neutral wording — an attractive but unconfirmed psychological explanation (envy, hurt pride) is easy to make.
INLINE = {
    "G-friend-promotion": {
        "topic": "Отношения с близким человеком",
        "experiences": ["Раздражение", "Растерянность", "Грусть"],
        "difficulty_center": "Я не понимаю, что со мной происходит",
        "free_narrative": ("Мы дружим с Андреем пятнадцать лет и работаем в одной компании. Месяц назад повышение, на "
                           "которое претендовали мы оба, получил он. Поздравлять было несложно. Но с тех пор мне тяжело "
                           "с ним разговаривать: отвечаю коротко, отказываюсь от обедов вместе, раздражаюсь на мелочи. "
                           "Не понимаю, что со мной происходит, и мне от этого неловко."),
    },
}
names = sys.argv[1].split(",")
out_file = sys.argv[2]

ensure_claude_on_path()
services = build_services()
services.retriever()

results = []
for name in names:
    if name in INLINE:
        sid, i = None, INLINE[name]
    else:
        sid = CASES[name]
        i = json.loads((Path("reports/prototype-sessions") / f"{sid}.json").read_text(encoding="utf-8"))["interpretation_input"]
    s = Session(services, OUT / "sessions")
    rec = {"case": name, "replayed_from": sid, "session_id": s.id, "user_situation": i}
    t0 = time.monotonic()
    try:
        s.submit(i["topic"], i["experiences"], i["difficulty_center"], i["free_narrative"])
        rec["proposed_question"] = s.interpretation.proposed_question
        s.confirm("confirmed")
        s.retrieve()
        view = s.compose()
        rec.update(view=view, card_ids=[p.card_id for p in s.composition.perspectives],
                   distinctions=[p.distinction for p in s.composition.perspectives],
                   writer=s.composition.meta.usage.get("writer"),
                   fewer_than_three_reason=s.composition.fewer_than_three_reason,
                   count_reason=s.composition.count_reason,
                   perspective_effects=[p.perspective_effect for p in s.composition.perspectives],
                   perspective_frames=[p.perspective_frame for p in s.composition.perspectives],
                   candidate_pool=s.composition.candidate_pool,
                   rejected=[r.model_dump() for r in s.composition.rejected])
    except Exception as exc:
        rec["error"] = repr(exc)[:2000]
        rec["session_errors"] = s.errors
    rec["timings"] = s.timings
    rec["total_seconds"] = round(time.monotonic() - t0, 1)
    print(name, "done", rec.get("error", "ok"), rec["total_seconds"], flush=True)
    results.append(rec)
    # saved after every case: an interrupted run or a plan limit keeps the cases already finished
    (OUT / out_file).write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

"""Full-corpus restoration A/B: compact (124 / 113 eligible) vs restored full (1090 / 815 eligible).

Per case: ONE interpretation (the same confirmed question and QueryRepresentation for both corpora), then
retrieval + selection on each corpus with everything else identical (same model, same prompts, same top_k).
Cards are written only when asked (``--write CASE``), on the full corpus, from the full-corpus selection.
Results are saved after every case.

usage: ab_run.py <case,case,...> <out.json> [--write CASE]
"""
import json
import sys
import time
from pathlib import Path

from navigator.composition.composer import (
    PROMPT_VERSION, ComposerMeta, ClaudeCodeCLIComposer, build_package, check_selection, compose_written, package_sha256,
)
from navigator.composition.grounding_validator import ClaudeCodeCLIValidator
from navigator.composition.writer import ClaudeCodeCLIWriter
from navigator.interpretation.interpreter import ClaudeCodeCLIInterpreter, confirm, interpret, to_query_representation
from navigator.models.fragment import Fragment
from navigator.models.interpretation import InterpretationInput
from navigator.providers.embeddings import LocalSentenceTransformerClient
from navigator.representations.meaning import meaning_card_text
from navigator.retrieval.engine import CandidateRetriever
from navigator.prototype.server import ensure_claude_on_path

OUT = Path("reports/full-corpus-ab")
CASES = {
    "W-wife": {"topic": "Отношения с близким человеком", "experiences": ["Страх", "Тревогу"],
               "difficulty_center": "Мне трудно принять происходящее таким, какое оно сейчас есть",
               "free_narrative": ("Моя жена идёт учиться на психоаналитика, и я боюсь, что она там влюбится. Я понимаю, "
                                  "что это от меня не зависит и что наша любовь сильнее, но не знаю, как это принять. "
                                  "Как мне найти в себе мужество принять это?")},
    "G-friend-promotion": {"topic": "Отношения с близким человеком", "experiences": ["Раздражение", "Растерянность", "Грусть"],
                           "difficulty_center": "Я не понимаю, что со мной происходит",
                           "free_narrative": ("Мы дружим с Андреем пятнадцать лет и работаем в одной компании. Месяц назад "
                                              "повышение, на которое претендовали мы оба, получил он. Поздравлять было "
                                              "несложно. Но с тех пор мне тяжело с ним разговаривать: отвечаю коротко, "
                                              "отказываюсь от обедов вместе, раздражаюсь на мелочи. Не понимаю, что со мной "
                                              "происходит, и мне от этого неловко.")},
}
SESSIONS = {"F-projects": "dbd44e5bd76f", "D-layoff": "77ad233e57d0", "E-teacher": "62eb82de110a",
            "A-productivity": "483f5633f57e", "B-son": "79c1111a1710"}


def load(path):
    return [Fragment.model_validate(json.loads(l)) for l in Path(path).read_text(encoding="utf-8").splitlines()]


def case_input(name):
    if name in CASES:
        return CASES[name]
    return json.loads((Path("reports/prototype-sessions") / f"{SESSIONS[name]}.json").read_text(encoding="utf-8"))["interpretation_input"]


def retrieval_view(res, frags_by_id):
    q1 = {h.card_id: h for h in res.q1_meaning.hits}
    st = {h.card_id: h for h in res.structure.hits}
    out = []
    for c in res.candidate_union:
        f = frags_by_id[c.card_id]
        out.append({"card_id": c.card_id, "found_by": c.found_by, "meaning_rank": c.meaning_rank,
                    "meaning_cosine": c.meaning_score, "structure_rank": c.structure_rank,
                    "matched_coordinates": c.matched_coordinates, "matched_tensions": c.matched_tensions,
                    "source": f"{f.work}, {f.location}", "status": f.technical.operational_status,
                    "meaning_doc": meaning_card_text(f), "move": f.technical.launch_philosophical_move})
    return sorted(out, key=lambda x: (x["meaning_rank"] or 99, x["structure_rank"] or 99))


def main():
    names = sys.argv[1].split(",")
    out_file = sys.argv[2]
    write_case = sys.argv[sys.argv.index("--write") + 1] if "--write" in sys.argv else None
    ensure_claude_on_path()
    corpora = {"compact": (load("data/corpus/fragments.jsonl"), "data/retrieval/embeddings", "launch-124"),
               "full": (load("data/corpus-full/fragments.jsonl"), "data/retrieval/embeddings-full", "corpus-full/1.0.0")}
    client = LocalSentenceTransformerClient()
    retrievers = {k: CandidateRetriever(f, client, cache_root=Path(c), corpus_version=v) for k, (f, c, v) in corpora.items()}
    interpreter, composer = ClaudeCodeCLIInterpreter(), ClaudeCodeCLIComposer()
    results = []
    for name in names:
        rec = {"case": name, "input": case_input(name)}
        i = rec["input"]
        inp = InterpretationInput(topic=i["topic"], experiences=i["experiences"], difficulty_center=i["difficulty_center"],
                                  free_narrative=i["free_narrative"])
        t = time.monotonic()
        interp = interpret(inp, interpreter)
        rec["interpretation_seconds"] = round(time.monotonic() - t, 2)
        rec["proposed_question"] = interp.proposed_question
        rec["working_hypotheses"] = interp.working_hypotheses
        rec["coordinates"], rec["canonical_tensions"] = interp.coordinates, interp.canonical_tensions
        query = to_query_representation(interp, confirm(interp, "confirmed"))
        for corpus, (frags, _, _) in corpora.items():
            by_id = {f.id: f for f in frags}
            t = time.monotonic()
            res = retrievers[corpus].retrieve(query, f"ab-{name}-{corpus}")
            r_sec = round(time.monotonic() - t, 3)
            trace = {"item_id": f"ab-{name}-{corpus}", "run_id": f"ab-{corpus}",
                     "candidate_retrieval": res.model_dump(mode="json")}
            pkg = build_package(trace, frags)
            t = time.monotonic()
            output, usage = composer.complete(pkg)
            s_sec = round(time.monotonic() - t, 2)
            try:
                sel = check_selection(pkg, output)
                sel_error = None
            except ValueError as exc:
                sel, sel_error = None, str(exc)
            rec[corpus] = {"retrieval_seconds": r_sec, "selection_seconds": s_sec, "selection_usage": usage,
                           "universe": res.retrieval_universe_size, "candidates": retrieval_view(res, by_id),
                           "selection": output, "selection_error": sel_error}
            if corpus == "full" and name == write_case and sel:
                meta = ComposerMeta(composer=composer.name, model=composer.model, prompt_version=PROMPT_VERSION,
                                    package_sha256=package_sha256(pkg), attempts=1, usage={"calls": [usage], "repairs": []})
                t = time.monotonic()
                comp = compose_written(pkg, output, frags, meta, ClaudeCodeCLIWriter(effort="medium"),
                                       validator=ClaudeCodeCLIValidator(effort="medium"))
                rec["full"]["writing_seconds"] = round(time.monotonic() - t, 2)
                from navigator.composition.references import fragment_reference
                rec["full"]["cards"] = [{"card_id": p.card_id, "title": p.title,
                                         "source": fragment_reference(by_id[p.card_id]), "main_idea": p.main_idea,
                                         "applied_insight": p.applied_insight, "reflection_question": p.reflection_question,
                                         "question_explanation": p.question_explanation, "details": p.perspective}
                                        for p in comp.perspectives]
                rec["full"]["writer"] = comp.meta.usage.get("writer")
        print(name, "done", {k: (rec[k]["retrieval_seconds"], rec[k]["selection_seconds"]) for k in corpora}, flush=True)
        results.append(rec)
        (OUT / out_file).write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

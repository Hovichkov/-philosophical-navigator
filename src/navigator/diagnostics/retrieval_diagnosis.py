"""M2.3 retrieval diagnosis — DIAGNOSTIC ONLY.

Reproduces the M2.2 baseline, so it deliberately uses the LEGACY M2.2 formats
(``meaning_card_text_v1``, ``q1_text_v1``), not the current M2.4 MEANING spec.

Builds temporary document/query variants and measures retrieval statistics with
the same embedding model and cosine ranking as the M2.2 baseline. Nothing here
is used by production retrieval; production representations, caches and
ranking are never modified (diagnostic embeddings use a separate cache root and
``diag-*`` versions).
"""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from navigator.benchmark.adapter import case_query
from navigator.corpus.readiness import meaning_inputs, retrieval_universe, structure_inputs
from navigator.embeddings.cache import EmbeddingCache
from navigator.models.benchmark import Benchmark
from navigator.models.fragment import Fragment
from navigator.models.query import QueryRepresentation
from navigator.models.vocabularies import TENSION_QUALIFIER
from navigator.providers.embeddings import EmbeddingClient
from navigator.representations.meaning import Representation, meaning_card_text_v1 as meaning_card_text, q0_text, q1_text_v1 as q1_text
from navigator.retrieval.routes import cosine_rank

TOP_K = 15
DIAG_PREFIX = "diag-m2.3"

# Template scaffolding of the textual-pass cards (see M1.5 readiness / M2.2 closeout).
PERSPECTIVE_TEMPLATE = "Рассмотреть ситуацию через операцию, которую задаёт сам фрагмент:"
QUESTION_TEMPLATE = "Какой философский ход совершает текст в ситуации:"


# ------------------------------------------------------------------ document variants


def _strip(t: str) -> str:
    return t[: -len(TENSION_QUALIFIER)] if t.endswith(TENSION_QUALIFIER) else t


def _lines(f: Fragment, *, perspective=False, questions=False, coordinates=False, tensions=False,
           drop_generic: set[str] | None = None, strip_templates=False) -> str:
    """Same line format as the production MEANING document, restricted to chosen fields."""
    m, s = meaning_inputs(f), structure_inputs(f)
    out: list[str] = []
    if perspective:
        for p in m.get("perspective", []):
            if strip_templates:
                p = p.replace(PERSPECTIVE_TEMPLATE, "").strip()
            out.append(f"Перспектива: {p}")
    if questions:
        qs = [q for q in m.get("philosophical_questions", []) if not (drop_generic and q in drop_generic)]
        if strip_templates:
            qs = [q.replace(QUESTION_TEMPLATE, "").strip() for q in qs]
        if qs:
            out.append("Философские вопросы:")
            out.extend(f"- {q}" for q in qs)
    if coordinates and s.get("coordinates"):
        out.append("Координаты: " + "; ".join(s["coordinates"]))
    if tensions and s.get("tensions"):
        out.append("Напряжения: " + "; ".join(_strip(t) for t in s["tensions"]))
    return "\n".join(out)


@dataclass(frozen=True)
class DocVariant:
    id: str
    description: str
    build: object  # callable(Fragment, generic_questions) -> str


DOC_VARIANTS: list[DocVariant] = [
    DocVariant("A_perspective", "perspective only", lambda f, g: _lines(f, perspective=True)),
    DocVariant("B_questions", "philosophical_questions only", lambda f, g: _lines(f, questions=True)),
    DocVariant("C_persp_questions", "perspective + philosophical_questions",
               lambda f, g: _lines(f, perspective=True, questions=True)),
    DocVariant("D_full", "current full MEANING (perspective + questions + coordinates + tensions)",
               lambda f, g: meaning_card_text(f)),
    DocVariant("E_full_no_tensions", "full MEANING without the tensions line (tests the tension-overlap hypothesis)",
               lambda f, g: _lines(f, perspective=True, questions=True, coordinates=True)),
    DocVariant("F_full_detemplated", "full MEANING with generic questions and template prefixes removed "
               "(tests the template-dilution hypothesis)",
               lambda f, g: _lines(f, perspective=True, questions=True, coordinates=True, tensions=True,
                                   drop_generic=g, strip_templates=True)),
    DocVariant("G_coords_tensions", "coordinates + tensions only (structural vocabulary alone)",
               lambda f, g: _lines(f, coordinates=True, tensions=True)),
]


def generic_questions(fragments: list[Fragment]) -> set[str]:
    counts = Counter(q for f in fragments for q in f.philosophical_questions or [])
    return {q for q, n in counts.items() if n > 1}


def build_doc_variant(variant: DocVariant, universe: list[Fragment]) -> dict[str, str]:
    g = generic_questions(universe)
    return {f.id: variant.build(f, g) for f in sorted(universe, key=lambda x: x.id)}


# ------------------------------------------------------------------ query variants


def query_variants(q: QueryRepresentation) -> dict[str, str]:
    tensions = [*q.canonical_tensions, *q.free_tensions]
    hyp = "Рабочие интерпретации:\n" + "\n".join(f"- {h}" for h in q.working_hypotheses)
    ten = ("Смысловые напряжения:\n" + "\n".join(f"- {t}" for t in tensions)) if tensions else ""
    base = f"Вопрос: {q.confirmed_question}"
    return {
        "Q0_question_only": q0_text(q),
        "QH_question_hypotheses": f"{base}\n{hyp}",
        "QT_question_tensions": f"{base}\n{ten}".strip(),
        "Q1_full": q1_text(q),
        "QTonly_tensions_only": ten or base,
    }


# ------------------------------------------------------------------ metrics


def gini(values: list[int]) -> float:
    xs = sorted(values)
    n, total = len(xs), sum(xs)
    if n == 0 or total == 0:
        return 0.0
    cum = sum((i + 1) * x for i, x in enumerate(xs))
    return round((2 * cum) / (n * total) - (n + 1) / n, 4)


def ranking_stats(rankings: dict[str, list[str]], universe_ids: list[str], recovered: set[str],
                  baseline: dict[str, list[str]] | None = None, focus: str = "C0056") -> dict:
    slots = [cid for ids in rankings.values() for cid in ids]
    freq = Counter(slots)
    all_freq = [freq.get(cid, 0) for cid in universe_ids]
    top10_share = sum(n for _, n in freq.most_common(10)) / len(slots) if slots else 0.0
    out = {
        "cases": len(rankings),
        "slots": len(slots),
        "recovered_share": round(sum(1 for c in slots if c in recovered) / len(slots), 4) if slots else None,
        "recovered_base_share": round(len(recovered & set(universe_ids)) / len(universe_ids), 4),
        "unique_cards": len(freq),
        "universe": len(universe_ids),
        "gini": gini(all_freq),
        "top10_cards_slot_share": round(top10_share, 4),
        "focus_card": focus,
        "focus_frequency": freq.get(focus, 0),
        "top_frequencies": freq.most_common(15),
        "frequency_histogram": dict(sorted(Counter(all_freq).items())),
    }
    out["recovered_per_case"] = {k: sum(1 for c in v if c in recovered) for k, v in rankings.items()}
    if baseline is not None:
        ov = [len(set(rankings[k]) & set(baseline[k])) / max(1, len(baseline[k])) for k in rankings if k in baseline]
        out["mean_overlap_with_baseline"] = round(statistics.mean(ov), 4) if ov else None
    return out


def rank_all(query_vecs: dict[str, np.ndarray], card_ids: list[str], card_vecs: np.ndarray, top_k: int = TOP_K) -> dict[str, list[str]]:
    return {k: [h.card_id for h in cosine_rank(v, card_ids, card_vecs, top_k)] for k, v in query_vecs.items()}


def doc_statistics(texts: dict[str, str], group: set[str]) -> dict:
    def summary(xs: list[float]) -> dict:
        xs = sorted(xs)
        return {"min": xs[0], "p25": xs[len(xs) // 4], "median": statistics.median(xs), "p75": xs[(3 * len(xs)) // 4],
                "max": xs[-1], "mean": round(statistics.mean(xs), 2)}

    def per(ids):
        words = {k: re.findall(r"\w+", texts[k].lower()) for k in ids}
        return {
            "n": len(ids),
            "chars": summary([len(texts[k]) for k in ids]),
            "words": summary([len(words[k]) for k in ids]),
            "type_token_ratio": summary([round(len(set(w)) / max(1, len(w)), 3) for w in words.values()]),
        }

    ids = sorted(texts)
    return {"recovered": per([k for k in ids if k in group]), "other": per([k for k in ids if k not in group])}


def repeated_patterns(texts: dict[str, str], group: set[str], min_cards: int = 2) -> list[dict]:
    """Lines and template prefixes shared by several documents, with their footprint."""
    line_cards: dict[str, set[str]] = {}
    for cid, t in texts.items():
        for line in set(t.split("\n")):
            line_cards.setdefault(line, set()).add(cid)
    out = []
    for line, cards in line_cards.items():
        if len(cards) >= min_cards:
            out.append({"pattern": line, "kind": "identical_line", "cards": len(cards),
                        "recovered_cards": len(cards & group), "other_cards": len(cards - group)})
    for prefix in (PERSPECTIVE_TEMPLATE, QUESTION_TEMPLATE):
        cards = {cid for cid, t in texts.items() if prefix in t}
        out.append({"pattern": prefix, "kind": "template_prefix", "cards": len(cards),
                    "recovered_cards": len(cards & group), "other_cards": len(cards - group)})
    return sorted(out, key=lambda r: -r["cards"])


def template_share(text: str, generic: set[str]) -> float:
    """Share of characters occupied by template prefixes, generic questions and duplicated move text."""
    lines = text.split("\n")
    templ = 0
    for line in lines:
        body = line[2:] if line.startswith("- ") else line
        if body in generic:
            templ += len(line)
        for prefix in (PERSPECTIVE_TEMPLATE, QUESTION_TEMPLATE):
            if prefix in line:
                templ += len(prefix)
    # launch move repeated in perspective and first question
    persp = next((l for l in lines if l.startswith("Перспектива: ")), "")
    move = persp.replace("Перспектива: ", "").replace(PERSPECTIVE_TEMPLATE, "").strip().rstrip(".")
    if move and PERSPECTIVE_TEMPLATE in persp and any(move in l for l in lines if l.startswith("- ")):
        templ += len(move)
    return round(templ / max(1, len(text)), 4)


def structural_share(text: str) -> float:
    """Share of characters in the TAXONOMY-vocabulary lines (coordinates / tensions)."""
    lines = [l for l in text.split("\n") if l.startswith(("Координаты:", "Напряжения:"))]
    return round(sum(len(l) for l in lines) / max(1, len(text)), 4)


def cosine_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    an = a / np.linalg.norm(a, axis=1, keepdims=True)
    bn = b / np.linalg.norm(b, axis=1, keepdims=True)
    return an @ bn.T


# ------------------------------------------------------------------ orchestration


class Embedder:
    """Diagnostic embedding with a separate cache root; never touches production caches."""

    def __init__(self, client: EmbeddingClient, cache_root: Path):
        self.client = client
        self.cache_root = cache_root

    def embed(self, namespace: str, texts: dict[str, str], version: str) -> np.ndarray:
        cache = EmbeddingCache(self.cache_root, self.client.config, f"{DIAG_PREFIX}-{namespace}")
        reps = [Representation(k, f"{DIAG_PREFIX}/{version}", texts[k]) for k in texts]
        return cache.embed(reps, self.client)


def run_diagnosis(fragments: list[Fragment], bench: Benchmark, baseline_traces: list[dict],
                  client: EmbeddingClient, cache_root: Path) -> dict:
    universe = sorted(retrieval_universe(fragments), key=lambda f: f.id)
    ids = [f.id for f in universe]
    recovered = {f.id for f in universe if f.technical.recovery_status}
    emb = Embedder(client, cache_root)
    queries = {c.id: case_query(c) for c in bench.cases}

    # --- baseline from the recorded M2.2 run
    base = {t["item_id"]: t["candidate_retrieval"] for t in baseline_traces}
    base_rank = {
        route: {k: [h["card_id"] for h in v[key]["hits"]] for k, v in base.items()}
        for route, key in (("Q0", "q0_control"), ("Q1", "q1_meaning"), ("STRUCTURE", "structure"))
    }
    baseline_stats = {r: ranking_stats(base_rank[r], ids, recovered) for r in base_rank}

    # --- documents
    generic = generic_questions(universe)
    full_docs = build_doc_variant(DOC_VARIANTS[3], universe)
    documents = {
        "group_statistics": doc_statistics(full_docs, recovered),
        "field_counts": {
            grp: {
                fld: _summ([len(getattr(f, fld) or []) for f in universe if (f.id in recovered) == (grp == "recovered")])
                for fld in ("philosophical_questions", "coordinates", "tensions")
            }
            for grp in ("recovered", "other")
        },
        "template_share": {
            grp: _summ([template_share(full_docs[f.id], generic) for f in universe if (f.id in recovered) == (grp == "recovered")])
            for grp in ("recovered", "other")
        },
        "structural_vocabulary_share": {
            grp: _summ([structural_share(full_docs[f.id]) for f in universe if (f.id in recovered) == (grp == "recovered")])
            for grp in ("recovered", "other")
        },
        "section_presence": {
            grp: {
                sec: sum(1 for f in universe if (f.id in recovered) == (grp == "recovered") and sec in full_docs[f.id])
                for sec in ("Перспектива:", "Философские вопросы:", "Координаты:", "Напряжения:")
            }
            for grp in ("recovered", "other")
        },
        "repeated_patterns": repeated_patterns(full_docs, recovered)[:25],
    }

    # --- field ablations (Q1 and Q0 queries against each document variant)
    q1_texts = {k: q1_text(q) for k, q in queries.items()}
    q0_texts = {k: q0_text(q) for k, q in queries.items()}
    q1_vecs = dict(zip(q1_texts, emb.embed("queries-q1", q1_texts, "q1")))
    q0_vecs = dict(zip(q0_texts, emb.embed("queries-q0", q0_texts, "q0")))
    field_ablations = {}
    doc_vectors = {}
    for v in DOC_VARIANTS:
        texts = build_doc_variant(v, universe)
        rankable = [k for k in ids if texts[k]]
        vecs = emb.embed(f"docs-{v.id}", {k: texts[k] for k in rankable}, v.id)
        doc_vectors[v.id] = (rankable, vecs)
        entry = {"description": v.description, "rankable_cards": len(rankable),
                 "empty_documents": sorted(set(ids) - set(rankable)),
                 "doc_chars": {grp: _summ([len(texts[k]) for k in rankable if (k in recovered) == (grp == "recovered")] or [0])
                               for grp in ("recovered", "other")}}
        for qname, qv in (("Q1", q1_vecs), ("Q0", q0_vecs)):
            r = rank_all(qv, rankable, vecs)
            entry[qname] = ranking_stats(r, ids, recovered, base_rank[qname])
            sims = cosine_matrix(np.stack(list(qv.values())), vecs)
            rec_mask = np.array([k in recovered for k in rankable])
            entry[qname]["mean_cosine_to_recovered"] = round(float(sims[:, rec_mask].mean()), 4) if rec_mask.any() else None
            entry[qname]["mean_cosine_to_other"] = round(float(sims[:, ~rec_mask].mean()), 4)
        field_ablations[v.id] = entry

    # --- query ablations against the production (D_full) documents
    rankable, full_vecs = doc_vectors["D_full"]
    qvars = {k: query_variants(q) for k, q in queries.items()}
    query_ablations = {}
    rec_mask = np.array([k in recovered for k in rankable])
    for qv_name in next(iter(qvars.values())):
        texts = {k: v[qv_name] for k, v in qvars.items()}
        vecs = dict(zip(texts, emb.embed(f"queries-{qv_name}", texts, qv_name)))
        r = rank_all(vecs, rankable, full_vecs)
        sims = cosine_matrix(np.stack(list(vecs.values())), full_vecs)
        query_ablations[qv_name] = dict(
            ranking_stats(r, ids, recovered, base_rank["Q1"]),
            mean_cosine_to_recovered=round(float(sims[:, rec_mask].mean()), 4),
            mean_cosine_to_other=round(float(sims[:, ~rec_mask].mean()), 4),
        )
    # lexical: do Q1 tension strings appear verbatim in card documents?
    lexical = {"cards_containing_any_query_tension": {}}
    for k, q in queries.items():
        tens = [*q.canonical_tensions, *q.free_tensions]
        hit = [cid for cid in rankable if any(t in full_docs[cid] for t in tens)]
        lexical["cards_containing_any_query_tension"][k] = {
            "recovered": sum(1 for c in hit if c in recovered), "other": sum(1 for c in hit if c not in recovered)}

    # --- embedding space (production documents)
    cc = cosine_matrix(full_vecs, full_vecs)
    np.fill_diagonal(cc, np.nan)
    rr = cc[np.ix_(rec_mask, rec_mask)]
    oo = cc[np.ix_(~rec_mask, ~rec_mask)]
    ro = cc[np.ix_(rec_mask, ~rec_mask)]
    centrality = np.nanmean(cc, axis=1)
    q1_mat = cosine_matrix(np.stack(list(q1_vecs.values())), full_vecs)
    mean_q1 = q1_mat.mean(axis=0)
    q1_freq = Counter(c for ids_ in base_rank["Q1"].values() for c in ids_)
    order_c = np.argsort(-centrality)
    space = {
        "within_recovered_mean": round(float(np.nanmean(rr)), 4),
        "within_other_mean": round(float(np.nanmean(oo)), 4),
        "between_groups_mean": round(float(np.nanmean(ro)), 4),
        "query_to_recovered_mean": round(float(q1_mat[:, rec_mask].mean()), 4),
        "query_to_other_mean": round(float(q1_mat[:, ~rec_mask].mean()), 4),
        "centrality_top15": [(rankable[i], round(float(centrality[i]), 4), rankable[i] in recovered) for i in order_c[:15]],
        "mean_q1_cosine_top15": [(rankable[i], round(float(mean_q1[i]), 4)) for i in np.argsort(-mean_q1)[:15]],
        "spearman_centrality_vs_q1_frequency": _spearman(
            list(centrality), [q1_freq.get(c, 0) for c in rankable]),
        "q1_similarity_quantiles": {
            grp: [round(float(x), 4) for x in np.quantile(q1_mat[:, m], [0.1, 0.25, 0.5, 0.75, 0.9])]
            for grp, m in (("recovered", rec_mask), ("other", ~rec_mask))
        },
    }

    # --- C0056 case study
    i56 = rankable.index("C0056")
    nn = np.argsort(-np.nan_to_num(cc[i56], nan=-1))[:10]
    per_query_rank = {k: base_rank["Q1"][k].index("C0056") + 1 if "C0056" in base_rank["Q1"][k] else None for k in base_rank["Q1"]}
    c0056 = {
        "document": full_docs["C0056"],
        "document_chars": len(full_docs["C0056"]),
        "recovered": "C0056" in recovered,
        "centrality": round(float(centrality[i56]), 4),
        "centrality_rank": int(np.where(order_c == i56)[0][0]) + 1,
        "mean_q1_cosine": round(float(mean_q1[i56]), 4),
        "mean_q1_cosine_rank": int(np.where(np.argsort(-mean_q1) == i56)[0][0]) + 1,
        "baseline_q1_rank_per_case": per_query_rank,
        "nearest_neighbours": [(rankable[j], round(float(cc[i56, j]), 4), rankable[j] in recovered) for j in nn],
        "frequency_by_doc_variant": {v: field_ablations[v]["Q1"]["focus_frequency"] for v in field_ablations},
        "frequency_by_query_variant": {v: query_ablations[v]["focus_frequency"] for v in query_ablations},
    }

    # --- STRUCTURE
    structure = structure_statistics(base, recovered, universe)

    return {
        "baseline": baseline_stats,
        "documents": documents,
        "field_ablations": field_ablations,
        "query_ablations": query_ablations,
        "query_lexical_overlap": lexical,
        "embedding_space": space,
        "c0056": c0056,
        "structure": structure,
    }


def structure_statistics(base: dict, recovered: set[str], universe: list[Fragment]) -> dict:
    per_case = {}
    tie_decided = 0
    tie_selected_recovered = tie_group_recovered = 0
    for k, v in base.items():
        s = v["structure"]
        hits = s["hits"]
        if not hits:
            per_case[k] = {"hits": 0}
            continue
        last = (hits[-1]["tension_overlap"], hits[-1]["coordinate_overlap"])
        kept_in_last_group = [h["card_id"] for h in hits if (h["tension_overlap"], h["coordinate_overlap"]) == last]
        decided = len(kept_in_last_group) if s["tied_at_cutoff"] else 0
        tie_decided += decided
        if decided:
            tie_selected_recovered += sum(1 for c in kept_in_last_group if c in recovered)
        per_case[k] = {
            "matching_cards": s["matching_cards"],
            "last_key": {"tension_overlap": last[0], "coordinate_overlap": last[1]},
            "tie_group_size": len(kept_in_last_group) + s["tied_at_cutoff"],
            "kept_from_tie_group": len(kept_in_last_group),
            "cut_from_tie_group": s["tied_at_cutoff"],
            "slots_decided_by_card_id": decided,
            "max_tension_overlap": max(h["tension_overlap"] for h in hits),
        }
    return {
        "per_case": per_case,
        "slots_decided_by_card_id_total": tie_decided,
        "slots_total": sum(len(v["structure"]["hits"]) for v in base.values()),
        "recovered_among_tie_decided_slots": tie_selected_recovered,
    }


def _summ(xs: list[float]) -> dict:
    xs = sorted(xs)
    return {"min": xs[0], "median": statistics.median(xs), "max": xs[-1], "mean": round(statistics.mean(xs), 3)}


def _spearman(a: list[float], b: list[float]) -> float:
    def ranks(x):
        order = sorted(range(len(x)), key=lambda i: x[i])
        r = [0.0] * len(x)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and x[order[j + 1]] == x[order[i]]:
                j += 1
            for t in range(i, j + 1):
                r[order[t]] = (i + j) / 2 + 1
            i = j + 1
        return r

    ra, rb = ranks(a), ranks(b)
    return round(float(np.corrcoef(ra, rb)[0, 1]), 4)


def write_report(result: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=False)
    for key, value in result.items():
        (out_dir / f"{key}.json").write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

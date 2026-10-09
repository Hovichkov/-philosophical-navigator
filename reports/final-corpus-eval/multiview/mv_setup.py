"""Multi-view retrieval experiment (read-only): baseline = B + Retrieval Layer v1 + guardrail, budget 15."""
import json, os, sys
from collections import Counter
from pathlib import Path
os.environ.setdefault("HF_HUB_OFFLINE", "1")
import numpy as np
from navigator.corpus.final_corpus import FINAL_CORPUS_VERSION, final_snapshot_fragments, load_final_active
from navigator.models.query import QueryProvenance, QueryRepresentation, UserContext
from navigator.providers.embeddings import LocalSentenceTransformerClient
from navigator.representations.final_meaning import mode_snapshot
from navigator.representations.meaning import q1_text
from navigator.representations.retrieval_layer import load_retrieval_layer
from navigator.retrieval.engine import CandidateRetriever
from navigator.benchmark.adapter import case_query
from navigator.models.benchmark import Benchmark

FINAL = final_snapshot_fragments(load_final_active())
BY = {f.id: f for f in FINAL}
AUTHOR = {f.id: f.author or "" for f in FINAL}
client = LocalSentenceTransformerClient()
snap = mode_snapshot(FINAL, "B", retrieval_layer=load_retrieval_layer(known_ids=set(BY)))
R = CandidateRetriever(snap.fragments, client, cache_root=Path("data/retrieval/embeddings-final"),
                       corpus_version=FINAL_CORPUS_VERSION, card_docs=snap.docs, persist_cache=False)
IDS = R.card_ids
CV = R.card_vectors / np.linalg.norm(R.card_vectors, axis=1, keepdims=True)
_qc = {}
def emb(texts):
    miss = [t for t in texts if t not in _qc]
    if miss:
        E = client.embed(miss); E = E / np.linalg.norm(E, axis=1, keepdims=True)
        for t, e in zip(miss, E): _qc[t] = e
    return np.stack([_qc[t] for t in texts])

SES = Path("reports/prototype-sessions"); EV = Path("reports/final-corpus-eval")
def qrep(sid): return QueryRepresentation.model_validate(json.load(open(SES / f"{sid}.json"))["query_representation"])
def mk(q, h, circ="", narr=None):
    return QueryRepresentation(confirmed_question=q, context=UserContext(circumstance=circ or None, narrative=narr),
                               working_hypotheses=h, provenance=QueryProvenance(origin="production",
                               confirmed_question_source="user_confirmed", interpretation_source="eval"))
KNOWN = {"роман": qrep("84ec8453fdcf"), "лекции": qrep("9635439e65fd"), "долги": qrep("3f952b110d2c"),
         "любит другого": qrep("e9559bde9cf8"), "студент": qrep("19e21efebc7e"), "жена": qrep("c1941dba2054")}
_abc = {r["case"]: r for r in json.load(open(EV / "cases-ABC-all.json"))}
KNOWN["R01"] = mk(_abc["4-R01"]["proposed_question"], _abc["4-R01"]["working_hypotheses"])
CONTROL = {"ctl:" + k: mk(r["proposed_question"], r["working_hypotheses"]) for k, r in _abc.items() if k != "4-R01"}
HOLD = {sid: qrep(sid) for sid in ["0cea5a1e196e","1067f8377ca7","17b9c41ecb2b","483f5633f57e","77ad233e57d0","79c1111a1710",
        "94e9f19afb64","bf98b63fa916","fa5146428783","dbd44e5bd76f","2c3e38305b9a","9baed3881055","1c787201b664"]}
_b = Benchmark.model_validate(json.loads(Path("data/eval/benchmarks/m2_1-retrieval-benchmark-v0.1.json").read_text(encoding="utf-8")))
BENCH = {"M2.1:" + c.id: case_query(c) for c in _b.cases}
SETS = {"known": KNOWN, "control": CONTROL, "holdout": HOLD, "M2.1": BENCH}

# ---- strong markers: every card the real composer ever selected for the SAME confirmed question
def _strong():
    s = {k: set() for k in KNOWN}
    sess = {"роман": "84ec8453fdcf", "лекции": "9635439e65fd", "долги": "3f952b110d2c", "любит другого": "e9559bde9cf8",
            "студент": "19e21efebc7e", "жена": "c1941dba2054"}
    for k, sid in sess.items():
        s[k] |= {p["card_id"] for p in json.load(open(SES / f"{sid}.json"))["composition"]["perspectives"]}
    for m in "ABC":
        s["R01"] |= {c["card_id"] for c in _abc["4-R01"][m].get("cards", [])}
    ga = {"A-loves-another": "любит другого", "B-psychology-student": "студент", "C-wife-control": "жена", "D-R01": "R01"}
    for r in json.load(open(EV / "guardrail-before-after.json")):
        s[ga[r["case"]]] |= set(r.get("after", {}).get("selected", []))
    for r in json.load(open(EV / "retrieval-layer-v1-compose.json")):
        s[r["case"]] |= set(r.get("after_selected", []))
    return s
STRONG = _strong()

def views(q):
    return [("Q", q.confirmed_question)] + [(f"H{i+1}", h) for i, h in enumerate(q.working_hypotheses)]

def scores(q):
    """per view cosine over all cards + the current combined Q1 view"""
    vs = views(q); texts = [t for _, t in vs] + [q1_text(q)]
    E = emb(texts); S = E @ CV.T
    return [n for n, _ in vs], S[:-1], S[-1]

def order(sc): return [IDS[i] for i in np.argsort(-sc, kind="stable")]

def fuse(q, method):
    names, S, comb = scores(q)
    if method == "single": return order(comb)
    if method == "max": return order(S.max(0))
    if method == "max+comb": return order(np.vstack([S, comb]).max(0))
    ranks = [np.argsort(np.argsort(-s, kind="stable"), kind="stable") for s in (list(S) + ([comb] if method.endswith("+comb") else []))]
    if method.startswith("rrf"): return order(sum(1.0 / (60 + r + 1) for r in ranks))
    if method == "rr":
        lists = [order(s) for s in S]; out, seen = [], set()
        for i in range(len(IDS)):
            for L in lists:
                if L[i] not in seen: out.append(L[i]); seen.add(L[i])
            if len(out) >= 120: break
        return out
    raise ValueError(method)

def pool(ranked, k, per=3):
    out, cnt = [], Counter()
    for c in ranked[: 3 * k]:
        if cnt[AUTHOR[c]] < per: out.append(c); cnt[AUTHOR[c]] += 1
        if len(out) == k: break
    return out

def found_by(q, card, top=30):
    names, S, comb = scores(q)
    i = IDS.index(card); hits = []
    for n, s in zip(names + ["Q1(склейка)"], list(S) + [comb]):
        r = int((s > s[i]).sum()) + 1
        if r <= top: hits.append(f"{n}#{r}")
    return hits

def hybrid(q, k, core=10, per=3):
    """baseline single-query core (after the source cap) + round-robin fill from the per-view rankings"""
    base = pool(fuse(q, "single"), core, per)
    names, S, comb = scores(q)
    lists = [order(s) for s in S]
    out, cnt = list(base), Counter(AUTHOR[c] for c in base)
    pos = [0] * len(lists)
    while len(out) < k and any(p < 3 * k for p in pos):
        for li, L in enumerate(lists):
            while pos[li] < 3 * k:
                c = L[pos[li]]; pos[li] += 1
                if c not in out and cnt[AUTHOR[c]] < per:
                    out.append(c); cnt[AUTHOR[c]] += 1; break
            if len(out) == k: break
    return out

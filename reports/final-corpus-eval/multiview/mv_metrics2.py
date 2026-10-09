import sys; sys.path.insert(0, sys.argv[1])
from mv_setup import *
import statistics as st
idx = {c: i for i, c in enumerate(IDS)}
def evaluate(name, poolfn):
    rec = {"recall": [], "weak": [], "cover": [], "spread": [], "freq": Counter()}
    for sn, Q in SETS.items():
        for qn, q in Q.items():
            names, S, comb = scores(q); p = poolfn(q)
            rec["freq"].update(p)
            ranks = [np.argsort(np.argsort(-s, kind="stable"), kind="stable") for s in list(S) + [comb]]
            best = [min(int(r[idx[c]]) + 1 for r in ranks) for c in p]
            rec["weak"].append(sum(b > 30 for b in best) / len(p))
            tops = [set(order(s)[:5]) for s in S]
            rec["cover"].append(sum(bool(t & set(p)) for t in tops) / len(tops))
            V = CV[[idx[c] for c in p]]; G = V @ V.T
            rec["spread"].append(float((G.sum() - len(p)) / (len(p) * (len(p) - 1))))
            if sn == "known": rec["recall"].append(len(STRONG[qn] & set(p)) / len(STRONG[qn]))
    print(f"{name:22} recall сильных={st.mean(rec['recall']):.0%}  слабых={st.mean(rec['weak']):.0%}  покрытие видов={st.mean(rec['cover']):.0%}  "
          f"ср.близость={st.mean(rec['spread']):.3f}  хабы={rec['freq'].most_common(3)}")
for k in (15, 20, 25):
    evaluate(f"single k={k}", lambda q, k=k: pool(fuse(q, "single"), k))
    for core in (10, 15):
        if core < k or (core == 15 and k > 15):
            evaluate(f"hybrid core{core} k={k}", lambda q, k=k, core=core: hybrid(q, k, core))

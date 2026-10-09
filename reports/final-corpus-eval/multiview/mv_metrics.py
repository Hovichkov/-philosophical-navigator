import sys; sys.path.insert(0, sys.argv[1])
from mv_setup import *
import statistics as st
idx = {c: i for i, c in enumerate(IDS)}
METHODS = ["single", "max", "max+comb", "rrf", "rrf+comb", "rr"]
rows = {}
for m in METHODS:
    for k in (15, 20, 25):
        rec = {"recall": [], "weak": [], "cover": [], "spread": [], "freq": Counter()}
        for sn, Q in SETS.items():
            for qn, q in Q.items():
                names, S, comb = scores(q)
                p = pool(fuse(q, m), k)
                rec["freq"].update(p)
                ranks = [np.argsort(np.argsort(-s, kind="stable"), kind="stable") for s in list(S) + [comb]]
                best = [min(int(r[idx[c]]) + 1 for r in ranks) for c in p]
                rec["weak"].append(sum(b > 30 for b in best) / len(p))
                tops = [set(order(s)[:5]) for s in S]
                rec["cover"].append(sum(bool(t & set(p)) for t in tops) / len(tops))
                V = CV[[idx[c] for c in p]]; G = V @ V.T
                rec["spread"].append(float((G.sum() - len(p)) / (len(p) * (len(p) - 1))))
                if sn == "known": rec["recall"].append(len(STRONG[qn] & set(p)) / len(STRONG[qn]))
        top = rec["freq"].most_common(3)
        rows[(m, k)] = rec
        print(f"{m:9} k={k}: recall сильных={st.mean(rec['recall']):.0%}  слабых(вне top-30 всех видов)={st.mean(rec['weak']):.0%}  "
              f"покрытие видов={st.mean(rec['cover']):.0%}  ср.близость в пуле={st.mean(rec['spread']):.3f}  "
              f"хабы={[(c, n) for c, n in top]}")

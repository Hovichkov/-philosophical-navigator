import sys; sys.path.insert(0, sys.argv[1])
from mv_setup import *
from navigator.composition.references import display_label
import csv
RT = {r["card_id"]: r["distinction"] for r in csv.DictReader(open("data/retrieval-layer/RETRIEVAL-LAYER-v1-BLOCK1.csv", encoding="utf-8"))}
q = KNOWN[sys.argv[2]]
for n, t in views(q): print(f"{n}: {t[:150]}")
MARK = ["C0258","C0005","C0065","C0581","C1067","C0046","C0485","C0248"]
print("\nПо какому виду найдены маркеры (места ≤30):")
for c in MARK: print(f"  {c} {display_label(BY[c])[:34]:34} {found_by(q, c)}")
for m, k in [("single",15),("rrf+comb",20),("rr",20),("max",20)]:
    p = pool(fuse(q, m), k)
    print(f"\n=== {m} k={k}")
    for c in p:
        tag = "★" if c in STRONG[sys.argv[2]] else " "
        mv = RT.get(c) or BY[c].technical.launch_philosophical_move
        print(f" {tag} {c} {display_label(BY[c])[:32]:32} {','.join(found_by(q,c,10))[:22]:22} | {mv[:85]}")

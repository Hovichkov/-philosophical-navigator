"""Baseline candidate-retrieval routes (M2.2): cosine ranking, STRUCTURE, union.

No combined MEANING/STRUCTURE score, no learned or benchmark-tuned weights.
"""

from __future__ import annotations

import numpy as np

from navigator.models.fragment import Fragment
from navigator.models.retrieval import SimilarityHit, StructureHit, UnionCandidate
from navigator.models.vocabularies import PHILOSOPHICAL_OPERATIONS_V0_1, TENSION_QUALIFIER

STRUCTURE_RANKING_RULE = (
    "lexicographic: (1) more exact canonical-tension matches, (2) more exact coordinate matches, "
    "(3) card_id ascending; cards with no match are not ranked; operation is logged, never scored"
)
UNION_RULE = (
    "union(Q1_MEANING top_k, STRUCTURE top_k); Q0 excluded; one entry per card_id with separate route "
    "signals; no combined score; listed by card_id ascending (the order is not a ranking)"
)


def cosine_rank(query_vector: np.ndarray, card_ids: list[str], card_vectors: np.ndarray, top_k: int) -> list[SimilarityHit]:
    """Brute-force cosine similarity; ties broken by card_id ascending."""
    if card_vectors.shape[0] != len(card_ids):
        raise ValueError("card_ids and card_vectors are misaligned")
    q = query_vector / (np.linalg.norm(query_vector) or 1.0)
    norms = np.linalg.norm(card_vectors, axis=1)
    norms[norms == 0] = 1.0
    sims = (card_vectors / norms[:, None]) @ q
    order = sorted(range(len(card_ids)), key=lambda i: (-float(sims[i]), card_ids[i]))
    return [SimilarityHit(card_id=card_ids[i], rank=r + 1, cosine=round(float(sims[i]), 6)) for r, i in enumerate(order[:top_k])]


def _card_tensions(fragment: Fragment) -> list[str]:
    out = []
    for t in fragment.tensions or []:
        base = t[: -len(TENSION_QUALIFIER)] if t.endswith(TENSION_QUALIFIER) else t
        if base not in out:
            out.append(base)
    return out


def structure_rank(
    fragments: list[Fragment], coordinates: list[str], canonical_tensions: list[str], top_k: int
) -> tuple[list[StructureHit], int, int]:
    """Return (top_k hits, number of matching cards, number of cards tied with the last kept hit but cut)."""
    q_coords, q_tensions = set(coordinates), set(canonical_tensions)
    scored = []
    for f in fragments:
        matched_t = sorted(set(_card_tensions(f)) & q_tensions)
        matched_c = sorted(set(f.coordinates or []) & q_coords)
        if not matched_t and not matched_c:
            continue
        op = f.philosophical_operation if f.philosophical_operation in PHILOSOPHICAL_OPERATIONS_V0_1 else None
        scored.append((len(matched_t), len(matched_c), f.id, matched_t, matched_c, op))
    scored.sort(key=lambda s: (-s[0], -s[1], s[2]))
    kept = scored[:top_k]
    tied = 0
    if kept and len(scored) > top_k:
        last_key = kept[-1][:2]
        tied = sum(1 for s in scored[top_k:] if s[:2] == last_key)
    hits = [
        StructureHit(
            card_id=s[2], rank=i + 1, tension_overlap=s[0], matched_tensions=s[3],
            coordinate_overlap=s[1], matched_coordinates=s[4], operation=s[5],
        )
        for i, s in enumerate(kept)
    ]
    return hits, len(scored), tied


def candidate_union(meaning_hits: list[SimilarityHit], structure_hits: list[StructureHit], operations: dict[str, str | None]) -> list[UnionCandidate]:
    m = {h.card_id: h for h in meaning_hits}
    s = {h.card_id: h for h in structure_hits}
    out = []
    for cid in sorted(set(m) | set(s)):
        mh, sh = m.get(cid), s.get(cid)
        out.append(
            UnionCandidate(
                card_id=cid,
                found_by=[r for r, h in (("Q1_MEANING", mh), ("STRUCTURE", sh)) if h is not None],
                meaning_rank=mh.rank if mh else None,
                meaning_score=mh.cosine if mh else None,
                structure_rank=sh.rank if sh else None,
                coordinate_overlap=sh.coordinate_overlap if sh else None,
                matched_coordinates=sh.matched_coordinates if sh else None,
                tension_overlap=sh.tension_overlap if sh else None,
                matched_tensions=sh.matched_tensions if sh else None,
                operation=operations.get(cid),
            )
        )
    return out

"""TEMPORARY MVP RETRIEVAL DIVERSITY GUARDRAIL — NOT the retrieval architecture.

temporary MVP retrieval diversity guardrail (2026-10-08), final corpus only.

Why it exists: the final-corpus retrieval audit (reports/validation/FINAL-CORPUS-RETRIEVAL-BIAS-AUDIT.md) showed that
semantic ranking is driven by the editorial style of the card text (form of ``philosophical_move``, length / genre of
the quote), not only by meaning; Epictetus (157 of 967 cards) took ~39 % of the top-30 hits in mode B. The real fix is
a unified ``retrieval_text`` layer for all cards — deliberately postponed until after the MVP. Until then this filter
keeps one source from filling the candidate pool. Remove it when ``retrieval_text`` exists (and re-measure first).

Rule (identical for every source, nothing is hardcoded per author):
- walk the ORIGINAL cosine ranking top-down;
- accept a card while its source has fewer than ``per_source`` accepted cards, otherwise skip it;
- stop at ``pool_size`` accepted cards.
It does NOT re-rank or re-score: accepted cards keep their original rank and cosine, in the original order.

Source = the card's ``author`` field from FINAL-CORPUS-ACTIVE-v1.csv, verbatim (no new source definition).
``work`` / the package's ``source_group`` would split Epictetus into Discourses + Enchiridion (up to 6 of 15).

Controlled fallback: the walk never goes below rank ``scan_limit`` (3 × pool size). If the pool is not full by then,
the pool stays SMALLER — it is never padded with low-ranked material and the cap is never relaxed. With 967 cards and
16+ authors this has not happened on the 34 evaluation queries (deepest accepted rank: 40).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from navigator.models.retrieval import SimilarityHit

GUARDRAIL_VERSION = "temporary-mvp-source-diversity-guardrail/0.1.0"


@dataclass(frozen=True)
class SourceDiversityGuardrail:
    """temporary MVP retrieval diversity guardrail — see the module docstring."""

    per_source: int = 3
    pool_size: int = 15
    scan_limit: int = 45

    def apply(self, ranked: list[SimilarityHit], source_of: dict[str, str]) -> tuple[list[SimilarityHit], dict]:
        """``ranked``: the original cosine ranking (at least ``scan_limit`` deep when available).
        Returns (accepted hits in original order with original ranks, trace record)."""
        accepted: list[SimilarityHit] = []
        skipped: list[dict] = []
        count: Counter[str] = Counter()
        for hit in ranked[: self.scan_limit]:
            if len(accepted) == self.pool_size:
                break
            source = source_of[hit.card_id]
            if count[source] < self.per_source:
                accepted.append(hit)
                count[source] += 1
            else:
                skipped.append({"card_id": hit.card_id, "rank": hit.rank, "source": source})
        return accepted, {
            "version": GUARDRAIL_VERSION,
            "status": "temporary MVP retrieval diversity guardrail (final corpus only; not the retrieval architecture)",
            "rule": f"walk the original cosine ranking; at most {self.per_source} cards per source (CSV author field); "
                    f"pool {self.pool_size}; never below rank {self.scan_limit}; no padding, no re-ranking",
            "per_source": self.per_source,
            "pool_size": self.pool_size,
            "scan_limit": self.scan_limit,
            "original_top": [h.card_id for h in ranked[: self.pool_size]],
            "skipped": skipped,
            "deepest_accepted_rank": max((h.rank for h in accepted), default=0),
            "pool_filled": len(accepted) == self.pool_size,
        }

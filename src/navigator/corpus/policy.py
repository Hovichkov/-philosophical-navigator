"""Which card ids may never enter retrieval / composition — per corpus.

- legacy corpora (launch 124 / restored 1090, ``corpus_version`` anything else or None): the historical
  ``UNRESOLVED_IDS`` guard of the M1 closeout (11 ids without a textual pass) — unchanged;
- the final corpus 2026-10-07 (``corpus_version == FINAL_CORPUS_VERSION``): the package itself is the source of truth —
  every id listed in EXCLUSIONS-AND-UNRESOLVED-v1.csv (rejected, ambiguous, unresolved, scope-excluded, gaps). An id
  that is in FINAL-CORPUS-ACTIVE-v1.csv and passed the final validator is resolved, whatever the legacy list says.
"""

from __future__ import annotations

import csv
from functools import lru_cache

from navigator.corpus.final_corpus import EXCLUSIONS_CSV, FINAL_CORPUS_VERSION, PACKAGE_DIR
from navigator.models.vocabularies import UNRESOLVED_IDS


@lru_cache(maxsize=1)
def final_excluded_ids() -> frozenset[str]:
    with (PACKAGE_DIR / EXCLUSIONS_CSV).open(encoding="utf-8-sig", newline="") as fh:
        return frozenset(r["card_id"] for r in csv.DictReader(fh))


def excluded_ids_for(corpus_version: str | None) -> frozenset[str]:
    if corpus_version == FINAL_CORPUS_VERSION:
        return final_excluded_ids()
    return UNRESOLVED_IDS

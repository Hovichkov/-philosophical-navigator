"""Which corpus snapshot the retrieval / card tests run on.

Default ``compact`` = data/corpus/fragments.jsonl (124 launch cards, 113 retrieval-eligible) — the snapshot every
existing test was written for. ``NAVIGATOR_TEST_CORPUS=final`` runs the same tests on the final corpus 2026-10-07
(corpus/final-2026-10-07/FINAL-CORPUS-ACTIVE-v1.csv, 967 cards, via navigator.corpus.final_corpus);
``final-diagnostic`` = the same minus the 11 old UNRESOLVED_IDS (diagnostic only).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from navigator.models.fragment import Fragment

ROOT = Path(__file__).resolve().parents[1]


def snapshot_name() -> str:
    return os.environ.get("NAVIGATOR_TEST_CORPUS", "compact")


def load_test_fragments() -> list[Fragment]:
    if snapshot_name() in ("final", "final-diagnostic"):
        from navigator.corpus.final_corpus import final_snapshot_fragments, load_final_active

        frags = final_snapshot_fragments(load_final_active(ROOT / "corpus/final-2026-10-07"))
        if snapshot_name() == "final-diagnostic":
            # DIAGNOSTIC ONLY: drops the 11 ids of the old launch UNRESOLVED_IDS guard (active and verified in the final
            # corpus) to see which incompatibilities remain behind that guard. Not a product decision.
            from navigator.models.vocabularies import UNRESOLVED_IDS

            frags = [f for f in frags if f.id not in UNRESOLVED_IDS]
        return frags
    return [Fragment.model_validate(json.loads(l))
            for l in (ROOT / "data/corpus/fragments.jsonl").read_text(encoding="utf-8").splitlines()]


# ------------------------------------------------------------------ snapshot-aware expectations (final-corpus test mode)
import pytest  # noqa: E402

FINAL = snapshot_name() != "compact"
LEGACY_REASON = ("legacy-corpus test: checks data recorded for the 124/113 launch corpus (M2 benchmark traces, M2.3 "
                 "diagnosis, quote-readiness audit, STRUCTURE metadata or corpus-file invariants); final-corpus "
                 "invariants are tested in test_final_corpus_import.py / test_final_corpus_retrieval.py")
legacy_only = pytest.mark.skipif(FINAL, reason=LEGACY_REASON)
LEGACY_CARD_REASON = ("legacy card contract (title / «Подробнее» / «Что имеется в виду?» / up to two questions): the "
                      "final corpus has its own MVP card (quote · comment · application · one question), tested in "
                      "tests/test_mvp_final_card.py; this test keeps running on the default compact snapshot")
legacy_card_only = pytest.mark.skipif(FINAL, reason=LEGACY_CARD_REASON)


def expected_eligible() -> int:
    """Size of the retrieval universe of the snapshot under test (113 for the launch corpus)."""
    if not FINAL:
        return 113
    from navigator.corpus.readiness import retrieval_universe

    return len(retrieval_universe(load_test_fragments()))


def blocked_ids() -> frozenset[str]:
    """Ids that must never be retrieved in this snapshot: the legacy guard, or the final package's exclusions."""
    from navigator.corpus.final_corpus import FINAL_CORPUS_VERSION
    from navigator.corpus.policy import excluded_ids_for

    return excluded_ids_for(FINAL_CORPUS_VERSION if FINAL else None)

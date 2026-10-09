"""Retrieval documents for the final corpus 2026-10-07 — three EXPERIMENTAL modes (not a chosen architecture).

The final CSV has a philosophical move and a verified verbatim quote per card, but no perspective, coordinates or
tensions. Three ways to build the MEANING card document (the query side — Q1 — is unchanged):

A  ``final-card-doc/A-move/1.0``        the philosophical_move, verbatim;
B  ``final-card-doc/B-move-quote/1.0``  the philosophical_move + the quote, verbatim;
C  ``final-card-doc/C-legacy/1.0``      DIAGNOSTIC ONLY: for a card with a reliable legacy correspondence — same
                                        card_id in the restored legacy registry (data/corpus-full), the same
                                        philosophical move (normalised) and a real (non-placeholder) legacy perspective —
                                        the legacy MEANING document (perspective + question) and the legacy coordinates /
                                        tensions for STRUCTURE; every other card falls back to the A document and has no
                                        STRUCTURE metadata. Built in memory for the experiment; nothing is written into the
                                        final corpus and the legacy metadata is not part of its source of truth.

In A and B the STRUCTURE route finds nothing (the final corpus has no coordinates / tensions).

Retrieval Layer v1 (2026-10-08, ``navigator.representations.retrieval_layer``): in mode B, a card covered by the layer
gets ``retrieval_text`` + the verified quote instead of move + quote (version ``final-card-doc/B-rl-<layer>/1.0``);
every other card keeps its B document. Reversible: ``retrieval_layer=None`` reproduces plain B exactly.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from navigator.corpus.readiness import meaning_inputs
from navigator.models.fragment import Fragment
from navigator.representations.meaning import Representation, meaning_card_text

MODES = ("A", "B", "C")
MODE_VERSIONS = {"A": "final-card-doc/A-move/1.0", "B": "final-card-doc/B-move-quote/1.0", "C": "final-card-doc/C-legacy/1.0"}
LEGACY_FULL = Path(__file__).resolve().parents[3] / "data/corpus-full/fragments.jsonl"


def _norm_move(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).rstrip(".").lower().replace("ё", "е")


@dataclass
class ModeSnapshot:
    mode: str
    fragments: list[Fragment]  # what retrieval sees (C: with legacy coordinates / tensions where reliable)
    docs: list[Representation]
    legacy_matched: list[str]  # C only: ids that use legacy metadata


def load_legacy(path: Path = LEGACY_FULL) -> dict[str, Fragment]:
    return {f.id: f for f in (Fragment.model_validate(json.loads(l))
                               for l in path.read_text(encoding="utf-8").splitlines())}


def reliable_legacy(final: Fragment, legacy: dict[str, Fragment]) -> Fragment | None:
    old = legacy.get(final.id)
    # a real legacy perspective: present AND not an editorial placeholder (exactly what legacy MEANING would read)
    if old is None or not old.technical.retrieval_eligible or not meaning_inputs(old).get("perspective"):
        return None
    if _norm_move(old.technical.launch_philosophical_move) != _norm_move(final.technical.launch_philosophical_move):
        return None
    return old


def mode_snapshot(final_fragments: list[Fragment], mode: str, legacy: dict[str, Fragment] | None = None,
                  retrieval_layer=None) -> ModeSnapshot:
    if mode not in MODES:
        raise ValueError(f"unknown retrieval mode {mode}")
    if retrieval_layer is not None and mode != "B":
        raise ValueError("the retrieval layer is defined for mode B (retrieval_text + verified quote)")
    version = MODE_VERSIONS[mode]
    layer_version = f"final-card-doc/B-rl-{retrieval_layer.name}/1.0" if retrieval_layer is not None else None
    frags, docs, matched = [], [], []
    for f in sorted(final_fragments, key=lambda x: x.id):
        move = f.technical.launch_philosophical_move
        text = move if mode != "B" else f"{move}\n{f.fragment}"
        if mode == "C":
            old = reliable_legacy(f, legacy if legacy is not None else load_legacy())
            if old is not None:
                text = meaning_card_text(old)
                f = f.model_copy(update={"coordinates": old.coordinates, "tensions": old.tensions})
                matched.append(f.id)
        if retrieval_layer is not None and f.id in retrieval_layer.texts:
            docs.append(Representation(f.id, layer_version, f"{retrieval_layer.texts[f.id]}\n{f.fragment}"))
            frags.append(f)
            continue
        frags.append(f)
        docs.append(Representation(f.id, version, text))
    return ModeSnapshot(mode, frags, docs, matched)

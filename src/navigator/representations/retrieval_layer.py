"""Retrieval Layer v1 — a separate SEARCH representation of final-corpus cards (2026-10-08).

Why. The audit (reports/validation/FINAL-CORPUS-RETRIEVAL-BIAS-AUDIT.md) showed that semantic retrieval mostly rewards
the editorial register of a card's text: cards already phrased in modern rational-applied language (Epictetus,
Epicurus) win, while the distinctions of other traditions stay invisible. ``retrieval_text`` states the philosophical
distinction a fragment makes, plus one sentence on the KIND of human situation it illuminates — general, never an
application to a particular question, grounded in the card's verified quote and philosophical move.

Scope. Block 1 = Bhagavad-gita (40) · Upanishads (95) · Dao De Jing (64) = 199 cards. Other cards keep their current
document. The layer is used only for the final corpus, retrieval mode B (retrieval_text + verified quote); it never
reaches the user's card, the selector or the writer, and it changes nothing in the verified corpus.

Format. ``data/retrieval-layer/RETRIEVAL-LAYER-v1-BLOCK1.csv`` — card_id, block, work, location, retrieval_text,
distinction, situation, layer_version, basis. Human-auditable; a later version replaces the file (and the version
string, so cached vectors never mix).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

LAYER_DIR = Path(__file__).resolve().parents[3] / "data/retrieval-layer"
LAYERS = {"v1-block1": "RETRIEVAL-LAYER-v1-BLOCK1.csv"}
DEFAULT_LAYER = "v1-block1"
COLUMNS = ("card_id", "block", "work", "location", "retrieval_text", "distinction", "situation", "layer_version", "basis")


@dataclass(frozen=True)
class RetrievalLayer:
    name: str
    version: str
    texts: dict[str, str]  # card_id → retrieval_text


def load_retrieval_layer(name: str = DEFAULT_LAYER, directory: Path = LAYER_DIR,
                         known_ids: set[str] | None = None) -> RetrievalLayer:
    """Load and check one layer file: exact columns, unique ids, non-empty texts, one version, ids in the corpus."""
    if name not in LAYERS:
        raise ValueError(f"unknown retrieval layer {name}; known: {sorted(LAYERS)}")
    with (directory / LAYERS[name]).open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError(f"retrieval layer {name}: columns {reader.fieldnames} != {list(COLUMNS)}")
        rows = list(reader)
    ids = [r["card_id"] for r in rows]
    problems = []
    if len(ids) != len(set(ids)):
        problems.append("duplicate card_id")
    if any(not (r["retrieval_text"] or "").strip() for r in rows):
        problems.append("empty retrieval_text")
    versions = {r["layer_version"] for r in rows}
    if len(versions) != 1:
        problems.append(f"mixed layer_version {sorted(versions)}")
    if known_ids is not None and set(ids) - known_ids:
        problems.append(f"ids not in the corpus: {sorted(set(ids) - known_ids)[:5]}")
    if problems:
        raise ValueError(f"retrieval layer {name}: " + "; ".join(problems))
    return RetrievalLayer(name, versions.pop(), {r["card_id"]: r["retrieval_text"].strip() for r in rows})

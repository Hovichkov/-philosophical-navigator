"""Retrieval Layer v1 / Block 1 (Bhagavad-gita · Upanishads · Dao De Jing, 199 cards): a separate search text.

What is checked: the layer file is complete and clean; it is used only in final mode B and only for its 199 cards;
plain B is reproduced exactly without it; the verified corpus, the user card and legacy retrieval are untouched.
Whether the texts are good philosophy is judged by the audit report, not here. Fake embeddings."""

from __future__ import annotations

import csv
import re

import pytest

from navigator.corpus.final_corpus import final_snapshot_fragments, load_final_active
from navigator.representations.final_meaning import MODE_VERSIONS, mode_snapshot
from navigator.representations.retrieval_layer import COLUMNS, LAYER_DIR, LAYERS, load_retrieval_layer


@pytest.fixture(scope="module")
def final():
    return final_snapshot_fragments(load_final_active())


def block1(f):
    return f.work in ("Бхагавад-гита", "Дао дэ цзин") or "упанишада" in (f.work or "").lower()


def test_layer_covers_exactly_block1_with_one_version(final):
    layer = load_retrieval_layer(known_ids={f.id for f in final})
    ids = {f.id for f in final if block1(f)}
    assert set(layer.texts) == ids and len(ids) == 199
    assert layer.version == "retrieval-layer/v1-block1"
    rows = list(csv.DictReader((LAYER_DIR / LAYERS["v1-block1"]).open(encoding="utf-8")))
    assert tuple(rows[0]) == COLUMNS
    counts = {b: sum(r["block"] == b for r in rows) for b in ("Бхагавад-гита", "Упанишады", "Дао дэ цзин")}
    assert counts == {"Бхагавад-гита": 40, "Упанишады": 95, "Дао дэ цзин": 64}
    for r in rows:  # retrieval_text = the distinction + one sentence on the kind of situation it illuminates
        assert r["retrieval_text"] == f"{r['distinction']} {r['situation']}"
        assert 10 <= len(r["retrieval_text"].split()) <= 80


def test_layer_texts_are_not_quotes_moves_or_self_help_slogans(final):
    by = {f.id: f for f in final}
    layer = load_retrieval_layer()
    slogans = r"сосредоточ\w* на процесс|прислушай|найдите настоящ|будьте гибк|не перенапряга|контролируйте"
    for cid, text in layer.texts.items():
        f = by[cid]
        assert text != f.fragment and text != f.technical.launch_philosophical_move
        assert not re.search(slogans, text, re.IGNORECASE), cid
    assert len(set(layer.texts.values())) == len(layer.texts)  # no two cards share a search text


def test_mode_b_uses_the_layer_only_for_block1_and_keeps_the_quote(final):
    layer = load_retrieval_layer()
    plain = {d.key: d for d in mode_snapshot(final, "B").docs}
    layered = {d.key: d for d in mode_snapshot(final, "B", retrieval_layer=layer).docs}
    by = {f.id: f for f in final}
    for cid, d in layered.items():
        if cid in layer.texts:
            assert d.version == "final-card-doc/B-rl-v1-block1/1.0"
            assert d.text == f"{layer.texts[cid]}\n{by[cid].fragment}"  # verified quote kept verbatim
        else:
            assert d == plain[cid] and d.version == MODE_VERSIONS["B"]


def test_layer_is_only_for_mode_b_and_is_reversible(final):
    layer = load_retrieval_layer()
    with pytest.raises(ValueError):
        mode_snapshot(final, "A", retrieval_layer=layer)
    assert [d.text for d in mode_snapshot(final, "B", retrieval_layer=None).docs] == \
           [d.text for d in mode_snapshot(final, "B").docs]


def test_broken_layer_file_is_rejected(tmp_path, final):
    src = (LAYER_DIR / LAYERS["v1-block1"]).read_text(encoding="utf-8").splitlines()
    (tmp_path / LAYERS["v1-block1"]).write_text("\n".join(src + [src[1]]) + "\n", encoding="utf-8")  # duplicate row
    with pytest.raises(ValueError, match="duplicate"):
        load_retrieval_layer(directory=tmp_path)
    bad = [src[0], src[1].replace("C0001", "C9999", 1)]
    (tmp_path / LAYERS["v1-block1"]).write_text("\n".join(bad) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not in the corpus"):
        load_retrieval_layer(directory=tmp_path, known_ids={f.id for f in final})

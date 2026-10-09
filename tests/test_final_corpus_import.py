"""Final corpus 2026-10-07: the importer/validator enforces CORPUS-CONTRACT-FOR-CLAUDE-CODE.md and keeps every value."""

from __future__ import annotations

import csv
import io
import shutil
from pathlib import Path

import pytest

from navigator.corpus.final_corpus import (
    ACTIVE_CSV,
    COLUMNS,
    EXCLUSIONS_CSV,
    FINAL_DIR,
    FinalCorpusError,
    final_snapshot_fragments,
    load_final_active,
    verify_manifest,
)
from navigator.corpus.readiness import retrieval_universe

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / FINAL_DIR


@pytest.fixture(scope="module")
def cards():
    return load_final_active(PKG)


def rows():
    with (PKG / ACTIVE_CSV).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_pkg(tmp_path, rs, header=COLUMNS):
    d = tmp_path / "pkg"
    d.mkdir()
    shutil.copy(PKG / EXCLUSIONS_CSV, d / EXCLUSIONS_CSV)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(header), lineterminator="\r\n")
    w.writeheader()
    for r in rs:
        w.writerow({k: r.get(k, "") for k in header})
    (d / ACTIVE_CSV).write_text("﻿" + buf.getvalue(), encoding="utf-8")
    return d


def test_package_is_intact_and_valid(cards):
    assert verify_manifest(PKG) == []
    assert len(cards) == 967 and len({c.card_id for c in cards}) == 967


def test_values_are_kept_verbatim(cards):
    original = rows()
    assert [c.card_id for c in cards] == [r["card_id"] for r in original]  # same order, same ids: nothing renumbered
    for c, r in zip(cards, original):
        assert all(getattr(c, k) == r[k] for k in COLUMNS)


@pytest.mark.parametrize("mutate,needle", [
    (lambda rs: rs.append(dict(rs[0])), "duplicate card_id"),
    (lambda rs: rs[3].update(card_id=""), "blank card_id"),
    (lambda rs: rs[3].update(card_id="  "), "blank card_id"),
    (lambda rs: rs[3].update(card_id="C105"), "not of the form"),
    (lambda rs: rs[4].update(philosophical_move=""), "blank philosophical_move"),
    (lambda rs: rs[4].update(philosophical_move="   "), "blank philosophical_move"),
    (lambda rs: rs[5].update(quote=""), "blank quote"),
    (lambda rs: rs[6].update(verification_status="REJECTED_MOVE_SOURCE_MISMATCH"), "forbidden verification_status"),
    (lambda rs: rs[6].update(verification_status="AMBIGUOUS"), "forbidden verification_status"),
])
def test_contract_violation_fails_the_import(mutate, needle, tmp_path):
    rs = rows()
    mutate(rs)
    with pytest.raises(FinalCorpusError, match=needle):
        load_final_active(write_pkg(tmp_path, rs))


@pytest.mark.parametrize("cid,needle", [
    ("C0848", "Plato outside the frozen scope"),  # Crito
    ("C0871", "Plato outside the frozen scope"),  # Phaedo
    ("C0293", "historical gap"),
    ("C0364", "rejected"),
    ("C0656", "are active"),  # present-ambiguous row, listed in EXCLUSIONS
    ("C1108", "are active"),  # Zhuangzi: out of final scope
])
def test_excluded_and_out_of_scope_ids_never_become_active(cid, needle, tmp_path):
    rs = rows()
    rs.append({**rs[0], "card_id": cid})
    with pytest.raises(FinalCorpusError, match=needle):
        load_final_active(write_pkg(tmp_path, rs))


def test_header_must_match_the_contract(tmp_path):
    rs = rows()
    with pytest.raises(FinalCorpusError, match="header"):
        load_final_active(write_pkg(tmp_path, rs, header=[*COLUMNS[:-1], "extra"]))


def test_all_violations_are_reported_together(tmp_path):
    rs = rows()
    rs[1]["quote"] = ""
    rs[2]["philosophical_move"] = ""
    with pytest.raises(FinalCorpusError) as exc:
        load_final_active(write_pkg(tmp_path, rs))
    assert len(exc.value.problems) == 2


def test_snapshot_keeps_ids_text_and_fills_nothing(cards):
    frags = final_snapshot_fragments(cards)
    by = {c.card_id: c for c in cards}
    assert [f.id for f in frags] == [c.card_id for c in cards]
    for f in frags:
        c = by[f.id]
        assert (f.work, f.location, f.fragment, f.translation) == (c.work, c.location, c.quote, c.translator)
        assert f.technical.launch_philosophical_move == c.philosophical_move
        assert f.perspective is None and f.coordinates is None and f.tensions is None and f.tradition is None
        assert f.philosophical_operation is None
    assert len(retrieval_universe(frags)) == 967

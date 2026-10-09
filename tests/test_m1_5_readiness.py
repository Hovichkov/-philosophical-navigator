"""M1.5 — corpus retrieval readiness regression tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from navigator.corpus.readiness import (
    generic_questions,
    is_editorial,
    meaning_inputs,
    meaning_readiness,
    retrieval_universe,
    structure_inputs,
    structure_ready,
)
from navigator.corpus.validator import validate_corpus_file
from navigator.models.fragment import Fragment
from navigator.models.vocabularies import UNRESOLVED_IDS

from test_validator import corpus, run, unresolved

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/corpus/fragments.jsonl"
MANIFEST = ROOT / "data/corpus/launch-manifest.json"
FOCUS = ["C1105", "C0957", "C0937", "C0949", "C0527", "C0339"]

needs_corpus = pytest.mark.skipif(not CORPUS.exists(), reason="canonical corpus not built")


@pytest.fixture(scope="module")
def fragments() -> list[Fragment]:
    return [Fragment.model_validate(json.loads(line)) for line in CORPUS.read_text(encoding="utf-8").splitlines()]


@pytest.fixture(scope="module")
def universe(fragments) -> list[Fragment]:
    return retrieval_universe(fragments)


# ------------------------------------------------------------------ corpus invariants


@needs_corpus
def test_corpus_invariant_124_113_11(fragments, universe):
    assert len(fragments) == 124
    assert len(universe) == 113
    assert {f.id for f in fragments if f.technical.operational_status == "unresolved"} == UNRESOLVED_IDS


@needs_corpus
def test_unresolved_never_enter_meaning_or_structure_retrieval(universe):
    ids = {f.id for f in universe}
    assert not ids & UNRESOLVED_IDS
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert not set(manifest["retrieval_allowlist"]) & UNRESOLVED_IDS


@needs_corpus
def test_validator_passes_with_readiness_checks():
    result = validate_corpus_file(CORPUS, MANIFEST)
    assert result.ok, result.errors[:5]
    assert not {"MEANING_NOT_READY", "STRUCTURE_NOT_READY", "EDITORIAL_TEXT_IN_MEANING"} & result.codes("error")


# ------------------------------------------------------------------ MEANING / STRUCTURE readiness


@needs_corpus
def test_all_113_have_usable_meaning(universe):
    generic = generic_questions(universe)
    not_usable = [f.id for f in universe if not meaning_readiness(f, generic).usable]
    assert not_usable == []


@needs_corpus
@pytest.mark.parametrize("fid", FOCUS)
def test_focus_cards_meaning_ready(universe, fid):
    generic = generic_questions(universe)
    frag = next(f for f in universe if f.id == fid)
    assert meaning_readiness(frag, generic).state == "READY"


@needs_corpus
def test_all_113_structure_ready(universe):
    assert [f.id for f in universe if not structure_ready(f)] == []


@needs_corpus
def test_former_empty_four_are_recovery_marked(fragments):
    by_id = {f.id: f for f in fragments}
    for fid in ("C1105", "C0957", "C0937", "C0949"):
        f = by_id[fid]
        assert f.perspective and f.coordinates and f.philosophical_questions
        assert f.thought is None and f.fragment is None  # not restored in M1.5
        assert f.technical.recovery_status.startswith("approved_batch_membership_confirmed")
        assert "CORPUS-FULL-1090" in f.technical.field_provenance["perspective"]
        assert f.technical.curation and "perspective" in f.technical.curation


@needs_corpus
def test_c0527_perspective_is_philosophical_and_old_note_preserved(fragments):
    f = next(x for x in fragments if x.id == "C0527")
    assert not is_editorial(f.perspective)
    assert f.technical.field_provenance["perspective"].startswith("EDITORIAL RECONSTRUCTION")
    assert "Сохранять притчу целиком" in f.technical.curation["perspective"]


@needs_corpus
def test_c0339_meaning_keeps_its_move_without_thought(fragments):
    f = next(x for x in fragments if x.id == "C0339")
    assert f.thought is None  # Thought intentionally left for the exact-text pass
    text = " ".join(sum(meaning_inputs(f).values(), []))
    assert "полноту в отсутствующее" in text


# ------------------------------------------------------------------ placeholder safety


@needs_corpus
def test_no_placeholder_or_editorial_text_in_retrieval_inputs(universe):
    for f in universe:
        for values in (*meaning_inputs(f).values(), *structure_inputs(f).values()):
            assert not any(is_editorial(v) for v in values), f.id


def test_meaning_inputs_drop_placeholders():
    rec = corpus()[0]
    rec["thought"] = "[FINAL TEXTUAL PASS: вставить короткий дословный Thought]"
    rec["perspective"] = "сильный кандидат для `ожидание ↔ действительность`. Сохранять притчу целиком."
    frag = Fragment.model_validate(rec)
    inputs = meaning_inputs(frag)
    assert "thought" not in inputs and "perspective" not in inputs


def test_editorial_perspective_is_blocking_for_eligible_fragment():
    records = corpus()
    records[0]["perspective"] = "сильный кандидат для `ожидание ↔ действительность`. Сохранять притчу целиком."
    assert "EDITORIAL_TEXT_IN_MEANING" in run(records).codes("error")


def test_generic_only_meaning_is_not_ready():
    records = corpus()
    for r in records:
        r["thought"] = None
        r["perspective"] = None
        r["philosophical_questions"] = ["Как меняется оценка ситуации, если принять исходные предпосылки самого текста?"]
    assert "MEANING_NOT_READY" in run(records).codes("error")


def test_unresolved_is_outside_retrieval_universe_even_if_complete():
    records = corpus(4)
    unresolved(records[2])
    frags = [Fragment.model_validate(r) for r in records]
    assert [f.id for f in retrieval_universe(frags)] == [records[0]["id"], records[1]["id"], records[3]["id"]]


# ------------------------------------------------------------------ SOURCE route


@needs_corpus
def test_source_route_stays_disabled(fragments):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["routes"]["SOURCE"] == "disabled_pending_full_fragment_text"
    assert all(f.fragment is None for f in fragments)

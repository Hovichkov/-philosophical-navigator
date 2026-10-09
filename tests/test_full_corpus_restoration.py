"""Full-corpus restoration: data/corpus-full is CORPUS-FULL-1090 in the current schema; data/corpus is untouched."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from navigator.corpus.full_restore import assemble_full, inline_pali_reference
from navigator.corpus.readiness import retrieval_universe
from navigator.models.fragment import Fragment
from navigator.models.vocabularies import UNRESOLVED_IDS
from navigator.prototype.server import CORPORA

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return [Fragment.model_validate(json.loads(l)) for l in (ROOT / path).read_text(encoding="utf-8").splitlines()]


@pytest.fixture(scope="module")
def full():
    return load("data/corpus-full/fragments.jsonl")


@pytest.fixture(scope="module")
def compact():
    return load("data/corpus/fragments.jsonl")


def test_full_corpus_has_every_registry_row_once(full):
    ids = [f.id for f in full]
    assert len(ids) == 1090 and len(set(ids)) == 1090
    m = json.loads((ROOT / "data/corpus-full/manifest.json").read_text(encoding="utf-8"))
    assert m["counts"]["total"] == 1090 and m["counts"]["retrieval_eligible"] == 815
    assert m["counts"]["by_status"] == {"verified": 113, "unresolved": 11, "registry_curated": 702, "registry_reserve": 264}
    assert m["fragments_sha256"] == hashlib.sha256((ROOT / "data/corpus-full/fragments.jsonl").read_bytes()).hexdigest()


def test_launch_cards_are_copied_verbatim(full, compact):
    by = {f.id: f for f in full}
    for f in compact:
        assert by[f.id] == f  # same fields, same status, same textual-pass content


def test_eligibility_rules(full):
    universe = {f.id for f in retrieval_universe(full)}
    assert len(universe) == 815 and not universe & UNRESOLVED_IDS
    for f in full:
        if f.technical.operational_status == "registry_reserve":
            assert not f.technical.retrieval_eligible and f.perspective is None
        if f.technical.operational_status == "registry_curated":
            assert f.technical.retrieval_eligible and f.perspective and f.philosophical_questions
            assert f.fragment is None and f.thought is None  # no source text is invented


def test_pali_references_are_recovered(full):
    by = {f.id: f for f in full}
    assert (by["C0210"].work, by["C0210"].location) == ("Дхаммачаккаппаваттана сутта", "СН 56.11")
    assert (by["C0253"].work, by["C0253"].location) == ("Бхаддекаратта сутта", "МН 131")
    assert (by["C0259"].work, by["C0259"].location) == ("Дведха-витакка сутта", "МН 19")
    broken = [f.id for f in full if f.technical.retrieval_eligible and f.work == "Дхаммачаккаппаваттана сутта — СН 56.11"]
    assert broken == []
    assert inline_pali_reference("**Уд 1.10, финал**") == ("Палийский канон", "Уд 1.10")
    assert inline_pali_reference("**Махамангала сутта Сн 2.4**") == ("Махамангала сутта", "Сн 2.4")


def test_restoration_is_reproducible(full):
    rebuilt, _ = assemble_full(ROOT)
    assert [f.model_dump(mode="json") for f in rebuilt] == [f.model_dump(mode="json") for f in full]


def test_compact_corpus_and_its_index_stay_the_default():
    assert CORPORA["compact"][0] == "data/corpus/fragments.jsonl"
    assert CORPORA["full"][2] != CORPORA["compact"][2]  # separate embedding cache: the compact index is not touched
    assert hashlib.sha256((ROOT / "data/corpus/fragments.jsonl").read_bytes()).hexdigest().startswith("5554aa8c0")
